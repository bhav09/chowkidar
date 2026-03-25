"""Prompt templates for SLM-based structured extraction of deprecation notices."""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime

logger = logging.getLogger(__name__)

DEPRECATION_EXTRACTION_PROMPT = """\
You are a structured data extractor. \
Given a text about AI model deprecation or sunset, extract ALL deprecation notices.

Return a JSON array where each element has:
- "model": the exact model name/id being deprecated (string)
- "provider": the provider name — one of "openai", "anthropic", "google", "mistral", or "other" (string)
- "sunset_date": the deprecation/sunset date in YYYY-MM-DD format, or null if not specified (string or null)
- "replacement": the recommended replacement model name, or null if not specified (string or null)
- "confidence": how confident you are in this extraction — "high", "medium", or "low" (string)

Rules:
- Only extract actual deprecation/sunset announcements, not general model listings
- Dates must be valid calendar dates
- Model names must match real provider naming conventions
- If no deprecation notices are found, return an empty array []

Return ONLY the JSON array, no other text.

TEXT:
{text}"""


def format_extraction_prompt(text: str) -> str:
    """Format the extraction prompt with the given text, truncating if too long."""
    max_text_len = 4000
    if len(text) > max_text_len:
        text = text[:max_text_len] + "\n... [truncated]"
    return DEPRECATION_EXTRACTION_PROMPT.format(text=text)


def parse_slm_response(response: str) -> list[dict[str, str | None]] | None:
    """Parse and validate the SLM's JSON response.

    Returns None if the response is invalid or fails validation.
    """
    response = response.strip()

    json_match = re.search(r"\[.*\]", response, re.DOTALL)
    if json_match:
        response = json_match.group()

    try:
        data = json.loads(response)
    except json.JSONDecodeError:
        logger.warning("SLM response is not valid JSON: %s", response[:200])
        return None

    if not isinstance(data, list):
        logger.warning("SLM response is not a JSON array")
        return None

    validated: list[dict[str, str | None]] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        if "model" not in item or not isinstance(item["model"], str):
            continue
        if len(item["model"]) < 3 or len(item["model"]) > 100:
            continue

        entry: dict[str, str | None] = {
            "model": item["model"],
            "provider": item.get("provider", "other"),
            "sunset_date": None,
            "replacement": item.get("replacement"),
            "confidence": item.get("confidence", "low"),
        }

        if item.get("sunset_date"):
            if _is_valid_date(str(item["sunset_date"])):
                entry["sunset_date"] = str(item["sunset_date"])
            else:
                logger.debug("Rejecting invalid date: %s", item["sunset_date"])
                continue

        if entry["confidence"] not in ("high", "medium", "low"):
            entry["confidence"] = "low"

        validated.append(entry)

    return validated if validated else None


def _is_valid_date(date_str: str) -> bool:
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        return dt.year >= 2020 and dt.year <= 2030
    except ValueError:
        return False
