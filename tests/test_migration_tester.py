"""Tests for the migration tester module."""

import json

from chowkidar.migration_tester import (
    _check_format,
    _simple_similarity,
    load_prompts,
)


def test_simple_similarity_identical():
    assert _simple_similarity("hello world", "hello world") == 1.0


def test_simple_similarity_partial():
    score = _simple_similarity("hello world foo", "hello world bar")
    assert 0.0 < score < 1.0


def test_simple_similarity_empty():
    assert _simple_similarity("", "") == 1.0


def test_simple_similarity_disjoint():
    score = _simple_similarity("aaa bbb", "ccc ddd")
    assert score == 0.0


def test_check_format_none():
    assert _check_format("anything", None) is True


def test_check_format_json_valid():
    assert _check_format('{"key": "value"}', "json") is True


def test_check_format_json_invalid():
    assert _check_format("not json", "json") is False


def test_check_format_other():
    assert _check_format("anything", "text") is True


def test_load_prompts(tmp_path):
    prompts_file = tmp_path / "prompts.jsonl"
    prompts_file.write_text(
        json.dumps({"prompt": "What is AI?", "system": "Be brief"}) + "\n"
        + json.dumps({"prompt": "Explain Python", "expected_format": "json"}) + "\n"
    )
    prompts = load_prompts(prompts_file)
    assert len(prompts) == 2
    assert prompts[0].prompt == "What is AI?"
    assert prompts[0].system == "Be brief"
    assert prompts[1].expected_format == "json"
