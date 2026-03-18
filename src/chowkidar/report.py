"""Report generation — HTML, JSON, and Markdown deprecation reports."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from .pricing import compare_cost
from .registry.db import Registry
from .scanner import scan_directory


def generate_report(
    project_paths: list[Path],
    output_format: str = "markdown",
    registry: Registry | None = None,
) -> str:
    """Generate a deprecation report across one or more projects."""
    if registry is None:
        registry = Registry()
        registry.init_db()

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    projects_data: list[dict] = []

    for project_path in project_paths:
        scan_result = scan_directory(project_path)
        models_data: list[dict] = []

        for m in scan_result.all_models:
            canonical = m["canonical"]
            record = registry.get_model(canonical)
            entry: dict = {
                "variable": m["variable"],
                "model": m["model"],
                "file": m["file"],
                "canonical": canonical,
                "status": "active",
                "sunset_date": None,
                "days_until": None,
                "replacement": None,
                "cost_summary": None,
            }

            if record and record.sunset_date:
                entry["sunset_date"] = record.sunset_date
                entry["replacement"] = record.replacement
                try:
                    sunset = datetime.fromisoformat(record.sunset_date)
                    entry["days_until"] = (sunset - now).days
                except ValueError:
                    pass

                if entry["days_until"] is not None:
                    if entry["days_until"] <= 0:
                        entry["status"] = "sunset"
                    elif entry["days_until"] <= 7:
                        entry["status"] = "critical"
                    elif entry["days_until"] <= 30:
                        entry["status"] = "warning"
                    else:
                        entry["status"] = "deprecating"

                if record.replacement:
                    cost = compare_cost(canonical, record.replacement)
                    if cost:
                        entry["cost_summary"] = cost.summary

            models_data.append(entry)

        projects_data.append({
            "path": str(project_path),
            "name": project_path.name,
            "total_models": scan_result.total_count,
            "models": models_data,
        })

    if output_format == "json":
        return _render_json(projects_data, now)
    elif output_format == "html":
        return _render_html(projects_data, now)
    else:
        return _render_markdown(projects_data, now)


def _render_json(projects_data: list[dict], now: datetime) -> str:
    return json.dumps({
        "generated_at": now.isoformat(),
        "projects": projects_data,
    }, indent=2)


def _render_markdown(projects_data: list[dict], now: datetime) -> str:
    lines: list[str] = [
        "# Chowkidar Deprecation Report",
        f"*Generated: {now.strftime('%Y-%m-%d %H:%M UTC')}*",
        "",
    ]

    for proj in projects_data:
        lines.append(f"## {proj['name']}")
        lines.append(f"Path: `{proj['path']}`")
        lines.append("")

        deprecated = [m for m in proj["models"] if m["status"] != "active"]
        if not deprecated:
            lines.append("No deprecated models found.")
            lines.append("")
            continue

        lines.append("| Variable | Model | Status | Sunset | Days | Replacement | Cost |")
        lines.append("|----------|-------|--------|--------|------|-------------|------|")
        for m in deprecated:
            days = str(m["days_until"]) if m["days_until"] is not None else "?"
            repl = m["replacement"] or "-"
            cost = m.get("cost_summary", "") or "-"
            lines.append(f"| {m['variable']} | {m['model']} | {m['status']} "
                         f"| {m['sunset_date'] or '-'} | {days} | {repl} | {cost} |")
        lines.append("")

    return "\n".join(lines)


def _render_html(projects_data: list[dict], now: datetime) -> str:
    status_colors = {
        "sunset": "#dc3545",
        "critical": "#fd7e14",
        "warning": "#ffc107",
        "deprecating": "#6c757d",
        "active": "#28a745",
    }

    rows_html: list[str] = []
    for proj in projects_data:
        for m in proj["models"]:
            if m["status"] == "active":
                continue
            color = status_colors.get(m["status"], "#6c757d")
            days = str(m["days_until"]) if m["days_until"] is not None else "?"
            repl = m["replacement"] or "-"
            cost = m.get("cost_summary", "") or "-"
            rows_html.append(
                f"<tr>"
                f"<td>{proj['name']}</td>"
                f"<td><code>{m['variable']}</code></td>"
                f"<td><code>{m['model']}</code></td>"
                f'<td><span style="color:{color};font-weight:bold">{m["status"]}</span></td>'
                f"<td>{m['sunset_date'] or '-'}</td>"
                f"<td>{days}</td>"
                f"<td>{repl}</td>"
                f"<td>{cost}</td>"
                f"</tr>"
            )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Chowkidar Deprecation Report</title>
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
         max-width: 1100px; margin: 2rem auto; padding: 0 1rem; color: #1a1a2e; }}
  h1 {{ border-bottom: 2px solid #e63946; padding-bottom: 0.5rem; }}
  table {{ width: 100%; border-collapse: collapse; margin: 1rem 0; }}
  th, td {{ padding: 0.6rem 0.8rem; border: 1px solid #dee2e6; text-align: left; }}
  th {{ background: #f8f9fa; font-weight: 600; }}
  tr:nth-child(even) {{ background: #f8f9fa; }}
  code {{ background: #e9ecef; padding: 0.15rem 0.4rem; border-radius: 3px; font-size: 0.9em; }}
  .meta {{ color: #6c757d; font-size: 0.9em; }}
</style>
</head>
<body>
<h1>Chowkidar Deprecation Report</h1>
<p class="meta">Generated: {now.strftime('%Y-%m-%d %H:%M UTC')}</p>
<table>
<thead>
<tr><th>Project</th><th>Variable</th><th>Model</th><th>Status</th>
<th>Sunset Date</th><th>Days Left</th><th>Replacement</th><th>Cost Impact</th></tr>
</thead>
<tbody>
{''.join(rows_html) if rows_html else '<tr><td colspan="8">No deprecated models found.</td></tr>'}
</tbody>
</table>
<p class="meta">Report by Chowkidar — local-first LLM deprecation watchdog</p>
</body>
</html>"""
