"""Model capability data and diff comparison."""

from __future__ import annotations

from dataclasses import dataclass

KNOWN_CAPABILITIES: dict[str, dict] = {
    "openai/gpt-3.5-turbo": {
        "context_window": 16385, "max_output": 4096,
        "vision": False, "tools": True, "json_mode": True, "streaming": True,
    },
    "openai/gpt-4": {
        "context_window": 8192, "max_output": 8192,
        "vision": False, "tools": True, "json_mode": True, "streaming": True,
    },
    "openai/gpt-4-turbo-preview": {
        "context_window": 128000, "max_output": 4096,
        "vision": True, "tools": True, "json_mode": True, "streaming": True,
    },
    "openai/gpt-4o": {
        "context_window": 128000, "max_output": 16384,
        "vision": True, "tools": True, "json_mode": True, "streaming": True,
    },
    "openai/gpt-4o-mini": {
        "context_window": 128000, "max_output": 16384,
        "vision": True, "tools": True, "json_mode": True, "streaming": True,
    },
    "openai/gpt-4.1": {
        "context_window": 1048576, "max_output": 32768,
        "vision": True, "tools": True, "json_mode": True, "streaming": True,
    },
    "openai/gpt-4.1-mini": {
        "context_window": 1048576, "max_output": 32768,
        "vision": True, "tools": True, "json_mode": True, "streaming": True,
    },
    "openai/o1": {
        "context_window": 200000, "max_output": 100000,
        "vision": True, "tools": True, "json_mode": True, "streaming": True,
    },
    "openai/o3-mini": {
        "context_window": 200000, "max_output": 100000,
        "vision": False, "tools": True, "json_mode": True, "streaming": True,
    },
    "anthropic/claude-2.1": {
        "context_window": 200000, "max_output": 4096,
        "vision": False, "tools": False, "json_mode": False, "streaming": True,
    },
    "anthropic/claude-3-opus-20240229": {
        "context_window": 200000, "max_output": 4096,
        "vision": True, "tools": True, "json_mode": False, "streaming": True,
    },
    "anthropic/claude-3-sonnet-20240229": {
        "context_window": 200000, "max_output": 4096,
        "vision": True, "tools": True, "json_mode": False, "streaming": True,
    },
    "anthropic/claude-3.5-sonnet-20241022": {
        "context_window": 200000, "max_output": 8192,
        "vision": True, "tools": True, "json_mode": False, "streaming": True,
    },
    "anthropic/claude-sonnet-4-20250514": {
        "context_window": 200000, "max_output": 16384,
        "vision": True, "tools": True, "json_mode": False, "streaming": True,
    },
    "google/gemini-1.0-pro": {
        "context_window": 32760, "max_output": 8192,
        "vision": False, "tools": True, "json_mode": True, "streaming": True,
    },
    "google/gemini-1.5-pro": {
        "context_window": 2097152, "max_output": 8192,
        "vision": True, "tools": True, "json_mode": True, "streaming": True,
    },
    "google/gemini-1.5-flash": {
        "context_window": 1048576, "max_output": 8192,
        "vision": True, "tools": True, "json_mode": True, "streaming": True,
    },
    "google/gemini-2.0-flash": {
        "context_window": 1048576, "max_output": 8192,
        "vision": True, "tools": True, "json_mode": True, "streaming": True,
    },
    "mistral/mistral-large-latest": {
        "context_window": 128000, "max_output": 8192,
        "vision": False, "tools": True, "json_mode": True, "streaming": True,
    },
    "mistral/mistral-small-latest": {
        "context_window": 32000, "max_output": 8192,
        "vision": False, "tools": True, "json_mode": True, "streaming": True,
    },
}

CAPABILITY_LABELS = {
    "context_window": "Context Window",
    "max_output": "Max Output Tokens",
    "vision": "Vision",
    "tools": "Tool Use",
    "json_mode": "JSON Mode",
    "streaming": "Streaming",
}


@dataclass
class CapabilityDiff:
    field: str
    label: str
    old_value: str
    new_value: str
    change_type: str  # "improved", "degraded", "same", "gained", "lost"


def get_capabilities(model_id: str) -> dict | None:
    return KNOWN_CAPABILITIES.get(model_id)


def diff_capabilities(old_model: str, new_model: str) -> list[CapabilityDiff]:
    old_caps = get_capabilities(old_model)
    new_caps = get_capabilities(new_model)
    if old_caps is None or new_caps is None:
        return []

    diffs: list[CapabilityDiff] = []
    for field, label in CAPABILITY_LABELS.items():
        old_val = old_caps.get(field)
        new_val = new_caps.get(field)
        if old_val is None or new_val is None:
            continue

        if isinstance(old_val, bool):
            if old_val == new_val:
                change = "same"
            elif new_val:
                change = "gained"
            else:
                change = "lost"
            old_str, new_str = "Yes" if old_val else "No", "Yes" if new_val else "No"
        else:
            old_str, new_str = _format_number(old_val), _format_number(new_val)
            if old_val == new_val:
                change = "same"
            elif new_val > old_val:
                change = "improved"
            else:
                change = "degraded"

        diffs.append(CapabilityDiff(field, label, old_str, new_str, change))
    return diffs


def _format_number(n: int | float) -> str:
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.0f}k"
    return str(n)
