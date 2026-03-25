"""Tests for the scanner framework detector."""


from chowkidar.scanner.framework_detector import (
    detect_framework,
    find_prefixed_model_strings,
    strip_framework_prefix,
)


def test_strip_litellm_openai():
    bare, provider = strip_framework_prefix("openai/gpt-4o")
    assert bare == "gpt-4o"
    assert provider == "openai"


def test_strip_litellm_anthropic():
    bare, provider = strip_framework_prefix("anthropic/claude-3-sonnet-20240229")
    assert bare == "claude-3-sonnet-20240229"
    assert provider == "anthropic"


def test_strip_litellm_bedrock():
    bare, provider = strip_framework_prefix("bedrock/claude-3-sonnet")
    assert bare == "claude-3-sonnet"
    assert provider is not None


def test_strip_azure():
    bare, provider = strip_framework_prefix("azure/gpt-4o-eu")
    assert bare == "gpt-4o-eu"
    assert provider == "openai"


def test_strip_no_prefix():
    bare, provider = strip_framework_prefix("gpt-4o")
    assert bare == "gpt-4o"
    assert provider is None


def test_strip_google_vertex():
    bare, provider = strip_framework_prefix("vertex_ai/gemini-1.5-pro")
    assert bare == "gemini-1.5-pro"
    assert provider == "google"


def test_find_prefixed_in_text():
    text = 'model = "openai/gpt-4o-mini"\nbackup = "anthropic/claude-3-sonnet"'
    results = find_prefixed_model_strings(text)
    assert len(results) >= 2
    originals = [r[0] for r in results]
    assert "openai/gpt-4o-mini" in originals
    assert "anthropic/claude-3-sonnet" in originals


def test_detect_framework_litellm(tmp_path):
    req = tmp_path / "requirements.txt"
    req.write_text("flask==2.0\nlitellm==1.5\nrequests\n")
    assert detect_framework(tmp_path) == "litellm"


def test_detect_framework_openrouter(tmp_path):
    pkg = tmp_path / "package.json"
    pkg.write_text('{"dependencies": {"openrouter": "^1.0"}}')
    assert detect_framework(tmp_path) == "openrouter"


def test_detect_framework_none(tmp_path):
    req = tmp_path / "requirements.txt"
    req.write_text("flask==2.0\nrequests\n")
    assert detect_framework(tmp_path) is None
