"""Tests for the dashboard module."""


import pytest

from chowkidar.dashboard import _build_dashboard_table
from chowkidar.registry.db import Registry


@pytest.fixture
def registry(tmp_path):
    db_path = tmp_path / "dashboard_test.db"
    reg = Registry(db_path=db_path)
    reg.init_db()
    return reg


def test_dashboard_no_projects(registry):
    table = _build_dashboard_table(registry, [])
    assert table.title is not None


def test_dashboard_with_valid_project(registry, tmp_path):
    project = tmp_path / "my_project"
    project.mkdir()
    env = project / ".env"
    env.write_text('MODEL="gpt-4o"\n')

    table = _build_dashboard_table(registry, [str(project)])
    assert table.row_count >= 2  # data row + total row


def test_dashboard_missing_project(registry):
    table = _build_dashboard_table(registry, ["/nonexistent/path"])
    assert table.row_count >= 2


def test_dashboard_with_deprecated(registry, tmp_path):
    project = tmp_path / "proj"
    project.mkdir()
    (project / ".env").write_text('M="gpt-3.5-turbo"\n')
    registry.upsert_model(
        model_id="openai/gpt-3.5-turbo",
        provider="openai",
        sunset_date="2024-01-01",
    )
    table = _build_dashboard_table(registry, [str(project)])
    assert table.row_count >= 2
