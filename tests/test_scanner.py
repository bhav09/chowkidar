"""Tests for the scanner module."""

from pathlib import Path

FIXTURES = Path(__file__).parent / "fixtures"


class TestPatterns:
    def test_openai_models(self):
        from chowkidar.scanner.patterns import find_model_strings, identify_provider

        models = ["gpt-4o", "gpt-4o-mini", "gpt-3.5-turbo", "gpt-4-turbo-preview",
                  "gpt-4.1", "gpt-4.1-mini", "o1", "o1-mini", "o3-mini"]
        for model in models:
            matches = find_model_strings(model)
            assert matches, f"Should match: {model}"
            assert identify_provider(model) == "openai", f"Should identify as openai: {model}"

    def test_anthropic_models(self):
        from chowkidar.scanner.patterns import find_model_strings, identify_provider

        models = ["claude-3-sonnet-20240229", "claude-3.5-sonnet-20241022",
                  "claude-2.1", "claude-sonnet-4-20250514", "claude-3-haiku-20240307"]
        for model in models:
            matches = find_model_strings(model)
            assert matches, f"Should match: {model}"
            assert identify_provider(model) == "anthropic", f"Should identify as anthropic: {model}"

    def test_google_models(self):
        from chowkidar.scanner.patterns import find_model_strings, identify_provider

        models = ["gemini-1.5-pro", "gemini-2.0-flash", "gemini-1.0-pro"]
        for model in models:
            matches = find_model_strings(model)
            assert matches, f"Should match: {model}"
            assert identify_provider(model) == "google", f"Should identify as google: {model}"

    def test_mistral_models(self):
        from chowkidar.scanner.patterns import find_model_strings, identify_provider

        models = ["mistral-large-latest", "mistral-small-latest", "codestral-latest"]
        for model in models:
            matches = find_model_strings(model)
            assert matches, f"Should match: {model}"
            assert identify_provider(model) == "mistral", f"Should identify as mistral: {model}"

    def test_non_model_strings(self):
        from chowkidar.scanner.patterns import find_model_strings

        non_models = ["hello-world", "my-app-v2", "postgres://localhost", "true", "8080"]
        for text in non_models:
            matches = find_model_strings(text)
            assert not matches, f"Should not match: {text}"

    def test_normalize_model_id(self):
        from chowkidar.scanner.patterns import normalize_model_id

        assert normalize_model_id("gpt-4o") == "openai/gpt-4o"
        assert normalize_model_id("claude-3-sonnet-20240229") == "anthropic/claude-3-sonnet-20240229"
        assert normalize_model_id("gemini-1.5-pro") == "google/gemini-1.5-pro"

    def test_is_model_variable_name(self):
        from chowkidar.scanner.patterns import is_model_variable_name

        assert is_model_variable_name("LLM_MODEL")
        assert is_model_variable_name("OPENAI_MODEL")
        assert is_model_variable_name("AI_MODEL_NAME")
        assert not is_model_variable_name("DATABASE_URL")
        assert not is_model_variable_name("PORT")


class TestEnvParser:
    def test_parse_sample_env(self):
        from chowkidar.scanner.env_parser import parse_env_file

        entries = parse_env_file(FIXTURES / "sample.env")
        model_values = {e.model_value for e in entries}
        assert "gpt-3.5-turbo" in model_values
        assert "gpt-4o-mini" in model_values
        assert "claude-3-sonnet-20240229" in model_values
        assert "text-embedding-ada-002" in model_values

    def test_no_api_keys_extracted(self):
        from chowkidar.scanner.env_parser import parse_env_file

        entries = parse_env_file(FIXTURES / "sample.env")
        variables = {e.variable_name for e in entries}
        assert "OPENAI_API_KEY" not in variables

    def test_discover_env_files(self):
        from chowkidar.scanner.env_parser import discover_env_files

        files = discover_env_files(FIXTURES)
        env_names = {f.name for f in files}
        assert "sample.env" not in env_names  # named sample.env, not .env


class TestConfigParser:
    def test_parse_yaml(self):
        from chowkidar.scanner.config_parser import parse_yaml_file

        entries = parse_yaml_file(FIXTURES / "sample_config.yaml")
        models = {e.model_value for e in entries}
        assert "gpt-4-turbo-preview" in models
        assert "gpt-3.5-turbo" in models
        assert "claude-2.1" in models

    def test_parse_json(self):
        from chowkidar.scanner.config_parser import parse_json_file

        entries = parse_json_file(FIXTURES / "sample_config.json")
        models = {e.model_value for e in entries}
        assert "gpt-4o" in models
        assert "claude-3-haiku-20240307" in models

    def test_key_paths(self):
        from chowkidar.scanner.config_parser import parse_yaml_file

        entries = parse_yaml_file(FIXTURES / "sample_config.yaml")
        key_paths = {e.key_path for e in entries}
        assert "llm.model" in key_paths
        assert "anthropic.model" in key_paths


class TestScanDirectory:
    def test_scan_fixtures(self):
        from chowkidar.scanner import scan_directory

        result = scan_directory(FIXTURES)
        assert result.total_count > 0
        assert len(result.unique_models) > 0
