"""Unit tests for local advisor module and SLM model selector."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from chowkidar.advisor import (
    calculate_context_hash,
    get_fallback_recommendation,
    get_project_advisory,
    infer_purpose_heuristically,
)
from chowkidar.config import Config
from chowkidar.registry.db import ModelRecord, Registry
from chowkidar.slm.selector import select_best_slm


def test_infer_purpose_heuristically():
    assert infer_purpose_heuristically("MY_EMBEDDING_VAR", "openai/text-embedding-ada-002") == "embeddings generation"
    assert infer_purpose_heuristically("RERANK_MODEL_NAME", "cohere/rerank") == "document reranking"
    assert infer_purpose_heuristically("VISION_MODEL_VAR", "openai/gpt-4o") == "multimodal/vision analysis"
    assert infer_purpose_heuristically("SPEECH_TO_TEXT", "openai/whisper-1") == "audio speech-to-text/text-to-speech synthesis"
    assert infer_purpose_heuristically("MODERATION_VAR", "openai/text-moderation-latest") == "text safety moderation filter"
    assert infer_purpose_heuristically("FALLBACK_MODEL", "openai/gpt-4o-mini") == "secondary fallback chat completion"
    assert infer_purpose_heuristically("DEFAULT_LLM", "openai/gpt-4o") == "general-purpose chat/text completion"


def test_get_fallback_recommendation():
    # OpenAI
    rec, conf, reason = get_fallback_recommendation("openai/gpt-3.5-turbo-0301")
    assert rec == "openai/gpt-4o-mini"
    assert conf == "high"

    rec, conf, reason = get_fallback_recommendation("openai/gpt-4-0613")
    assert rec == "openai/gpt-4o"
    assert conf == "medium"

    # Anthropic
    rec, conf, reason = get_fallback_recommendation("anthropic/claude-2.1")
    assert rec == "anthropic/claude-3-haiku-20240307"
    assert conf == "medium"

    rec, conf, reason = get_fallback_recommendation("anthropic/claude-3-opus-20240229")
    assert rec == "anthropic/claude-3.5-sonnet-20241022"
    assert conf == "high"

    # Google
    rec, conf, reason = get_fallback_recommendation("google/gemini-1.0-pro")
    assert rec == "google/gemini-1.5-flash"
    assert conf == "high"

    # Other
    rec, conf, reason = get_fallback_recommendation("unrecognized/model")
    assert rec == "openai/gpt-4o-mini"
    assert conf == "low"


@patch("chowkidar.slm.selector.get_system_ram_gb")
@patch("chowkidar.slm.selector.get_free_disk_gb")
@patch("chowkidar.slm.selector.get_installed_ollama_models")
def test_select_best_slm(mock_installed, mock_disk, mock_ram, tmp_path):
    config = Config(tmp_path / "config.toml")

    # 1. Respect user explicitly configured non-default model
    config.set("slm_model", "custom-model:latest")
    model, reason = select_best_slm(config)
    assert model == "custom-model:latest"
    assert "User explicitly" in reason

    # Reset config for resource tests
    config.set("slm_model", "gemma3:1b")

    # 2. Match installed models first (reusing already installed)
    mock_installed.return_value = ["qwen2.5:1.5b", "some-other-model"]
    model, reason = select_best_slm(config)
    assert model == "qwen2.5:1.5b"
    assert "Reusing" in reason

    # 3. High system profile (RAM: 32GB, Disk: 50GB)
    mock_installed.return_value = []
    mock_ram.return_value = 32.0
    mock_disk.return_value = 50.0
    model, reason = select_best_slm(config)
    assert model == "qwen2.5:7b"
    assert "High system config" in reason

    # 4. Medium system profile (RAM: 16GB, Disk: 20GB)
    mock_ram.return_value = 16.0
    mock_disk.return_value = 20.0
    model, reason = select_best_slm(config)
    assert model == "gemma3:4b"
    assert "Medium system config" in reason

    # 5. Standard system profile (RAM: 8GB, Disk: 10GB)
    mock_ram.return_value = 8.0
    mock_disk.return_value = 10.0
    model, reason = select_best_slm(config)
    assert model == "gemma3:1b"
    assert "Standard system config" in reason

    # 6. Constrained resources profile (RAM: 4GB, Disk: 5GB)
    mock_ram.return_value = 4.0
    mock_disk.return_value = 5.0
    model, reason = select_best_slm(config)
    assert model == "qwen2.5:0.5b"
    assert "Constrained system resources" in reason


@patch("chowkidar.advisor._load_cache")
@patch("chowkidar.advisor._save_cache")
def test_get_project_advisory_cache_hit(mock_save, mock_load):
    mock_registry = MagicMock(spec=Registry)
    mock_registry.last_sync_time.return_value = "2026-05-21T00:00:00"
    
    models = [{"variable": "MODEL_VAR", "model": "gpt-3.5-turbo", "canonical": "openai/gpt-3.5-turbo", "file": ".env"}]
    ctx_hash = calculate_context_hash("/my/project", models, "2026-05-21T00:00:00")
    
    # Mock cache hit
    cached_advice = [{"variable": "MODEL_VAR", "model": "gpt-3.5-turbo", "purpose": "cached purpose"}]
    mock_load.return_value = {ctx_hash: cached_advice}

    result = get_project_advisory("/my/project", models, mock_registry)
    assert result == cached_advice
    mock_save.assert_not_called()


@patch("chowkidar.advisor._load_cache")
@patch("chowkidar.advisor._save_cache")
@patch("chowkidar.advisor.SLMClient")
def test_get_project_advisory_slm_enrichment(mock_slm_client_cls, mock_save, mock_load, tmp_path):
    mock_registry = MagicMock(spec=Registry)
    mock_registry.last_sync_time.return_value = "2026-05-21T00:00:00"
    
    # Registry mock get_model
    mock_record = ModelRecord(
        id="openai/gpt-3.5-turbo", provider="openai", aliases=[], sunset_date="2025-09-01",
        replacement="openai/gpt-4o-mini", replacement_confidence="high", breaking_changes=False,
        source_url=None, current_snapshot=None, privacy_tier="unknown",
        last_checked_at=None, created_at=None
    )
    mock_registry.get_model.return_value = mock_record
    mock_registry.is_pinned.return_value = False

    models = [{"variable": "MODEL_VAR", "model": "gpt-3.5-turbo", "canonical": "openai/gpt-3.5-turbo", "file": ".env"}]
    
    mock_load.return_value = {}  # Cache miss

    # Mock SLM client
    mock_client = MagicMock()
    mock_client.is_available.return_value = True
    mock_client.model = "gemma3:1b"
    mock_client.advise_replacements.return_value = {
        "advisory": [
            {
                "variable": "MODEL_VAR",
                "purpose": "highly customized chat completion",
                "recommended_model": "gpt-4o-mini",
                "confidence": "high",
                "reason": "Enriched reason",
                "risk": "Enriched risk"
            }
        ]
    }
    mock_slm_client_cls.return_value = mock_client

    config = Config(tmp_path / "config.toml")
    config.set("slm_enabled", True)

    result = get_project_advisory("/my/project", models, mock_registry, config)
    
    assert len(result) == 1
    assert result[0]["purpose"] == "highly customized chat completion"
    assert result[0]["reason"] == "Enriched reason"
    mock_client.unload_model.assert_called_once()
    mock_save.assert_called_once()
