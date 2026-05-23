"""Tests for deployment signal detection and cloud adapter contracts."""

from chowkidar.cloud_adapters import CloudTarget, VercelAdapter
from chowkidar.config import Config
from chowkidar.deployment import detect_deployment


def test_detects_vercel_signal(tmp_path):
    (tmp_path / "vercel.json").write_text('{"version": 2}')

    assessment = detect_deployment(tmp_path)

    assert assessment.state in {"possible", "likely"}
    assert any(signal.adapter == "vercel" for signal in assessment.signals)


def test_detects_kubernetes_secret_signal(tmp_path):
    (tmp_path / "secret.yaml").write_text("kind: Secret\nmetadata:\n  name: app-secret\n")

    assessment = detect_deployment(tmp_path)

    assert assessment.state in {"possible", "likely"}
    assert any(signal.adapter == "kubernetes" for signal in assessment.signals)


def test_no_signals_is_none(tmp_path):
    assessment = detect_deployment(tmp_path)

    assert assessment.state == "none"
    assert assessment.confidence == 0.0


def test_cloud_adapter_blocks_without_provider_client(tmp_path):
    config = Config(tmp_path / "config.toml")
    config.set("cloud_vercel_enabled", True)
    adapter = VercelAdapter(config)

    result = adapter.dry_run(CloudTarget("vercel", "my-app"), "OPENAI_MODEL", "gpt-4o-mini")

    assert result.status == "blocked"
    assert "explicit credentials" in result.message
