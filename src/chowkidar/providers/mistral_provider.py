"""Mistral provider adapter — scrapes deprecation data from docs."""

from __future__ import annotations

import logging
import re

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from .base import DeprecationNotice, ModelInfo

logger = logging.getLogger(__name__)

MISTRAL_DOCS_URL = "https://docs.mistral.ai/getting-started/models/"

KNOWN_MISTRAL_MODELS: list[dict[str, str | None]] = [
    {"id": "mistral-tiny", "sunset": "2024-06-01", "replacement": "open-mistral-7b"},
    {"id": "mistral-small-2312", "sunset": "2024-06-01", "replacement": "mistral-small-latest"},
    {"id": "mistral-medium-2312", "sunset": "2024-09-01", "replacement": "mistral-large-latest"},
    {"id": "mistral-small-latest", "sunset": None, "replacement": None},
    {"id": "mistral-medium-latest", "sunset": None, "replacement": "mistral-large-latest"},
    {"id": "mistral-large-latest", "sunset": None, "replacement": None},
    {"id": "open-mistral-7b", "sunset": None, "replacement": None},
    {"id": "open-mistral-nemo", "sunset": None, "replacement": None},
    {"id": "open-mixtral-8x7b", "sunset": None, "replacement": None},
    {"id": "open-mixtral-8x22b", "sunset": None, "replacement": None},
    {"id": "codestral-latest", "sunset": None, "replacement": None},
    {"id": "mistral-embed", "sunset": None, "replacement": None},
    {"id": "pixtral-large-latest", "sunset": None, "replacement": None},
    {"id": "pixtral-12b-latest", "sunset": None, "replacement": None},
]


class MistralProvider:
    name = "mistral"

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=30))
    async def fetch_models(self) -> list[ModelInfo]:
        models: list[ModelInfo] = []
        for m in KNOWN_MISTRAL_MODELS:
            models.append(ModelInfo(
                id=str(m["id"]), provider="mistral",
                is_active=m["sunset"] is None,
            ))
        return models

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=30))
    async def fetch_deprecations(self) -> list[DeprecationNotice]:
        notices_by_id: dict[str, DeprecationNotice] = {}

        for m in KNOWN_MISTRAL_MODELS:
            if m["sunset"]:
                model_id = f"mistral/{m['id']}"
                notices_by_id[model_id] = DeprecationNotice(
                    model_id=model_id,
                    provider="mistral",
                    sunset_date=m["sunset"],
                    replacement=f"mistral/{m['replacement']}" if m["replacement"] else None,
                    replacement_confidence="high",
                    source_url=MISTRAL_DOCS_URL,
                )

        try:
            async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
                resp = await client.get(MISTRAL_DOCS_URL)
                if resp.status_code == 200:
                    scraped = self._parse_docs_page(resp.text)
                    for s in scraped:
                        notices_by_id[s.model_id] = s
        except httpx.HTTPError as e:
            logger.warning("Failed to scrape Mistral docs: %s", e)

        return list(notices_by_id.values())

    def _parse_docs_page(self, html: str) -> list[DeprecationNotice]:
        notices: list[DeprecationNotice] = []
        pattern = re.compile(
            r"(mistral-[0-9a-z._-]+|codestral[0-9a-z._-]*|open-mi[xs]tral-[0-9a-z._-]+)\s*.*?"
            r"(?:deprecated?|sunset|legacy|retire)\w*\s*"
            r"(?:on|by|:)?\s*(\d{4}-\d{2}-\d{2}|\w+\s+\d{1,2},?\s+\d{4})",
            re.IGNORECASE,
        )
        for match in pattern.finditer(html):
            notices.append(DeprecationNotice(
                model_id=f"mistral/{match.group(1).strip()}",
                provider="mistral",
                sunset_date=match.group(2).strip(),
                source_url=MISTRAL_DOCS_URL,
            ))
        return notices
