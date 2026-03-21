"""Scanner module — discovers and extracts model strings from project files."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path

from .config_parser import (
    ConfigModelEntry,
    discover_config_files,
    parse_json_file,
    parse_source_file,
    parse_toml_file,
    parse_yaml_file,
)
from .env_parser import EnvModelEntry, discover_env_files, parse_env_file
from .framework_detector import strip_framework_prefix
from .patterns import ModelMatch, identify_provider, normalize_model_id

__all__ = [
    "ScanResult",
    "scan_directory",
    "EnvModelEntry",
    "ConfigModelEntry",
    "ModelMatch",
]


@dataclass
class ScanResult:
    """Aggregated scan result for a project directory."""

    project_path: str
    env_entries: list[EnvModelEntry] = field(default_factory=list)
    config_entries: list[ConfigModelEntry] = field(default_factory=list)

    @property
    def all_models(self) -> list[dict[str, str]]:
        """Return a flat list of all found models with metadata."""
        results: list[dict[str, str]] = []
        for e in self.env_entries:
            results.append({
                "file": e.file_path,
                "variable": e.variable_name,
                "model": e.model_value,
                "canonical": _normalize_with_framework(e.model_value),
                "source_type": "env",
            })
        for c in self.config_entries:
            results.append({
                "file": c.file_path,
                "variable": c.key_path,
                "model": c.model_value,
                "canonical": _normalize_with_framework(c.model_value),
                "source_type": "config",
            })
        return results

    @property
    def unique_models(self) -> set[str]:
        """Return set of unique canonical model IDs."""
        return {m["canonical"] for m in self.all_models}

    @property
    def total_count(self) -> int:
        return len(self.env_entries) + len(self.config_entries)


def _normalize_with_framework(model_value: str) -> str:
    """Normalize model string, stripping framework prefixes first."""
    bare, _provider = strip_framework_prefix(model_value)
    if bare != model_value and identify_provider(bare):
        return normalize_model_id(bare)
    return normalize_model_id(model_value)


def scan_directory(directory: str | Path, system_wide: bool = False) -> ScanResult:
    """Scan a project directory for all model strings."""
    directory = Path(directory).resolve()
    result = ScanResult(project_path=str(directory))

    if system_wide:
        from .env_parser import discover_system_env_files
        env_files = discover_system_env_files()
        config_files = {"yaml": [], "toml": [], "json": [], "source": []}
    else:
        env_files = discover_env_files(directory)
        config_files = discover_config_files(directory)

    with ThreadPoolExecutor() as executor:
        # Schedule pure env files
        env_futures = {executor.submit(parse_env_file, f): f for f in env_files}
        
        # Schedule config files mapped to their parser function
        config_tasks = []
        for yaml_file in config_files["yaml"]:
            config_tasks.append((parse_yaml_file, yaml_file))
        for toml_file in config_files["toml"]:
            config_tasks.append((parse_toml_file, toml_file))
        for json_file in config_files["json"]:
            config_tasks.append((parse_json_file, json_file))
        for source_file in config_files["source"]:
            config_tasks.append((parse_source_file, source_file))

        config_futures = {executor.submit(func, f): f for func, f in config_tasks}

        # Gather results
        for future in as_completed(env_futures):
            try:
                result.env_entries.extend(future.result())
            except Exception:
                pass

        for future in as_completed(config_futures):
            try:
                result.config_entries.extend(future.result())
            except Exception:
                pass

    return result

