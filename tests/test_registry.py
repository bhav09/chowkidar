"""Tests for the registry module."""


import pytest

from chowkidar.registry.db import Registry


@pytest.fixture
def registry(tmp_path):
    db_path = tmp_path / "test_registry.db"
    reg = Registry(db_path)
    reg.init_db()
    yield reg
    reg.close()


class TestModels:
    def test_upsert_and_get(self, registry):
        registry.upsert_model(
            model_id="openai/gpt-3.5-turbo",
            provider="openai",
            sunset_date="2025-09-01",
            replacement="openai/gpt-4o-mini",
            replacement_confidence="high",
        )
        record = registry.get_model("openai/gpt-3.5-turbo")
        assert record is not None
        assert record.sunset_date == "2025-09-01"
        assert record.replacement == "openai/gpt-4o-mini"

    def test_get_deprecated(self, registry):
        registry.upsert_model("openai/gpt-3.5-turbo", "openai", sunset_date="2025-09-01")
        registry.upsert_model("openai/gpt-4o", "openai", sunset_date=None)

        deprecated = registry.get_deprecated_models()
        assert len(deprecated) == 1
        assert deprecated[0].id == "openai/gpt-3.5-turbo"

    def test_upsert_preserves_existing(self, registry):
        registry.upsert_model("openai/gpt-4o", "openai", sunset_date="2026-01-01")
        registry.upsert_model("openai/gpt-4o", "openai", sunset_date=None, replacement="gpt-4.1")
        record = registry.get_model("openai/gpt-4o")
        assert record.sunset_date == "2026-01-01"  # COALESCE keeps existing
        assert record.replacement == "gpt-4.1"


class TestPinning:
    def test_pin_unpin(self, registry):
        registry.pin_model("openai/gpt-3.5-turbo", "budget constraint")
        assert registry.is_pinned("openai/gpt-3.5-turbo")

        registry.unpin_model("openai/gpt-3.5-turbo")
        assert not registry.is_pinned("openai/gpt-3.5-turbo")

    def test_get_pinned(self, registry):
        registry.pin_model("openai/gpt-3.5-turbo", "testing")
        pinned = registry.get_pinned_models()
        assert len(pinned) == 1
        assert pinned[0] == ("openai/gpt-3.5-turbo", "testing")


class TestWatchedProjects:
    def test_watch_unwatch(self, registry):
        registry.watch_project("/home/user/project1")
        projects = registry.get_watched_projects()
        assert "/home/user/project1" in projects

        registry.unwatch_project("/home/user/project1")
        projects = registry.get_watched_projects()
        assert "/home/user/project1" not in projects


class TestNotifications:
    def test_log_and_check(self, registry):
        assert not registry.is_recently_notified("/proj", "openai/gpt-3.5-turbo", "30d")
        registry.log_notification("/proj", "openai/gpt-3.5-turbo", "30d")
        assert registry.is_recently_notified("/proj", "openai/gpt-3.5-turbo", "30d")

    def test_snooze(self, registry):
        assert not registry.is_snoozed("openai/gpt-3.5-turbo")
        registry.set_snooze("openai/gpt-3.5-turbo", 7)
        assert registry.is_snoozed("openai/gpt-3.5-turbo")


class TestScanResults:
    def test_save_and_get(self, registry):
        entries = [
            {"file": "/proj/.env", "variable": "LLM_MODEL", "model": "gpt-3.5-turbo",
             "canonical": "openai/gpt-3.5-turbo", "source_type": "env"},
        ]
        registry.save_scan_results("/proj", entries)
        results = registry.get_scan_results("/proj")
        assert len(results) == 1
        assert results[0].model_value == "gpt-3.5-turbo"
