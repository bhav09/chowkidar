"""Advisory engine that infers LLM usage purpose and recommends context-aware replacements."""

from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path
from typing import Any

from .config import CHOWKIDAR_HOME, Config
from .recommendations import build_recommendation
from .registry.db import Registry
from .slm.client import SLMClient

logger = logging.getLogger(__name__)

CACHE_PATH = CHOWKIDAR_HOME / "advisory_cache.json"


def _load_cache() -> dict[str, Any]:
    """Load persistent advisory cache."""
    if CACHE_PATH.exists():
        try:
            return json.loads(CACHE_PATH.read_text())
        except Exception:
            pass
    return {}


def _save_cache(cache: dict[str, Any]) -> None:
    """Save persistent advisory cache."""
    try:
        CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        CACHE_PATH.write_text(json.dumps(cache, indent=2))
    except Exception as e:
        logger.debug("Failed to save advisory cache: %s", e)


def calculate_context_hash(project_path: str, models: list[dict[str, str]], last_sync: str | None) -> str:
    """Calculate MD5 hash of inputs to determine cache validity."""
    # Convert models list to stable sorted representation
    sorted_models = sorted(models, key=lambda x: (x.get("variable", ""), x.get("file", ""), x.get("model", "")))
    serialized_models = json.dumps(sorted_models)
    data = f"{project_path}:{serialized_models}:{last_sync or ''}"
    return hashlib.md5(data.encode()).hexdigest()


def infer_purpose_heuristically(variable: str, model_id: str) -> str:
    """Infer LLM usage purpose using local deterministic heuristics."""
    v_lower = variable.lower()
    m_lower = model_id.lower()

    if "embed" in v_lower or "embedding" in v_lower or "ada" in m_lower:
        return "embeddings generation"
    if "rerank" in v_lower or "reranker" in v_lower:
        return "document reranking"
    if "vision" in v_lower or "img" in v_lower or "image" in v_lower or "visual" in v_lower or "vision" in m_lower:
        return "multimodal/vision analysis"
    if "audio" in v_lower or "speech" in v_lower or "tts" in v_lower or "whisper" in m_lower:
        return "audio speech-to-text/text-to-speech synthesis"
    if "moderation" in v_lower or "moderate" in v_lower or "moderation" in m_lower:
        return "text safety moderation filter"
    if "fallback" in v_lower or "secondary" in v_lower:
        return "secondary fallback chat completion"

    return "general-purpose chat/text completion"


def get_fallback_recommendation(canonical_id: str) -> tuple[str, str, str]:
    """Provide a reliable capability-matched fallback replacement and reason.

    Returns tuple of (recommended_model_id, confidence, reason).
    """
    provider = canonical_id.split("/")[0] if "/" in canonical_id else "other"
    model = canonical_id.split("/")[-1] if "/" in canonical_id else canonical_id

    # Fallbacks based on provider and size
    if provider == "openai":
        if "gpt-3.5" in model:
            return (
                "openai/gpt-4o-mini",
                "high",
                "GPT-4o-mini is OpenAI's direct fast, cheap successor to GPT-3.5-turbo with 128k context."
            )
        if "gpt-4-turbo" in model or "preview" in model:
            return (
                "openai/gpt-4o",
                "medium",
                "GPT-4o is OpenAI's flagship fast and highly capable successor to GPT-4-turbo."
            )
        if "gpt-4" in model:
            return (
                "openai/gpt-4o",
                "medium",
                "GPT-4o is highly cost-optimized, significantly faster, and more capable than legacy GPT-4."
            )
        if "ada" in model:
            return (
                "openai/text-embedding-3-small",
                "high",
                "Text-embedding-3-small is cheaper, smaller, and higher performing."
            )
        return "openai/gpt-4o-mini", "low", "Recommended default lightweight and cost-effective successor."

    elif provider == "anthropic":
        if "claude-2" in model:
            return (
                "anthropic/claude-3-haiku-20240307",
                "medium",
                "Claude 3 Haiku is exponentially faster and significantly cheaper than Claude 2."
            )
        if "opus" in model:
            return (
                "anthropic/claude-3.5-sonnet-20241022",
                "high",
                "Claude 3.5 Sonnet beats legacy Claude 3 Opus on most evals at a fraction of the cost."
            )
        if "sonnet" in model:
            return (
                "anthropic/claude-3.5-sonnet-20241022",
                "high",
                "Claude 3.5 Sonnet is Anthropic's flagship recommended state-of-the-art model."
            )
        return (
            "anthropic/claude-3-haiku-20240307",
            "low",
            "Recommended default highly cost-efficient Anthropic successor."
        )

    elif provider == "google":
        if "gemini-1.0" in model:
            return (
                "google/gemini-1.5-flash",
                "high",
                "Gemini 1.5 Flash provides massive 1M token context window and 80%+ lower costs."
            )
        if "pro" in model:
            return (
                "google/gemini-1.5-pro",
                "high",
                "Gemini 1.5 Pro offers massive context, multi-modal capabilities, and much faster inference."
            )
        return "google/gemini-1.5-flash", "low", "Recommended default high-performance lightweight Google successor."

    elif provider == "mistral":
        if "large" in model:
            return (
                "mistral/mistral-large-latest",
                "high",
                "Mistral Large Latest is Mistral's premier flagship successor."
            )
        return (
            "mistral/mistral-small-latest",
            "medium",
            "Mistral Small Latest is Mistral's highly cost-optimized alternative."
        )

    return "openai/gpt-4o-mini", "low", "Generic highly-capable fallback model suggestion."


