"""OpenAI provider adapter — scrapes deprecation data from public docs and API."""

from __future__ import annotations

import logging
import re
from datetime import datetime

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from .base import DeprecationNotice, ModelInfo

logger = logging.getLogger(__name__)

OPENAI_DEPRECATIONS_URL = "https://platform.openai.com/docs/deprecations"
OPENAI_MODELS_URL = "https://api.openai.com/v1/models"

KNOWN_OPENAI_MODELS: list[dict[str, str | None]] = [
    {"id": "gpt-3.5-turbo-0301", "sunset": "2024-06-13", "replacement": "gpt-3.5-turbo"},
    {"id": "gpt-3.5-turbo-0613", "sunset": "2024-06-13", "replacement": "gpt-3.5-turbo"},
    {"id": "gpt-3.5-turbo-1106", "sunset": "2025-06-01", "replacement": "gpt-4o-mini"},
    {"id": "gpt-3.5-turbo-0125", "sunset": "2025-09-01", "replacement": "gpt-4o-mini"},
    {"id": "gpt-3.5-turbo", "sunset": "2025-09-01", "replacement": "gpt-4o-mini"},
    {"id": "gpt-4-0314", "sunset": "2025-06-06", "replacement": "gpt-4o"},
    {"id": "gpt-4-0613", "sunset": "2025-06-06", "replacement": "gpt-4o"},
    {"id": "gpt-4-32k-0314", "sunset": "2025-06-06", "replacement": "gpt-4o"},
    {"id": "gpt-4-32k-0613", "sunset": "2025-06-06", "replacement": "gpt-4o"},
    {"id": "gpt-4-1106-preview", "sunset": "2025-06-06", "replacement": "gpt-4o"},
    {"id": "gpt-4-0125-preview", "sunset": "2025-06-06", "replacement": "gpt-4o"},
    {"id": "gpt-4-turbo-preview", "sunset": "2025-06-06", "replacement": "gpt-4o"},
    {"id": "gpt-4-vision-preview", "sunset": "2025-06-06", "replacement": "gpt-4o"},
    {"id": "gpt-4o-2024-05-13", "sunset": None, "replacement": "gpt-4o"},
    {"id": "gpt-4o", "sunset": None, "replacement": None},
    {"id": "gpt-4o-mini", "sunset": None, "replacement": None},
    {"id": "gpt-4.1", "sunset": None, "replacement": None},
    {"id": "gpt-4.1-mini", "sunset": None, "replacement": None},
    {"id": "gpt-4.1-nano", "sunset": None, "replacement": None},
    {"id": "o1", "sunset": None, "replacement": None},
    {"id": "o1-mini", "sunset": None, "replacement": None},
    {"id": "o1-preview", "sunset": None, "replacement": "o1"},
    {"id": "o3", "sunset": None, "replacement": None},
    {"id": "o3-mini", "sunset": None, "replacement": None},
    {"id": "o4-mini", "sunset": None, "replacement": None},
    {"id": "text-embedding-ada-002", "sunset": None, "replacement": "text-embedding-3-small"},
]


class OpenAIProvider:
    name = "openai"

    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=30))
    async def fetch_models(self) -> list[ModelInfo]:
        """Fetch models from OpenAI. Uses API if key available, otherwise known list."""
        models: list[ModelInfo] = []

        if self.api_key:
            try:
                async with httpx.AsyncClient(timeout=30) as client:
                    resp = await client.get(
                        OPENAI_MODELS_URL,
                        headers={"Authorization": f"Bearer {self.api_key}"},
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        for m in data.get("data", []):
                            models.append(ModelInfo(
                                id=m["id"], provider="openai",
                                created_date=str(m.get("created", "")),
                            ))
                        return models
            except httpx.HTTPError as e:
                logger.warning("OpenAI API fetch failed, falling back to known list: %s", e)

        for m in KNOWN_OPENAI_MODELS:
            models.append(ModelInfo(id=str(m["id"]), provider="openai"))
        return models

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=30))
    async def fetch_deprecations(self) -> list[DeprecationNotice]:
        """Fetch deprecation notices. Merges known data with scraped data."""
        notices_by_id: dict[str, DeprecationNotice] = {}

        for m in KNOWN_OPENAI_MODELS:
            if m["sunset"]:
                model_id = f"openai/{m['id']}"
                notices_by_id[model_id] = DeprecationNotice(
                    model_id=model_id,
                    provider="openai",
                    sunset_date=m["sunset"],
                    replacement=f"openai/{m['replacement']}" if m["replacement"] else None,
                    replacement_confidence="high",
                    source_url=OPENAI_DEPRECATIONS_URL,
                )

        try:
            async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
                resp = await client.get(OPENAI_DEPRECATIONS_URL)
                if resp.status_code == 200:
                    scraped = self._parse_deprecations_page(resp.text)
                    for s in scraped:
                        notices_by_id[s.model_id] = s
        except httpx.HTTPError as e:
            logger.warning("Failed to scrape OpenAI deprecations page: %s", e)

        return list(notices_by_id.values())

    def _parse_deprecations_page(self, html: str) -> list[DeprecationNotice]:
        """Best-effort extraction of deprecation dates from the docs HTML."""
        notices: list[DeprecationNotice] = []
        date_pattern = re.compile(
            r"(gpt-[0-9a-z._-]+)\s*.*?(?:deprecated?|sunset|shutdown|retire)\w*\s*"
            r"(?:on|by|:)?\s*(\d{4}-\d{2}-\d{2}|\w+\s+\d{1,2},?\s+\d{4})",
            re.IGNORECASE,
        )
        for match in date_pattern.finditer(html):
            model_name = match.group(1).strip()
            date_str = match.group(2).strip()
            try:
                for fmt in ("%Y-%m-%d", "%B %d, %Y", "%B %d %Y"):
                    try:
                        parsed = datetime.strptime(date_str, fmt)
                        date_str = parsed.strftime("%Y-%m-%d")
                        break
                    except ValueError:
                        continue
            except Exception:
                continue

            notices.append(DeprecationNotice(
                model_id=f"openai/{model_name}",
                provider="openai",
                sunset_date=date_str,
                source_url=OPENAI_DEPRECATIONS_URL,
            ))
        return notices
