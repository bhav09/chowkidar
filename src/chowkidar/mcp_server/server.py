"""MCP server implementation using FastMCP for IDE integration.

Exposes tools for querying model deprecation status and updating env files.
Run via: chowkidar mcp (stdio transport, spawned by IDE)
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from ..config import Config
from ..registry.db import Registry
from ..scanner import scan_directory
from ..updater.env_writer import update_env_value

mcp = FastMCP(
    "chowkidar",
    instructions=(
        "Chowkidar is a local LLM model deprecation watchdog. "
        "Use its tools to check if models in the current project are deprecated "
        "and to get recommended replacements."
    ),
)

_registry: Registry | None = None
_config: Config | None = None


def _get_registry() -> Registry:
    global _registry
    if _registry is None:
        _registry = Registry()
        _registry.init_db()
    return _registry


def _get_config() -> Config:
    global _config
    if _config is None:
        _config = Config()
    return _config


@mcp.tool()
def list_deprecated_models(project_path: str | None = None) -> str:
    """List all deprecated or soon-to-sunset models found in the current project.

    Args:
        project_path: Path to project directory. Uses CWD if not specified.

    Returns:
        JSON summary of deprecated models with sunset dates and replacements.
    """
    project_path = project_path or os.getcwd()
    registry = _get_registry()

    scan_result = scan_directory(project_path)
    if scan_result.total_count == 0:
        return json.dumps({"status": "clean", "message": "No model strings found in project."})

    deprecated: list[dict] = []
    clean: list[dict] = []

    for model_info in scan_result.all_models:
        canonical = model_info["canonical"]
        record = registry.get_model(canonical)

        if record and record.sunset_date:
            try:
                sunset = datetime.fromisoformat(record.sunset_date)
                days_until = (sunset - datetime.now(timezone.utc).replace(tzinfo=None)).days
            except ValueError:
                days_until = None

            deprecated.append({
                "variable": model_info["variable"],
                "file": model_info["file"],
                "model": model_info["model"],
                "sunset_date": record.sunset_date,
                "days_until_sunset": days_until,
                "replacement": record.replacement,
                "replacement_confidence": record.replacement_confidence,
                "breaking_changes": record.breaking_changes,
                "is_pinned": registry.is_pinned(canonical),
            })
        else:
            clean.append({
                "variable": model_info["variable"],
                "model": model_info["model"],
                "status": "active" if record else "unknown",
            })

    return json.dumps({
        "project": project_path,
        "deprecated_count": len(deprecated),
        "active_count": len(clean),
        "deprecated_models": deprecated,
        "active_models": clean,
        "last_registry_sync": registry.last_sync_time(),
    }, indent=2)


@mcp.tool()
def get_model_status(model_id: str) -> str:
    """Get the deprecation status of a specific model.

    Args:
        model_id: The model identifier (e.g., 'gpt-3.5-turbo' or 'openai/gpt-3.5-turbo').

    Returns:
        JSON with model status, sunset date, and replacement info.
    """
    registry = _get_registry()

    from ..scanner.patterns import normalize_model_id
    canonical = normalize_model_id(model_id)

    record = registry.get_model(canonical)
    if record is None:
        record = registry.get_model(model_id)

    if record is None:
        return json.dumps({
            "model_id": model_id,
            "status": "unknown",
            "message": f"Model '{model_id}' not found in registry. Run 'chowkidar sync' to update.",
        })

    status = "active"
    days_until = None
    if record.sunset_date:
        try:
            sunset = datetime.fromisoformat(record.sunset_date)
            days_until = (sunset - datetime.now(timezone.utc).replace(tzinfo=None)).days
            status = "sunset_passed" if days_until <= 0 else "deprecating"
        except ValueError:
            status = "deprecating"

    return json.dumps({
        "model_id": record.id,
        "provider": record.provider,
        "status": status,
        "sunset_date": record.sunset_date,
        "days_until_sunset": days_until,
        "replacement": record.replacement,
        "replacement_confidence": record.replacement_confidence,
        "breaking_changes": record.breaking_changes,
        "is_pinned": registry.is_pinned(record.id),
        "source_url": record.source_url,
    }, indent=2)


@mcp.tool()
def update_model_env(
    file_path: str,
    variable_name: str,
    new_model: str,
    dry_run: bool = False,
) -> str:
    """Update a model value in an env file with a recommended replacement.

    This tool requires AUTO_UPDATE=true in Chowkidar config. By default it is disabled.

    Args:
        file_path: Path to the .env file to modify.
        variable_name: The environment variable name (e.g., 'LLM_MODEL_NAME').
        new_model: The new model identifier to set.
        dry_run: If true, show what would change without writing.

    Returns:
        JSON result of the update operation.
    """
    config = _get_config()

    if not config.get("auto_update", False):
        return json.dumps({
            "status": "permission_denied",
            "message": (
                "Auto-update is disabled. Enable with: chowkidar config set auto_update true\n"
                "Or manually update the file."
            ),
        })

    result = update_env_value(
        file_path=Path(file_path),
        variable_name=variable_name,
        new_value=new_model,
        dry_run=dry_run,
    )

    return json.dumps(result, indent=2)


def run_server() -> None:
    """Start the MCP server (stdio transport)."""
    mcp.run(transport="stdio")