def generate_local_advice(models: list[dict[str, str]], registry: Registry) -> list[dict[str, Any]]:
    """Generate high-quality advice purely using local database and heuristics."""
    advice_list = []
    for m in models:
        canonical = m["canonical"]
        variable = m["variable"]
        file_path = m["file"]
        file_name = Path(file_path).name

        purpose = infer_purpose_heuristically(variable, canonical)

        record = registry.get_model(canonical)
        fallback = None if record and record.sunset_date and record.replacement else get_fallback_recommendation(canonical)
        recommendation = build_recommendation(canonical, record, fallback)
        rec_model = recommendation.recommended_model
        confidence = recommendation.confidence
        reason = recommendation.reason
        if recommendation.cost_summary:
            reason = f"{reason} Migration {recommendation.cost_summary}."
        risk_parts = [recommendation.risk]
        risk_parts.extend(recommendation.commercial_risks)
        risk_parts.extend(recommendation.future_risks)
        risk_parts.extend(recommendation.privacy_risks)
        risk = " ".join(risk_parts)

        advice_list.append({
            "variable": variable,
            "file": file_name,
            "model": m["model"],
            "purpose": purpose,
            "recommended_model": rec_model.split("/")[-1] if rec_model and "/" in rec_model else rec_model,
            "recommended_model_canonical": rec_model,
            "confidence": confidence,
            "reason": reason,
            "risk": risk,
            "source_type": m.get("source_type", "env"),
            "manual_review_required": recommendation.manual_review_required,
            "auto_write_allowed": recommendation.auto_write_allowed,
            "capability_diffs": recommendation.capability_diffs,
            "commercial_risks": recommendation.commercial_risks,
            "future_risks": recommendation.future_risks,
            "privacy_risks": recommendation.privacy_risks,
        })
    return advice_list


def get_project_advisory(
    project_path: str,
    models: list[dict[str, str]],
    registry: Registry,
    config: Config | None = None,
) -> list[dict[str, Any]]:
    """Orchestrate advisory generation. Uses cache, falls back to Gemma/local SLM if enabled,

    and defaults to deterministic local heuristics.
    """
    config = config or Config()
    last_sync = registry.last_sync_time()
    context_hash = calculate_context_hash(project_path, models, last_sync)

    # 1. Check persistent cache
    cache = _load_cache()
    if context_hash in cache:
        logger.debug("Advisory cache hit for project '%s'", project_path)
        return cache[context_hash]

    logger.debug("Advisory cache miss. Generating new recommendations...")

    # Generate reliable deterministic baseline
    local_advice = generate_local_advice(models, registry)

    # 2. If SLM is enabled, try to enrich with local usage-aware Gemma/Ollama reasoning
    if config.get("slm_enabled", False):
        client = SLMClient(config)
        if client.is_available():
            logger.info("Local SLM is available. Enriching recommendations via '%s'...", client.model)

            # Prepare sanitized context for SLM input
            sanitized_models = []
            for m in local_advice:
                sanitized_models.append({
                    "variable": m["variable"],
                    "file": m["file"],
                    "model": m["model"],
                    "source_type": m.get("source_type", "env"),
                    "proposed_fallback": m["recommended_model"],
                    "proposed_reason": m["reason"]
                })

            slm_input = {
                "project_folder": Path(project_path).name,
                "findings": sanitized_models
            }

            slm_resp = client.advise_replacements(slm_input)

            # Explicitly unload the model to preserve memory
            client.unload_model()

            if slm_resp and "advisory" in slm_resp:
                enriched_list = []
                slm_advisory = {
                    adv.get("variable", ""): adv
                    for adv in slm_resp["advisory"]
                    if isinstance(adv, dict)
                }

                for local_item in local_advice:
                    var = local_item["variable"]
                    if var in slm_advisory:
                        slm_item = slm_advisory[var]
                        # Merge SLM recommendations carefully, validating values
                        enriched_item = dict(local_item)
                        if slm_item.get("purpose"):
                            enriched_item["purpose"] = slm_item["purpose"]
                        # The local SLM may enrich rationale, but replacement IDs stay on
                        # the deterministic, capability-validated baseline.
                        if slm_item.get("confidence") in ("high", "medium", "low"):
                            enriched_item["confidence"] = slm_item["confidence"]
                        if slm_item.get("reason"):
                            enriched_item["reason"] = slm_item["reason"]
                        if slm_item.get("risk"):
                            enriched_item["risk"] = slm_item["risk"]
                        enriched_list.append(enriched_item)
                    else:
                        enriched_list.append(local_item)

                logger.info("Successfully enriched advisory using local SLM.")
                # Save to cache
                cache[context_hash] = enriched_list
                _save_cache(cache)
                return enriched_list
            else:
                logger.warning(
                    "SLM advisory returned invalid format or failed. "
                    "Falling back to robust deterministic advice."
                )
        else:
            logger.debug("Local SLM '%s' is not pulled or Ollama is offline. Using local heuristics.", client.model)
    else:
        logger.debug("Local SLM is disabled. Using local heuristics.")

    # Save to cache and return local baseline
    cache[context_hash] = local_advice
    _save_cache(cache)
    return local_advice
