"""Scanner module — discovers and extracts model strings from project files."""

from __future__ import annotations

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


def scan_directory(directory: str | Path) -> ScanResult:
    """Scan a project directory for all model strings."""
    directory = Path(directory).resolve()
    result = ScanResult(project_path=str(directory))

    env_files = discover_env_files(directory)
    for env_file in env_files:
        result.env_entries.extend(parse_env_file(env_file))

    config_files = discover_config_files(directory)

    for yaml_file in config_files["yaml"]:
        result.config_entries.extend(parse_yaml_file(yaml_file))
    for toml_file in config_files["toml"]:
        result.config_entries.extend(parse_toml_file(toml_file))
    for json_file in config_files["json"]:
        result.config_entries.extend(parse_json_file(json_file))
    for source_file in config_files["source"]:
        result.config_entries.extend(parse_source_file(source_file))

    return result
