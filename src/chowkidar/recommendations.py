"""Unified model replacement recommendations and risk validation."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from .capabilities import CapabilityDiff, diff_capabilities
from .pricing import compare_cost
from .registry.db import ModelRecord
from .scanner.patterns import normalize_model_id


BLOCKING_CAPABILITY_CHANGES = {"degraded", "lost"}


@dataclass
class Recommendation:
    current_model: str
    recommended_model: str | None
    confidence: str
    source: str
    reason: str
    risk: str
    cost_summary: str | None = None
    capability_diffs: list[dict[str, str]] = field(default_factory=list)
    commercial_risks: list[str] = field(default_factory=list)
    future_risks: list[str] = field(default_factory=list)
    privacy_risks: list[str] = field(default_factory=list)
    manual_review_required: bool = False
    auto_write_allowed: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_recommendation(
    current_model: str,
    record: ModelRecord | None,
    fallback: tuple[str, str, str] | None = None,
) -> Recommendation:
    """Build a validated recommendation from registry data plus optional fallback advice."""
    current_canonical = normalize_model_id(current_model)
    source = "none"
    recommended: str | None = None
    confidence = "none"
    reason = "No validated replacement is available."
    risk = "Manual review required before changing this model."

    if record and record.replacement:
        recommended = record.replacement
        confidence = record.replacement_confidence or "medium"
        source = "provider_registry"
        reason = f"Provider registry lists {record.replacement} as the successor."
        risk = "Verify application prompts and response expectations before production use."
    elif fallback is not None:
        recommended, confidence, reason = fallback
        source = "local_fallback"
        risk = "Fallback recommendation is heuristic. Manual review is required."

    recommendation = Recommendation(
        current_model=current_canonical,
        recommended_model=recommended,
        confidence=confidence,
        source=source,
        reason=reason,
        risk=risk,
    )

    if record and record.breaking_changes:
        recommendation.commercial_risks.append("Provider marks this migration as having breaking changes.")
        recommendation.manual_review_required = True

    if record and record.privacy_tier and record.privacy_tier != "unknown":
        recommendation.privacy_risks.append(f"Provider privacy tier: {record.privacy_tier}.")

    if not recommended:
        recommendation.manual_review_required = True
        return recommendation

    cost = compare_cost(current_canonical, recommended)
    if cost:
        recommendation.cost_summary = cost.summary
        if cost.input_delta_pct > 25 or cost.output_delta_pct > 25:
            recommendation.commercial_risks.append("Replacement may materially increase token costs.")

    capability_diffs = diff_capabilities(current_canonical, recommended)
    recommendation.capability_diffs = [_capability_diff_to_dict(d) for d in capability_diffs]
    blocking = [d for d in capability_diffs if d.change_type in BLOCKING_CAPABILITY_CHANGES]
    if blocking:
        labels = ", ".join(d.label for d in blocking)
        recommendation.manual_review_required = True
        recommendation.commercial_risks.append(f"Replacement loses or reduces capabilities: {labels}.")

    if not capability_diffs:
        recommendation.future_risks.append("Capability data is unavailable or incomplete for this model pair.")
        recommendation.manual_review_required = True

    if confidence not in {"high", "medium"}:
        recommendation.manual_review_required = True

    recommendation.auto_write_allowed = not recommendation.manual_review_required
    return recommendation


def _capability_diff_to_dict(diff: CapabilityDiff) -> dict[str, str]:
    return {
        "field": diff.field,
        "label": diff.label,
        "old_value": diff.old_value,
        "new_value": diff.new_value,
        "change_type": diff.change_type,
    }
