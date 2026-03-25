"""Model pricing data and cost impact analysis."""

from __future__ import annotations

from dataclasses import dataclass

KNOWN_PRICING: dict[str, dict[str, float | int]] = {
    "openai/gpt-3.5-turbo": {"input": 0.50, "output": 1.50, "context": 16385},
    "openai/gpt-3.5-turbo-0125": {"input": 0.50, "output": 1.50, "context": 16385},
    "openai/gpt-4": {"input": 30.00, "output": 60.00, "context": 8192},
    "openai/gpt-4-turbo": {"input": 10.00, "output": 30.00, "context": 128000},
    "openai/gpt-4-turbo-preview": {"input": 10.00, "output": 30.00, "context": 128000},
    "openai/gpt-4o": {"input": 2.50, "output": 10.00, "context": 128000},
    "openai/gpt-4o-mini": {"input": 0.15, "output": 0.60, "context": 128000},
    "openai/gpt-4.1": {"input": 2.00, "output": 8.00, "context": 1048576},
    "openai/gpt-4.1-mini": {"input": 0.40, "output": 1.60, "context": 1048576},
    "openai/gpt-4.1-nano": {"input": 0.10, "output": 0.40, "context": 1048576},
    "openai/o1": {"input": 15.00, "output": 60.00, "context": 200000},
    "openai/o1-mini": {"input": 1.10, "output": 4.40, "context": 128000},
    "openai/o1-preview": {"input": 15.00, "output": 60.00, "context": 128000},
    "openai/o3": {"input": 10.00, "output": 40.00, "context": 200000},
    "openai/o3-mini": {"input": 1.10, "output": 4.40, "context": 200000},
    "openai/o4-mini": {"input": 1.10, "output": 4.40, "context": 200000},
    "openai/text-embedding-ada-002": {"input": 0.10, "output": 0.0, "context": 8191},
    "openai/text-embedding-3-small": {"input": 0.02, "output": 0.0, "context": 8191},
    "openai/text-embedding-3-large": {"input": 0.13, "output": 0.0, "context": 8191},
    "anthropic/claude-2.1": {"input": 8.00, "output": 24.00, "context": 200000},
    "anthropic/claude-3-opus-20240229": {"input": 15.00, "output": 75.00, "context": 200000},
    "anthropic/claude-3-sonnet-20240229": {"input": 3.00, "output": 15.00, "context": 200000},
    "anthropic/claude-3-haiku-20240307": {"input": 0.25, "output": 1.25, "context": 200000},
    "anthropic/claude-3.5-sonnet-20241022": {"input": 3.00, "output": 15.00, "context": 200000},
    "anthropic/claude-3.5-haiku-20241022": {"input": 0.80, "output": 4.00, "context": 200000},
    "anthropic/claude-sonnet-4-20250514": {"input": 3.00, "output": 15.00, "context": 200000},
    "anthropic/claude-opus-4-20250514": {"input": 15.00, "output": 75.00, "context": 200000},
    "google/gemini-1.0-pro": {"input": 0.50, "output": 1.50, "context": 32760},
    "google/gemini-1.5-pro": {"input": 1.25, "output": 5.00, "context": 2097152},
    "google/gemini-1.5-flash": {"input": 0.075, "output": 0.30, "context": 1048576},
    "google/gemini-2.0-flash": {"input": 0.10, "output": 0.40, "context": 1048576},
    "google/gemini-2.5-pro-preview": {"input": 1.25, "output": 10.00, "context": 1048576},
    "google/gemini-2.5-flash-preview": {"input": 0.15, "output": 0.60, "context": 1048576},
    "mistral/mistral-small-latest": {"input": 0.10, "output": 0.30, "context": 32000},
    "mistral/mistral-large-latest": {"input": 2.00, "output": 6.00, "context": 128000},
    "mistral/codestral-latest": {"input": 0.30, "output": 0.90, "context": 256000},
}


@dataclass
class CostComparison:
    current_model: str
    replacement_model: str
    current_input: float
    current_output: float
    replacement_input: float
    replacement_output: float
    input_delta_pct: float
    output_delta_pct: float
    current_context: int
    replacement_context: int
    summary: str


def get_pricing(model_id: str) -> dict[str, float | int] | None:
    return KNOWN_PRICING.get(model_id)


def compare_cost(current_id: str, replacement_id: str) -> CostComparison | None:
    cur = get_pricing(current_id)
    rep = get_pricing(replacement_id)
    if cur is None or rep is None:
        return None

    ci, co = float(cur["input"]), float(cur["output"])
    ri, ro = float(rep["input"]), float(rep["output"])

    input_delta = ((ri - ci) / ci * 100) if ci > 0 else 0.0
    output_delta = ((ro - co) / co * 100) if co > 0 else 0.0

    avg_cur = (ci + co) / 2
    avg_rep = (ri + ro) / 2
    if avg_cur > 0:
        overall = ((avg_rep - avg_cur) / avg_cur) * 100
    else:
        overall = 0.0

    if overall < -10:
        summary = f"saves ~{abs(overall):.0f}%"
    elif overall > 10:
        summary = f"costs ~{overall:.0f}% more"
    else:
        summary = "similar cost"

    return CostComparison(
        current_model=current_id,
        replacement_model=replacement_id,
        current_input=ci,
        current_output=co,
        replacement_input=ri,
        replacement_output=ro,
        input_delta_pct=input_delta,
        output_delta_pct=output_delta,
        current_context=int(cur["context"]),
        replacement_context=int(rep["context"]),
        summary=summary,
    )
