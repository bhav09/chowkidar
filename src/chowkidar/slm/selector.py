"""Adaptive local SLM selector based on system hardware resources and installed models."""

from __future__ import annotations

import logging
import platform
import shutil
import subprocess
from pathlib import Path

from ..config import Config

logger = logging.getLogger(__name__)

# Configured list of supported model candidates in order of preference per tier
# RAM thresholds in GB:
# Tiny: < 6GB RAM -> Qwen 0.5B (approx 390MB)
# Small: 6GB - 12GB RAM -> Gemma 1B (approx 815MB) or Qwen 1.5B
# Medium: 12GB - 24GB RAM -> Gemma 4B (approx 2.6GB) or Qwen 3B
# Large: > 24GB RAM -> Qwen 7B (approx 4.7GB) or Gemma 8B (approx 5GB)
SLM_TIERS = {
    "tiny": {
        "models": ["qwen2.5:0.5b", "qwen2.5:1.5b", "gemma3:1b"],
        "min_ram_gb": 0.0,
        "required_disk_gb": 1.0,
    },
    "small": {
        "models": ["gemma3:1b", "qwen2.5:1.5b", "qwen2.5:0.5b"],
        "min_ram_gb": 6.0,
        "required_disk_gb": 1.8,
    },
    "medium": {
        "models": ["gemma3:4b", "qwen2.5:3b", "gemma3:1b"],
        "min_ram_gb": 12.0,
        "required_disk_gb": 4.5,
    },
    "large": {
        "models": ["qwen2.5:7b", "gemma3:4b", "gemma3:1b"],
        "min_ram_gb": 24.0,
        "required_disk_gb": 8.0,
    },
}


def get_system_ram_gb() -> float:
    """Detect total system RAM in GB. Returns 8.0 as fallback if detection fails."""
    system = platform.system()
    try:
        if system == "Darwin":
            # macOS
            res = subprocess.run(
                ["sysctl", "-n", "hw.memsize"],
                capture_output=True, text=True, timeout=5
            )
            if res.returncode == 0:
                return int(res.stdout.strip()) / (1024 ** 3)
        elif system == "Linux":
            # Linux meminfo
            mem_path = Path("/proc/meminfo")
            if mem_path.exists():
                for line in mem_path.read_text().splitlines():
                    if line.startswith("MemTotal:"):
                        parts = line.split()
                        if len(parts) >= 2:
                            return int(parts[1]) / (1024 ** 2)  # kb to GB
        elif system == "Windows":
            # Windows wmic / powershell
            res = subprocess.run(
                [
                    "powershell",
                    "-Command",
                    "(Get-CimInstance Win32_PhysicalMemory | Measure-Object -Property Capacity -Sum).Sum"
                ],
                capture_output=True, text=True, timeout=5
            )
            if res.returncode == 0 and res.stdout.strip():
                return int(res.stdout.strip()) / (1024 ** 3)
    except Exception as e:
        logger.debug("Failed to detect system RAM: %s", e)

    return 8.0  # Safe default fallback


def get_free_disk_gb() -> float:
    """Return free disk space in GB for CHOWKIDAR_HOME's drive."""
    try:
        usage = shutil.disk_usage(Path.home())
        return usage.free / (1024 ** 3)
    except Exception as e:
        logger.debug("Failed to check disk usage: %s", e)
        return 10.0  # Assume enough space as safe fallback


def get_installed_ollama_models() -> list[str]:
    """Retrieve list of currently installed Ollama models."""
    try:
        # Avoid forcing dependencies or SDK if not loaded yet; use command line or SDK if possible
        from .client import _get_ollama
        ollama = _get_ollama()
        if ollama is not None:
            models = ollama.list()
            return [m.model for m in models.models] if models.models else []
    except Exception as e:
        logger.debug("Ollama Python SDK list call failed: %s", e)

    # CLI fallback
    if shutil.which("ollama") is not None:
        try:
            res = subprocess.run(
                ["ollama", "list"],
                capture_output=True, text=True, timeout=5
            )
            if res.returncode == 0:
                models = []
                for line in res.stdout.splitlines()[1:]:  # skip header
                    if line.strip():
                        models.append(line.split()[0])
                return models
        except Exception:
            pass

    return []


def select_best_slm(config: Config | None = None) -> tuple[str, str]:
    """Select the best local SLM based on system resources and pre-installed models.

    Returns tuple of (model_name, decision_reason).
    """
    config = config or Config()

    # Check if a model is explicitly pinned/configured by the user
    user_configured = config.get("slm_model")
    if user_configured and user_configured != "gemma3:1b":
        # If the user explicitly set some other model, respect it
        return user_configured, f"User explicitly configured model '{user_configured}'"

    ram_gb = get_system_ram_gb()
    free_disk = get_free_disk_gb()
    installed = get_installed_ollama_models()

    logger.debug("System RAM: %.1f GB, Free Disk: %.1f GB", ram_gb, free_disk)
    logger.debug("Installed Ollama models: %s", installed)

    # 1. Prefer pre-installed models that we know work well
    # Group all candidate models across all tiers
    all_candidates = []
    for tier in ["large", "medium", "small", "tiny"]:
        for m in SLM_TIERS[tier]["models"]:
            if m not in all_candidates:
                all_candidates.append(m)

    for candidate in all_candidates:
        # Check if the exact candidate or a matching tag name is installed
        if any(candidate in inst or inst in candidate for inst in installed):
            # Resolve the installed name
            installed_name = next(
                inst for inst in installed if candidate in inst or inst in candidate
            )
            return installed_name, f"Reusing already-installed compatible model '{installed_name}'"

    # If the user has some other models installed that we didn't list but might be compatible,
    # let's look for any generic qwen2.5 or gemma3 models
    for inst in installed:
        inst_lower = inst.lower()
        has_compat = (
            "gemma3:1b" in inst_lower or
            "gemma3:4b" in inst_lower or
            "qwen2.5:0.5b" in inst_lower or
            "qwen2.5:1.5b" in inst_lower
        )
        if has_compat:
            return inst, f"Reusing existing installed compatible model '{inst}'"

    # 2. No pre-installed compatible models found. Select candidate based on system hardware resources
    if ram_gb >= 24.0 and free_disk >= SLM_TIERS["large"]["required_disk_gb"]:
        selected = SLM_TIERS["large"]["models"][0]
        reason = (
            f"High system config detected (RAM: {ram_gb:.1f}GB, Free Disk: {free_disk:.1f}GB). "
            f"Selecting high-tier model '{selected}'."
        )
    elif ram_gb >= 12.0 and free_disk >= SLM_TIERS["medium"]["required_disk_gb"]:
        selected = SLM_TIERS["medium"]["models"][0]
        reason = (
            f"Medium system config detected (RAM: {ram_gb:.1f}GB, Free Disk: {free_disk:.1f}GB). "
            f"Selecting medium-tier model '{selected}'."
        )
    elif ram_gb >= 6.0 and free_disk >= SLM_TIERS["small"]["required_disk_gb"]:
        selected = SLM_TIERS["small"]["models"][0]
        reason = (
            f"Standard system config detected (RAM: {ram_gb:.1f}GB, Free Disk: {free_disk:.1f}GB). "
            f"Selecting standard model '{selected}'."
        )
    else:
        selected = SLM_TIERS["tiny"]["models"][0]
        reason = (
            f"Constrained system resources detected (RAM: {ram_gb:.1f}GB, Free Disk: {free_disk:.1f}GB). "
            f"Selecting tiny lightweight model '{selected}'."
        )

    return selected, reason
