"""Deprecation prediction — estimate sunset dates from historical data."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from .registry.db import ModelRecord


@dataclass
class PredictionResult:
    model_id: str
    provider: str
    created_at: str | None
    estimated_sunset: str | None
    confidence: str  # "high", "medium", "low"
    basis: str  # explanation of how it was estimated

PROVIDER_AVERAGE_LIFESPANS: dict[str, int] = {
    "openai": 14,
    "anthropic": 18,
    "google": 12,
    "mistral": 10,
}


def predict_deprecation(model: ModelRecord) -> PredictionResult | None:
    """Estimate when a model might be deprecated based on provider lifecycle averages."""
    if model.sunset_date:
        return None

    avg_months = PROVIDER_AVERAGE_LIFESPANS.get(model.provider)
    if avg_months is None:
        return PredictionResult(
            model_id=model.id,
            provider=model.provider,
            created_at=model.created_at,
            estimated_sunset=None,
            confidence="low",
            basis=f"No lifecycle data available for provider '{model.provider}'.",
        )

    if model.created_at:
        try:
            created = datetime.fromisoformat(model.created_at)
            estimated = created.replace(month=((created.month - 1 + avg_months) % 12) + 1)
            year_add = (created.month - 1 + avg_months) // 12
            estimated = estimated.replace(year=created.year + year_add)
            return PredictionResult(
                model_id=model.id,
                provider=model.provider,
                created_at=model.created_at,
                estimated_sunset=estimated.strftime("%Y-%m-%d"),
                confidence="medium",
                basis=f"{model.provider} models average ~{avg_months} months lifespan.",
            )
        except (ValueError, OverflowError):
            pass

    return PredictionResult(
        model_id=model.id,
        provider=model.provider,
        created_at=model.created_at,
        estimated_sunset=None,
        confidence="low",
        basis=f"Based on {model.provider} average: ~{avg_months} months, but no creation date known.",
    )


def predict_all(models: list[ModelRecord]) -> list[PredictionResult]:
    """Predict deprecation for all models without existing sunset dates."""
    results: list[PredictionResult] = []
    for m in models:
        pred = predict_deprecation(m)
        if pred is not None:
            results.append(pred)
    return results


def get_provider_lifecycle_stats(models: list[ModelRecord]) -> dict[str, dict]:
    """Calculate observed lifecycle statistics per provider from historical data."""
    stats: dict[str, list[int]] = {}

    for m in models:
        if m.sunset_date and m.created_at:
            try:
                created = datetime.fromisoformat(m.created_at)
                sunset = datetime.fromisoformat(m.sunset_date)
                months = max(1, (sunset - created).days // 30)
                stats.setdefault(m.provider, []).append(months)
            except ValueError:
                continue

    result: dict[str, dict] = {}
    for provider, lifespans in stats.items():
        result[provider] = {
            "avg_months": round(sum(lifespans) / len(lifespans), 1),
            "min_months": min(lifespans),
            "max_months": max(lifespans),
            "sample_size": len(lifespans),
        }
    return result
