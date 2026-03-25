"""Tests for SLM prompts and response parsing (no Ollama required)."""


from chowkidar.slm.prompts import format_extraction_prompt, parse_slm_response


class TestPromptFormatting:
    def test_format_prompt(self):
        prompt = format_extraction_prompt("OpenAI is deprecating gpt-3.5-turbo on 2025-09-01")
        assert "gpt-3.5-turbo" in prompt
        assert "YYYY-MM-DD" in prompt

    def test_truncates_long_text(self):
        long_text = "x" * 10000
        prompt = format_extraction_prompt(long_text)
        assert "truncated" in prompt


class TestResponseParsing:
    def test_valid_response(self):
        response = """[
            {
                "model": "gpt-3.5-turbo",
                "provider": "openai",
                "sunset_date": "2025-09-01",
                "replacement": "gpt-4o-mini",
                "confidence": "high"
            }
        ]"""
        result = parse_slm_response(response)
        assert result is not None
        assert len(result) == 1
        assert result[0]["model"] == "gpt-3.5-turbo"
        assert result[0]["sunset_date"] == "2025-09-01"

    def test_invalid_json(self):
        result = parse_slm_response("This is not JSON")
        assert result is None

    def test_empty_array(self):
        result = parse_slm_response("[]")
        assert result is None

    def test_invalid_date(self):
        response = '[{"model": "gpt-4", "sunset_date": "not-a-date", "provider": "openai"}]'
        result = parse_slm_response(response)
        assert result is None  # Invalid date causes rejection

    def test_future_date_limit(self):
        response = '[{"model": "gpt-4", "sunset_date": "2035-01-01", "provider": "openai"}]'
        result = parse_slm_response(response)
        assert result is None  # Year > 2030 rejected

    def test_extracts_json_from_text(self):
        json_part = '[{"model": "gpt-4o", "provider": "openai", "sunset_date": "2026-01-01"}]'
        response = f"Here is the result:\n{json_part}\nDone."
        result = parse_slm_response(response)
        assert result is not None
        assert result[0]["model"] == "gpt-4o"

    def test_normalizes_confidence(self):
        response = '[{"model": "gpt-4", "provider": "openai", "sunset_date": "2025-06-01", "confidence": "INVALID"}]'
        result = parse_slm_response(response)
        assert result is not None
        assert result[0]["confidence"] == "low"
