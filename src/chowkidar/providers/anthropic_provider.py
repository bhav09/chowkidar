"""Anthropic provider adapter — scrapes deprecation data from docs."""

from __future__ import annotations

import logging
import re

import httpx
from diskcache import Cache
from tenacity import retry, stop_after_attempt, wait_exponential

from ..config import CHOWKIDAR_HOME
from .base import DeprecationNotice, ModelInfo

logger = logging.getLogger(__name__)

ANTHROPIC_MODELS_URL = "https://docs.anthropic.com/en/docs/about-claude/models"

KNOWN_ANTHROPIC_MODELS: list[dict[str, str | None]] = [
    {"id": "claude-instant-1.2", "sunset": "2025-01-06", "replacement": "claude-3-haiku-20240307"},
    {"id": "claude-2.0", "sunset": "2025-02-24", "replacement": "claude-3-sonnet-20240229"},
    {"id": "claude-2.1", "sunset": "2025-02-24", "replacement": "claude-3-sonnet-20240229"},
    {"id": "claude-3-opus-20240229", "sunset": "2025-09-01", "replacement": "claude-sonnet-4-20250514"},
    {"id": "claude-3-sonnet-20240229", "sunset": "2025-07-21", "replacement": "claude-3.5-sonnet-20241022"},
    {"id": "claude-3-haiku-20240307", "sunset": "2025-09-01", "replacement": "claude-3.5-haiku-20241022"},
    {"id": "claude-3.5-sonnet-20240620", "sunset": "2025-07-21", "replacement": "claude-3.5-sonnet-20241022"},
    {"id": "claude-3.5-sonnet-20241022", "sunset": None, "replacement": None},
    {"id": "claude-3.5-haiku-20241022", "sunset": None, "replacement": None},
    {"id": "claude-sonnet-4-20250514", "sunset": None, "replacement": None},
    {"id": "claude-opus-4-20250514", "sunset": None, "replacement": None},
    {"id": "claude-haiku-4-20250514", "sunset": None, "replacement": None},
]


class AnthropicProvider:
    name = "anthropic"

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=30))
    async def fetch_models(self) -> list[ModelInfo]:
        models: list[ModelInfo] = []
        for m in KNOWN_ANTHROPIC_MODELS:
            models.append(ModelInfo(
                id=str(m["id"]), provider="anthropic",
                is_active=m["sunset"] is None,
            ))
        return models

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=30))
    async def fetch_deprecations(self) -> list[DeprecationNotice]:
        notices_by_id: dict[str, DeprecationNotice] = {}

        for m in KNOWN_ANTHROPIC_MODELS:
            if m["sunset"]:
                model_id = f"anthropic/{m['id']}"
                notices_by_id[model_id] = DeprecationNotice(
                    model_id=model_id,
                    provider="anthropic",
                    sunset_date=m["sunset"],
                    replacement=f"anthropic/{m['replacement']}" if m["replacement"] else None,
                    replacement_confidence="high",
                    source_url=ANTHROPIC_MODELS_URL,
                )

        try:
            with Cache(str(CHOWKIDAR_HOME / "cache" / "anthropic")) as cache:
                html = cache.get("models_html")
                if not html:
                    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
                        resp = await client.get(ANTHROPIC_MODELS_URL)
                        if resp.status_code == 200:
                            html = resp.text
                            cache.set("models_html", html, expire=86400)
                if html:
                    scraped = self._parse_models_page(html)
                    for s in scraped:
                        notices_by_id[s.model_id] = s
        except httpx.HTTPError as e:
            logger.warning("Failed to scrape Anthropic models page: %s", e)

        return list(notices_by_id.values())

    def _parse_models_page(self, html: str) -> list[DeprecationNotice]:
        notices: list[DeprecationNotice] = []
        pattern = re.compile(
            r"(claude-[0-9a-z._-]+)\s*.*?"
            r"(?:deprecated?|sunset|end.of.life|retire)\w*\s*"
            r"(?:on|by|:)?\s*(\d{4}-\d{2}-\d{2}|\w+\s+\d{1,2},?\s+\d{4})",
            re.IGNORECASE,
        )
        for match in pattern.finditer(html):
            model_name = match.group(1).strip()
            date_str = match.group(2).strip()
            notices.append(DeprecationNotice(
                model_id=f"anthropic/{model_name}",
                provider="anthropic",
                sunset_date=date_str,
                source_url=ANTHROPIC_MODELS_URL,
            ))
        return notices
