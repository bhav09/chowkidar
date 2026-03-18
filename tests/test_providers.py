"""Tests for provider adapters."""

import pytest

from chowkidar.providers.anthropic_provider import KNOWN_ANTHROPIC_MODELS, AnthropicProvider
from chowkidar.providers.google_provider import KNOWN_GOOGLE_MODELS, GoogleProvider
from chowkidar.providers.mistral_provider import KNOWN_MISTRAL_MODELS, MistralProvider
from chowkidar.providers.openai_provider import KNOWN_OPENAI_MODELS, OpenAIProvider


class TestKnownModels:
    def test_openai_known_models_format(self):
        for m in KNOWN_OPENAI_MODELS:
            assert "id" in m
            assert "sunset" in m
            assert "replacement" in m

    def test_anthropic_known_models_format(self):
        for m in KNOWN_ANTHROPIC_MODELS:
            assert "id" in m
            assert "sunset" in m

    def test_google_known_models_format(self):
        for m in KNOWN_GOOGLE_MODELS:
            assert "id" in m
            assert "sunset" in m

    def test_mistral_known_models_format(self):
        for m in KNOWN_MISTRAL_MODELS:
            assert "id" in m
            assert "sunset" in m


@pytest.mark.asyncio
class TestProviderFetchFallback:
    """Test that providers return known models even without network."""

    async def test_openai_fallback(self):
        provider = OpenAIProvider()
        deprecations = await provider.fetch_deprecations()
        assert len(deprecations) > 0
        model_ids = {d.model_id for d in deprecations}
        assert any("gpt-3.5" in m for m in model_ids)

    async def test_anthropic_fallback(self):
        provider = AnthropicProvider()
        deprecations = await provider.fetch_deprecations()
        assert len(deprecations) > 0

    async def test_google_fallback(self):
        provider = GoogleProvider()
        deprecations = await provider.fetch_deprecations()
        assert len(deprecations) > 0

    async def test_mistral_fallback(self):
        provider = MistralProvider()
        deprecations = await provider.fetch_deprecations()
        assert len(deprecations) > 0
