"""CI/CD gate — blocks deployments with deprecated models."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from .registry.db import Registry
from .scanner import scan_directory


def run_gate(
    project_path: Path,
    severity: str = "block-sunset",
    output_format: str = "table",
) -> tuple[int, list[dict], str]:
    """Run CI/CD gate check.

    Returns (exit_code, violations, formatted_output).
    exit_code: 0 = clean, 1 = blocked.
    """
    registry = Registry()
    registry.init_db()
    scan_result = scan_directory(project_path)
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    violations: list[dict] = []

    for m in scan_result.all_models:
        canonical = m["canonical"]
        if registry.is_pinned(canonical):
            continue

        record = registry.get_model(canonical)
        if record is None or record.sunset_date is None:
            continue

        try:
            sunset = datetime.fromisoformat(record.sunset_date)
            days_until = (sunset - now).days
        except ValueError:
            continue

        should_block = False
        if severity == "block-sunset" and days_until <= 0:
            should_block = True
        elif severity == "block-7d" and days_until <= 7:
            should_block = True
        elif severity == "block-30d" and days_until <= 30:
            should_block = True
        elif severity == "block-all" and record.sunset_date is not None:
            should_block = True

        if should_block:
            violations.append({
                "variable": m["variable"],
                "file": m["file"],
                "model": m["model"],
                "canonical": canonical,
                "sunset_date": record.sunset_date,
                "days_until": days_until,
                "replacement": record.replacement,
                "replacement_confidence": record.replacement_confidence,
            })

    registry.close()

    exit_code = 1 if violations else 0
    formatted = _format_output(violations, output_format, project_path, severity)
    return exit_code, violations, formatted


def run_gate_staged(
    project_path: Path,
    staged_files: list[str],
) -> tuple[int, list[dict]]:
    """Gate check only on staged/changed files for pre-commit hooks."""
    from .scanner.config_parser import parse_source_file
    from .scanner.env_parser import parse_env_file
    from .scanner.patterns import normalize_model_id

    registry = Registry()
    registry.init_db()
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    violations: list[dict] = []
    for file_str in staged_files:
        fp = Path(file_str)
        if not fp.exists():
            continue

        models = []
        if fp.name.startswith(".env"):
            for entry in parse_env_file(fp):
                models.append({"model": entry.model_value, "variable": entry.variable_name, "file": str(fp)})
        else:
            for entry in parse_source_file(fp):
                models.append({"model": entry.model_value, "variable": entry.key_path, "file": str(fp)})

        for m in models:
            canonical = normalize_model_id(m["model"])
            record = registry.get_model(canonical)
            if record and record.sunset_date:
                try:
                    days_until = (datetime.fromisoformat(record.sunset_date) - now).days
                except ValueError:
                    continue
                if days_until <= 0:
                    violations.append({
                        **m, "canonical": canonical,
                        "sunset_date": record.sunset_date, "days_until": days_until,
                    })

    registry.close()
    return (1 if violations else 0), violations


def _format_output(violations: list[dict], fmt: str, project_path: Path, severity: str) -> str:
    if fmt == "json":
        return json.dumps({
            "project": str(project_path),
            "severity": severity,
            "passed": len(violations) == 0,
            "violation_count": len(violations),
            "violations": violations,
        }, indent=2)

    if fmt == "github-actions":
        lines: list[str] = []
        for v in violations:
            lines.append(
                f"::error file={v['file']},title=Chowkidar Gate"
                f"::{v['model']} sunsets on {v['sunset_date']} "
                f"(replace with {v.get('replacement', 'N/A')})"
            )
        if not violations:
            lines.append("::notice ::Chowkidar gate passed — no deprecated models found.")
        return "\n".join(lines)

    if not violations:
        return "Chowkidar gate: PASSED (no deprecated models found)"
    lines = [f"Chowkidar gate: FAILED ({len(violations)} violation(s))", ""]
    for v in violations:
        repl = v.get("replacement", "N/A")
        lines.append(f"  {v['variable']} = {v['model']} (sunset: {v['sunset_date']}, replace: {repl})")
    return "\n".join(lines)
