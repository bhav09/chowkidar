"""Tests for the capabilities module."""

from chowkidar.capabilities import diff_capabilities, get_capabilities


def test_get_capabilities_known():
    caps = get_capabilities("openai/gpt-4o")
    assert caps is not None
    assert caps["context_window"] == 128000
    assert caps["vision"] is True


def test_get_capabilities_unknown():
    assert get_capabilities("unknown/model") is None


def test_diff_both_known():
    diffs = diff_capabilities("openai/gpt-3.5-turbo", "openai/gpt-4o")
    assert len(diffs) > 0

    context_diff = next(d for d in diffs if d.field == "context_window")
    assert context_diff.change_type == "improved"

    vision_diff = next(d for d in diffs if d.field == "vision")
    assert vision_diff.change_type == "gained"


def test_diff_unknown_model():
    diffs = diff_capabilities("unknown/a", "openai/gpt-4o")
    assert diffs == []


def test_diff_same_model():
    diffs = diff_capabilities("openai/gpt-4o", "openai/gpt-4o")
    for d in diffs:
        assert d.change_type == "same"


def test_diff_degraded_context():
    diffs = diff_capabilities("openai/gpt-4.1", "openai/gpt-4o")
    context_diff = next(d for d in diffs if d.field == "context_window")
    assert context_diff.change_type == "degraded"
