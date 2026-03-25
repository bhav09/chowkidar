"""Tests for the env writer/updater module."""


import pytest

from chowkidar.updater.env_writer import rollback_env, update_env_value


@pytest.fixture
def env_file(tmp_path):
    content = """DATABASE_URL=postgres://localhost/mydb
LLM_MODEL=gpt-3.5-turbo
ANTHROPIC_MODEL="claude-2.1"
API_KEY=sk-test-123
"""
    env_path = tmp_path / ".env"
    env_path.write_text(content)
    return env_path


class TestUpdateEnvValue:
    def test_basic_update(self, env_file):
        result = update_env_value(env_file, "LLM_MODEL", "gpt-4o-mini")
        assert result["status"] == "updated"
        assert result["old_value"] == "gpt-3.5-turbo"
        assert result["new_value"] == "gpt-4o-mini"

        content = env_file.read_text()
        assert "LLM_MODEL=gpt-4o-mini" in content
        assert "gpt-3.5-turbo" not in content

    def test_preserves_quotes(self, env_file):
        result = update_env_value(env_file, "ANTHROPIC_MODEL", "claude-3-sonnet-20240229")
        assert result["status"] == "updated"

        content = env_file.read_text()
        assert 'ANTHROPIC_MODEL="claude-3-sonnet-20240229"' in content

    def test_creates_backup(self, env_file):
        update_env_value(env_file, "LLM_MODEL", "gpt-4o-mini")
        backup = env_file.parent / ".env.chowkidar.bak"
        assert backup.exists()
        assert "gpt-3.5-turbo" in backup.read_text()

    def test_dry_run(self, env_file):
        result = update_env_value(env_file, "LLM_MODEL", "gpt-4o-mini", dry_run=True)
        assert result["status"] == "dry_run"
        assert "gpt-3.5-turbo" in env_file.read_text()

    def test_no_change_needed(self, env_file):
        result = update_env_value(env_file, "LLM_MODEL", "gpt-3.5-turbo")
        assert result["status"] == "no_change"

    def test_variable_not_found(self, env_file):
        result = update_env_value(env_file, "NONEXISTENT", "value")
        assert result["status"] == "error"

    def test_file_not_found(self, tmp_path):
        result = update_env_value(tmp_path / "missing.env", "KEY", "value")
        assert result["status"] == "error"

    def test_other_vars_preserved(self, env_file):
        update_env_value(env_file, "LLM_MODEL", "gpt-4o-mini")
        content = env_file.read_text()
        assert "DATABASE_URL=postgres://localhost/mydb" in content
        assert "API_KEY=sk-test-123" in content


class TestRollback:
    def test_rollback(self, env_file):
        update_env_value(env_file, "LLM_MODEL", "gpt-4o-mini")
        assert "gpt-4o-mini" in env_file.read_text()

        result = rollback_env(env_file)
        assert result["status"] == "restored"
        assert "gpt-3.5-turbo" in env_file.read_text()

    def test_rollback_no_backup(self, env_file):
        result = rollback_env(env_file)
        assert result["status"] == "error"
