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


ADVISORY_PROMPT = """\
You are an expert AI models and LLMOps advisor. \
Given a list of expiring or legacy AI models used in a software project, analyze their usage context (based on variable names, file names, and current model types) and recommend the best modern, cost-optimized, and capability-matched replacements.

Input Context:
{context_json}

Your goal:
For each used model, infer its purpose, analyze the best successor, and output structured recommendations.
Consider:
- Cost: Prefer modern cheaper models (e.g. gpt-4o-mini is 60%+ cheaper than gpt-3.5-turbo, claude-3-haiku is much cheaper than claude-2.1).
- Context size and capabilities: Ensure replacement has similar or better context size, tool use, JSON support, or vision support if the variable/model suggests it.
- Risk/confidence level.

Return a JSON object with a single "advisory" key containing a list of objects. Each object must have:
- "variable": (string) the variable name from input
- "file": (string) the file path from input
- "model": (string) the current model from input
- "purpose": (string) inferred purpose of the model (e.g. "chat completion", "embeddings", "vision task", "fallback")
- "recommended_model": (string) the primary recommended replacement model ID
- "confidence": (string) "high", "medium", or "low"
- "reason": (string) concise reason for this specific choice, mentioning cost/speed/capability benefits
- "risk": (string) concise risk notes (e.g. "losses JSON mode support", "smaller context window", "requires manual review of prompt templates")

Return ONLY the raw JSON object. Do not include any markdown fences or conversational preambles.
"""


def format_advisory_prompt(context: dict) -> str:
    """Format the advisory prompt with the given project/model context."""
    context_json = json.dumps(context, indent=2)
    return ADVISORY_PROMPT.format(context_json=context_json)


def parse_advisory_response(response: str) -> dict | None:
    """Parse and validate the SLM's advisory JSON response."""
    response = response.strip()

    # Strip any potential markdown code blocks if the model ignored instructions
    json_match = re.search(r"\{.*\}", response, re.DOTALL)
    if json_match:
        response = json_match.group()

    try:
        data = json.loads(response)
    except json.JSONDecodeError:
        logger.warning("SLM response is not valid JSON: %s", response[:200])
        return None

    if not isinstance(data, dict) or "advisory" not in data:
        logger.warning("SLM response is not a valid advisory dictionary")
        return None

    return data


def _is_valid_date(date_str: str) -> bool:
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        return dt.year >= 2020 and dt.year <= 2030
    except ValueError:
        return False
