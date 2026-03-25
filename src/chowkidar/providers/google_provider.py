"""Google AI provider adapter — scrapes deprecation data from Vertex AI docs."""

from __future__ import annotations

import logging
import re

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from .base import DeprecationNotice, ModelInfo

logger = logging.getLogger(__name__)

GOOGLE_MODELS_URL = "https://cloud.google.com/vertex-ai/generative-ai/docs/learn/model-versions"

KNOWN_GOOGLE_MODELS: list[dict[str, str | None]] = [
    {"id": "gemini-1.0-pro", "sunset": "2025-04-09", "replacement": "gemini-1.5-pro"},
    {"id": "gemini-1.0-pro-001", "sunset": "2025-04-09", "replacement": "gemini-1.5-pro"},
    {"id": "gemini-1.0-ultra", "sunset": "2025-04-09", "replacement": "gemini-1.5-pro"},
    {"id": "gemini-pro", "sunset": "2025-04-09", "replacement": "gemini-1.5-pro"},
    {"id": "gemini-1.5-pro", "sunset": None, "replacement": None},
    {"id": "gemini-1.5-flash", "sunset": None, "replacement": None},
    {"id": "gemini-2.0-flash", "sunset": None, "replacement": None},
    {"id": "gemini-2.0-flash-lite", "sunset": None, "replacement": None},
    {"id": "gemini-2.5-pro-preview", "sunset": None, "replacement": None},
    {"id": "gemini-2.5-flash-preview", "sunset": None, "replacement": None},
    {"id": "text-bison", "sunset": "2025-04-09", "replacement": "gemini-1.5-flash"},
    {"id": "chat-bison", "sunset": "2025-04-09", "replacement": "gemini-1.5-flash"},
]


class GoogleProvider:
    name = "google"

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=30))
    async def fetch_models(self) -> list[ModelInfo]:
        models: list[ModelInfo] = []
        for m in KNOWN_GOOGLE_MODELS:
            models.append(ModelInfo(
                id=str(m["id"]), provider="google",
                is_active=m["sunset"] is None,
            ))
        return models

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=30))
    async def fetch_deprecations(self) -> list[DeprecationNotice]:
        notices_by_id: dict[str, DeprecationNotice] = {}

        for m in KNOWN_GOOGLE_MODELS:
            if m["sunset"]:
                model_id = f"google/{m['id']}"
                notices_by_id[model_id] = DeprecationNotice(
                    model_id=model_id,
                    provider="google",
                    sunset_date=m["sunset"],
                    replacement=f"google/{m['replacement']}" if m["replacement"] else None,
                    replacement_confidence="high",
                    source_url=GOOGLE_MODELS_URL,
                )

        try:
            async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
                resp = await client.get(GOOGLE_MODELS_URL)
                if resp.status_code == 200:
                    scraped = self._parse_docs_page(resp.text)
                    for s in scraped:
                        notices_by_id[s.model_id] = s
        except httpx.HTTPError as e:
            logger.warning("Failed to scrape Google AI docs: %s", e)

        return list(notices_by_id.values())

    def _parse_docs_page(self, html: str) -> list[DeprecationNotice]:
        notices: list[DeprecationNotice] = []
        pattern = re.compile(
            r"(gemini-[0-9a-z._-]+|text-bison[0-9a-z._-]*|chat-bison[0-9a-z._-]*)\s*.*?"
            r"(?:deprecated?|sunset|discontinue|end.of.life)\w*\s*"
            r"(?:on|by|:)?\s*(\d{4}-\d{2}-\d{2}|\w+\s+\d{1,2},?\s+\d{4})",
            re.IGNORECASE,
        )
        for match in pattern.finditer(html):
            notices.append(DeprecationNotice(
                model_id=f"google/{match.group(1).strip()}",
                provider="google",
                sunset_date=match.group(2).strip(),
                source_url=GOOGLE_MODELS_URL,
            ))
        return notices
