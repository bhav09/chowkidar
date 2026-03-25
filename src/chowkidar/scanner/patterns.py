"""Model string regex patterns and normalization for all supported providers."""

from __future__ import annotations

import re
from dataclasses import dataclass

PROVIDER_PATTERNS: dict[str, list[str]] = {
    "openai": [
        r"gpt-4\.?1(?:-mini|-nano)?(?:-\d{4}-\d{2}-\d{2})?",
        r"gpt-4o(?:-mini)?(?:-\d{4}-\d{2}-\d{2})?",
        r"gpt-4-turbo(?:-preview)?(?:-\d{4}-\d{2}-\d{2})?",
        r"gpt-4(?:-\d{4}-\d{2}-\d{2})?",
        r"gpt-3\.5-turbo(?:-\d{4})?(?:-\d{2}-\d{2})?",
        r"o[134](?:-mini|-preview|-pro)?(?:-\d{4}-\d{2}-\d{2})?",
        r"text-embedding-(?:ada-002|3-(?:small|large))",
        r"dall-e-[23]",
        r"whisper-1",
        r"tts-1(?:-hd)?(?:-\d{4})?",
        r"chatgpt-4o-latest",
    ],
    "anthropic": [
        r"claude-(?:opus|sonnet|haiku)-4(?:-\d{8})?",
        r"claude-3\.5-(?:opus|sonnet|haiku)(?:-\d{8})?",
        r"claude-3-(?:opus|sonnet|haiku)(?:-\d{8})?",
        r"claude-2\.1",
        r"claude-2\.0",
        r"claude-instant-1\.2",
    ],
    "google": [
        r"gemini-2\.5-(?:pro|flash)(?:-preview)?(?:-\d{2}-\d{2})?",
        r"gemini-2\.0-(?:pro|flash)(?:-lite)?(?:-exp)?(?:-\d{2}-\d{2})?",
        r"gemini-1\.5-(?:pro|flash)(?:-\d{3})?",
        r"gemini-1\.0-(?:pro|ultra)(?:-\d{3})?",
        r"gemini-(?:pro|ultra)",
        r"text-bison(?:-\d{3})?",
        r"chat-bison(?:-\d{3})?",
    ],
    "mistral": [
        r"mistral-(?:large|medium|small|tiny)(?:-latest|-\d{4}-\d{2}-\d{2})?",
        r"codestral(?:-mamba)?(?:-latest|-\d{4}-\d{2}-\d{2})?",
        r"open-mistral-(?:7b|nemo)(?:-\d{4}-\d{2}-\d{2})?",
        r"open-mixtral-8x(?:7b|22b)(?:-\d{4}-\d{2}-\d{2})?",
        r"pixtral-(?:large|12b)-(?:latest|\d{4}-\d{2}-\d{2})",
        r"mistral-embed",
    ],
    "deepseek": [
        r"deepseek-(?:chat|coder|reasoner)(?:-v\d+(?:\.\d+)?)?",
    ],
    "xai": [
        r"grok-(?:3|2|beta)(?:-mini)?(?:-\d{4}-\d{2}-\d{2})?",
    ],
}

_COMBINED_PATTERN: re.Pattern[str] | None = None


def _get_combined_pattern() -> re.Pattern[str]:
    global _COMBINED_PATTERN
    if _COMBINED_PATTERN is None:
        all_patterns = []
        for patterns in PROVIDER_PATTERNS.values():
            all_patterns.extend(patterns)
        combined = "|".join(f"(?:{p})" for p in all_patterns)
        _COMBINED_PATTERN = re.compile(rf"\b({combined})\b", re.IGNORECASE)
    return _COMBINED_PATTERN


@dataclass(frozen=True)
class ModelMatch:
    """A model string found in a file."""

    model_string: str
    provider: str
    canonical_id: str


def is_model_string(text: str) -> bool:
    return bool(_get_combined_pattern().search(text))


def find_model_strings(text: str) -> list[str]:
    return _get_combined_pattern().findall(text)


def identify_provider(model_string: str) -> str | None:
    model_lower = model_string.lower()
    for provider, patterns in PROVIDER_PATTERNS.items():
        for pattern in patterns:
            if re.fullmatch(pattern, model_lower, re.IGNORECASE):
                return provider
    return None


def normalize_model_id(model_string: str) -> str:
    """Normalize a model string to a canonical 'provider/model' form."""
    provider = identify_provider(model_string)
    if provider is None:
        return model_string.lower()
    return f"{provider}/{model_string.lower()}"


def extract_models_from_text(text: str) -> list[ModelMatch]:
    """Extract all model string matches from arbitrary text."""
    results: list[ModelMatch] = []
    seen: set[str] = set()
    for match_str in find_model_strings(text):
        canonical = normalize_model_id(match_str)
        if canonical not in seen:
            seen.add(canonical)
            provider = identify_provider(match_str) or "unknown"
            results.append(ModelMatch(match_str, provider, canonical))
    return results


ENV_VAR_HINTS = re.compile(
    r"(?:model|llm|ai|openai|anthropic|claude|gemini|gpt|mistral)",
    re.IGNORECASE,
)


def is_model_variable_name(var_name: str) -> bool:
    """Heuristic: does this variable name look like it holds a model identifier?"""
    return bool(ENV_VAR_HINTS.search(var_name))
