"""Tests for the deprecation predictor module."""

from chowkidar.predictor import (
    get_provider_lifecycle_stats,
    predict_all,
    predict_deprecation,
)
from chowkidar.registry.db import ModelRecord


def _make_model(
    model_id="openai/gpt-4o",
    provider="openai",
    sunset_date=None,
    created_at="2024-05-01T00:00:00",
    **kwargs,
):
    return ModelRecord(
        id=model_id, provider=provider, aliases=[], sunset_date=sunset_date,
        replacement=None, replacement_confidence="medium", breaking_changes=False,
        source_url=None, last_checked_at=None, created_at=created_at, **kwargs,
    )


def test_predict_with_created_at():
    model = _make_model(created_at="2024-01-15T00:00:00")
    pred = predict_deprecation(model)
    assert pred is not None
    assert pred.estimated_sunset is not None
    assert pred.confidence == "medium"
    assert "14 months" in pred.basis


def test_predict_already_sunset():
    model = _make_model(sunset_date="2025-01-01")
    pred = predict_deprecation(model)
    assert pred is None


def test_predict_unknown_provider():
    model = _make_model(provider="unknown_provider", model_id="unknown/foo")
    pred = predict_deprecation(model)
    assert pred is not None
    assert pred.confidence == "low"


def test_predict_no_created_at():
    model = _make_model(created_at=None)
    pred = predict_deprecation(model)
    assert pred is not None
    assert pred.confidence == "low"


def test_predict_all():
    models = [
        _make_model(model_id="openai/gpt-4o", created_at="2024-05-01T00:00:00"),
        _make_model(model_id="openai/gpt-4", sunset_date="2025-06-01"),
    ]
    results = predict_all(models)
    assert len(results) == 1
    assert results[0].model_id == "openai/gpt-4o"


def test_lifecycle_stats():
    models = [
        _make_model(model_id="openai/a", created_at="2023-01-01T00:00:00", sunset_date="2024-03-01"),
        _make_model(model_id="openai/b", created_at="2023-06-01T00:00:00", sunset_date="2024-06-01"),
    ]
    stats = get_provider_lifecycle_stats(models)
    assert "openai" in stats
    assert stats["openai"]["sample_size"] == 2
    assert stats["openai"]["avg_months"] > 0
