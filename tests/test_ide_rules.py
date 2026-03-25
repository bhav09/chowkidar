"""Tests for IDE rules writer and templates."""


import pytest


@pytest.fixture
def sample_deprecations():
    return [
        {
            "variable": "LLM_MODEL",
            "file": "/project/.env",
            "model": "gpt-3.5-turbo",
            "canonical": "openai/gpt-3.5-turbo",
            "sunset_date": "2025-09-01",
            "replacement": "openai/gpt-4o-mini",
            "replacement_confidence": "high",
            "breaking_changes": False,
            "days_until": 15,
        },
        {
            "variable": "ANTHROPIC_MODEL",
            "file": "/project/.env",
            "model": "claude-2.1",
            "canonical": "anthropic/claude-2.1",
            "sunset_date": "2025-02-24",
            "replacement": "anthropic/claude-3-sonnet-20240229",
            "replacement_confidence": "high",
            "breaking_changes": False,
            "days_until": -100,
        },
    ]


class TestCursorTemplate:
    def test_generate(self, sample_deprecations):
        from chowkidar.ide.templates.cursor import generate_cursor_rules

        content = generate_cursor_rules(sample_deprecations)
        assert "alwaysApply: false" in content
        assert "gpt-3.5-turbo" in content
        assert "claude-2.1" in content
        assert "Chowkidar" in content

    def test_contains_sunset_info(self, sample_deprecations):
        from chowkidar.ide.templates.cursor import generate_cursor_rules

        content = generate_cursor_rules(sample_deprecations)
        assert "PASSED" in content  # claude-2.1 is past sunset


class TestClaudeTemplate:
    def test_generate(self, sample_deprecations):
        from chowkidar.ide.templates.claude_code import generate_claude_rules

        content = generate_claude_rules(sample_deprecations)
        assert "gpt-3.5-turbo" in content
        assert "Chowkidar" in content


class TestCopilotTemplate:
    def test_generate_and_inject(self, sample_deprecations):
        from chowkidar.ide.templates.copilot import (
            generate_copilot_section,
            inject_into_copilot_file,
        )

        section = generate_copilot_section(sample_deprecations)
        assert "<!-- chowkidar:start -->" in section
        assert "<!-- chowkidar:end -->" in section

        existing = "# My Project\n\nSome instructions here.\n"
        result = inject_into_copilot_file(existing, section)
        assert "# My Project" in result
        assert "chowkidar:start" in result

    def test_replace_existing_section(self, sample_deprecations):
        from chowkidar.ide.templates.copilot import (
            generate_copilot_section,
            inject_into_copilot_file,
        )

        section = generate_copilot_section(sample_deprecations)
        content_with_old = (
            "# My Project\n\n"
            "<!-- chowkidar:start -->\nold content\n<!-- chowkidar:end -->\n\n"
            "Other stuff\n"
        )
        result = inject_into_copilot_file(content_with_old, section)
        assert "old content" not in result
        assert "gpt-3.5-turbo" in result
        assert "Other stuff" in result


class TestDetector:
    def test_detect_editors(self, tmp_path):
        from chowkidar.ide.detector import detect_editors

        (tmp_path / ".cursor").mkdir()
        (tmp_path / ".github").mkdir()
        editors = detect_editors(tmp_path)
        assert "cursor" in editors
        assert "copilot" in editors

    def test_no_editors(self, tmp_path):
        from chowkidar.ide.detector import detect_editors

        detect_editors(tmp_path)
        # Falls back to checking home dir; may or may not find editors


class TestRulesWriter:
    def test_write_and_clean(self, tmp_path, sample_deprecations):
        from chowkidar.config import Config
        from chowkidar.ide.rules_writer import clean_rules, write_rules_for_project

        (tmp_path / ".cursor").mkdir()
        config = Config(tmp_path / "test_config.toml")
        config.set("write_rules", True)
        config.set("gitignore_rules", False)

        written = write_rules_for_project(tmp_path, sample_deprecations, config)
        assert len(written) > 0

        cursor_rules = tmp_path / ".cursor" / "rules" / "chowkidar-alerts.mdc"
        assert cursor_rules.exists()
        content = cursor_rules.read_text()
        assert "gpt-3.5-turbo" in content

        removed = clean_rules(tmp_path)
        assert len(removed) > 0
        assert not cursor_rules.exists()
