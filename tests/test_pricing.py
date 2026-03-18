"""Tests for the pricing module."""

from chowkidar.pricing import compare_cost, get_pricing


def test_get_pricing_known():
    p = get_pricing("openai/gpt-3.5-turbo")
    assert p is not None
    assert p["input"] == 0.50
    assert p["output"] == 1.50


def test_get_pricing_unknown():
    assert get_pricing("unknown/model") is None


def test_compare_cost_known():
    result = compare_cost("openai/gpt-3.5-turbo", "openai/gpt-4o-mini")
    assert result is not None
    assert result.current_input == 0.50
    assert result.replacement_input == 0.15
    assert "saves" in result.summary.lower()


def test_compare_cost_more_expensive():
    result = compare_cost("openai/gpt-4o-mini", "openai/gpt-4o")
    assert result is not None
    assert "more" in result.summary.lower() or "costs" in result.summary.lower()


def test_compare_cost_unknown():
    assert compare_cost("unknown/a", "unknown/b") is None


def test_compare_cost_partial_unknown():
    assert compare_cost("openai/gpt-4o", "unknown/model") is None


def test_context_window_in_pricing():
    p = get_pricing("openai/gpt-4o")
    assert p is not None
    assert p["context"] == 128000
