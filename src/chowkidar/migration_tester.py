"""Shadow test runner — compare model outputs before migrating."""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class PromptCase:
    prompt: str
    system: str | None = None
    expected_format: str | None = None


TestPrompt = PromptCase


@dataclass
class ComparisonResult:
    prompt: str
    old_response: str
    new_response: str
    old_latency_ms: float
    new_latency_ms: float
    similarity_score: float
    format_match: bool


TestResult = ComparisonResult


@dataclass
class MigrationReport:
    old_model: str
    new_model: str
    results: list[ComparisonResult] = field(default_factory=list)
    avg_similarity: float = 0.0
    avg_old_latency: float = 0.0
    avg_new_latency: float = 0.0
    confidence: str = "unknown"


def load_prompts(file_path: Path) -> list[PromptCase]:
    """Load test prompts from a JSONL file."""
    prompts: list[PromptCase] = []
    with open(file_path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            data = json.loads(line)
            prompts.append(PromptCase(
                prompt=data["prompt"],
                system=data.get("system"),
                expected_format=data.get("expected_format"),
            ))
    return prompts


def _call_openai(model: str, prompt: str, system: str | None = None) -> tuple[str, float]:
    """Call OpenAI-compatible API. Requires OPENAI_API_KEY env var."""
    import httpx

    api_key = os.environ.get("OPENAI_API_KEY", "")
    base_url = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    start = time.monotonic()
    resp = httpx.post(
        f"{base_url}/chat/completions",
        json={"model": model, "messages": messages, "max_tokens": 1024},
        headers={"Authorization": f"Bearer {api_key}"},
        timeout=60,
    )
    latency_ms = (time.monotonic() - start) * 1000
    resp.raise_for_status()
    content = resp.json()["choices"][0]["message"]["content"]
    return content, latency_ms


def _simple_similarity(a: str, b: str) -> float:
    """Jaccard similarity on word sets — a rough approximation."""
    words_a = set(a.lower().split())
    words_b = set(b.lower().split())
    if not words_a and not words_b:
        return 1.0
    intersection = words_a & words_b
    union = words_a | words_b
    return len(intersection) / len(union) if union else 1.0


def _check_format(response: str, expected_format: str | None) -> bool:
    if expected_format is None:
        return True
    if expected_format == "json":
        try:
            json.loads(response)
            return True
        except json.JSONDecodeError:
            return False
    return True


def run_migration_test(
    old_model: str,
    new_model: str,
    prompts: list[PromptCase],
) -> MigrationReport:
    """Run the same prompts through both models and compare."""
    report = MigrationReport(old_model=old_model, new_model=new_model)

    for tp in prompts:
        try:
            old_resp, old_lat = _call_openai(old_model, tp.prompt, tp.system)
            new_resp, new_lat = _call_openai(new_model, tp.prompt, tp.system)

            similarity = _simple_similarity(old_resp, new_resp)
            fmt_match = _check_format(new_resp, tp.expected_format)

            report.results.append(TestResult(
                prompt=tp.prompt[:100],
                old_response=old_resp[:200],
                new_response=new_resp[:200],
                old_latency_ms=old_lat,
                new_latency_ms=new_lat,
                similarity_score=similarity,
                format_match=fmt_match,
            ))
        except Exception:
            report.results.append(TestResult(
                prompt=tp.prompt[:100],
                old_response="ERROR",
                new_response="ERROR",
                old_latency_ms=0,
                new_latency_ms=0,
                similarity_score=0.0,
                format_match=False,
            ))

    if report.results:
        report.avg_similarity = sum(r.similarity_score for r in report.results) / len(report.results)
        report.avg_old_latency = sum(r.old_latency_ms for r in report.results) / len(report.results)
        report.avg_new_latency = sum(r.new_latency_ms for r in report.results) / len(report.results)

        if report.avg_similarity > 0.8 and all(r.format_match for r in report.results):
            report.confidence = "high"
        elif report.avg_similarity > 0.5:
            report.confidence = "medium"
        else:
            report.confidence = "low"

    return report
