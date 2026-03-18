"""Tests for the CI/CD gate module."""

import json
from pathlib import Path

import pytest

from chowkidar.gate import _format_output, run_gate, run_gate_staged
from chowkidar.registry.db import Registry


@pytest.fixture
def project_with_env(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text('MODEL_NAME="gpt-3.5-turbo"\nAPI_KEY="sk-123"\n')
    return tmp_path


@pytest.fixture
def registry_with_sunset(tmp_path):
    db_path = tmp_path / "test_gate.db"
    reg = Registry(db_path=db_path)
    reg.init_db()
    reg.upsert_model(
        model_id="openai/gpt-3.5-turbo",
        provider="openai",
        sunset_date="2024-01-01",
        replacement="openai/gpt-4o-mini",
    )
    return reg, db_path


def test_gate_passes_no_deprecated(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text('MODEL_NAME="gpt-4o"\n')
    exit_code, violations, _ = run_gate(tmp_path)
    assert exit_code == 0
    assert violations == []


def test_format_output_json(tmp_path):
    violations = [{"variable": "X", "model": "m", "sunset_date": "2024-01-01", "replacement": "r"}]
    result = _format_output(violations, "json", tmp_path, "block-sunset")
    data = json.loads(result)
    assert data["passed"] is False
    assert data["violation_count"] == 1


def test_format_output_github_actions():
    violations = [{"file": "a.env", "model": "m", "sunset_date": "2024-01-01", "replacement": "r"}]
    result = _format_output(violations, "github-actions", Path("."), "block-sunset")
    assert "::error" in result


def test_format_output_table_passed():
    result = _format_output([], "table", Path("."), "block-sunset")
    assert "PASSED" in result


def test_format_output_table_failed():
    violations = [{"variable": "X", "model": "m", "sunset_date": "2024-01-01", "replacement": "r"}]
    result = _format_output(violations, "table", Path("."), "block-sunset")
    assert "FAILED" in result


def test_gate_staged_no_files():
    exit_code, violations = run_gate_staged(Path("."), [])
    assert exit_code == 0
    assert violations == []


def test_gate_staged_nonexistent_files():
    exit_code, violations = run_gate_staged(Path("."), ["/nonexistent/file.env"])
    assert exit_code == 0
    assert violations == []
