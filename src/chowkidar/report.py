"""Report generation — HTML, JSON, and Markdown deprecation reports."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from .deployment import detect_deployment
from .pricing import compare_cost
from .recommendations import build_recommendation
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
        deployment = detect_deployment(project_path)
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
                "recommendation": None,
                "manual_review_required": False,
                "risk_summary": None,
            }

            if record and record.sunset_date:
                entry["sunset_date"] = record.sunset_date
                entry["replacement"] = record.replacement
                recommendation = build_recommendation(canonical, record)
                entry["recommendation"] = recommendation.to_dict()
                entry["manual_review_required"] = recommendation.manual_review_required
                risks = recommendation.commercial_risks + recommendation.future_risks + recommendation.privacy_risks
                entry["risk_summary"] = "; ".join(risks) if risks else recommendation.risk
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
            "deployment": deployment.to_dict(),
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
        deployment = proj.get("deployment", {})
        lines.append(
            f"Deployment signals: **{deployment.get('state', 'none')}** "
            f"(confidence {deployment.get('confidence', 0.0)})"
        )
        lines.append("")

        deprecated = [m for m in proj["models"] if m["status"] != "active"]
        if not deprecated:
            lines.append("No deprecated models found.")
            lines.append("")
            continue

        lines.append("| Variable | Model | Status | Sunset | Days | Replacement | Cost | Review |")
        lines.append("|----------|-------|--------|--------|------|-------------|------|--------|")
        for m in deprecated:
            days = str(m["days_until"]) if m["days_until"] is not None else "?"
            repl = m["replacement"] or "-"
            cost = m.get("cost_summary", "") or "-"
            review = "required" if m.get("manual_review_required") else "not required"
            lines.append(f"| {m['variable']} | {m['model']} | {m['status']} "
                         f"| {m['sunset_date'] or '-'} | {days} | {repl} | {cost} | {review} |")
        lines.append("")

    return "\n".join(lines)


def _escape_js_string(s: str) -> str:
    return s.replace("\\", "\\\\").replace("'", "\\'")


def _render_html(projects_data: list[dict], now: datetime) -> str:
    status_colors = {
        "sunset": "#dc3545",
        "critical": "#fd7e14",
        "warning": "#ffc107",
        "deprecating": "#6c757d",
        "active": "#28a745",
    }

    rows_html: list[str] = []
    projects_html: list[str] = []
    
    for proj in projects_data:
        dep = proj.get("deployment", {})
        state = dep.get("state", "none")
        conf = dep.get("confidence", 0.0)
        signals = dep.get("signals", [])
        
        dep_color = "#6c757d"
        if state == "likely":
            dep_color = "#dc3545"
        elif state == "possible":
            dep_color = "#ffc107"
        elif state == "confirmed":
            dep_color = "#28a745"
            
        signals_li = ""
        if signals:
            signals_li = '<ul style="margin: 0.5rem 0; padding-left: 1.2rem;">' + "".join(
                f"<li><code>{s.get('adapter').upper()}</code>: {s.get('evidence')} (strength {s.get('strength')}) in <code>{Path(s.get('file_path')).name}</code></li>"
                for s in signals
            ) + "</ul>"
        else:
            signals_li = "<p style='margin:0; font-style:italic;'>No local deployment signals detected.</p>"
            
        projects_html.append(
            f'<div style="border: 1px solid var(--border-color); border-radius: 6px; padding: 1rem; margin: 1rem 0; background-color: var(--header-bg);">'
            f'  <h3 style="margin: 0 0 0.5rem 0; font-size: 1.15em;">Project: <span style="color: var(--highlight-var-color);">{proj["name"]}</span></h3>'
            f'  <p style="margin: 0.25rem 0; font-size: 0.9em;">Local Path: <code>{proj["path"]}</code></p>'
            f'  <p style="margin: 0.25rem 0; font-size: 0.9em;">'
            f'    Deployment Signals: <span class="badge" style="background-color: {dep_color}; color: #ffffff; font-weight: bold;">{state}</span> '
            f'    (confidence score: <b>{conf}</b>)'
            f'  </p>'
            f'  <div style="font-size: 0.85em; color: #6c757d; margin-top: 0.5rem; border-top: 1px solid var(--border-color); padding-top: 0.5rem;">'
            f'    {signals_li}'
            f'  </div>'
            f'</div>'
        )

        for m in proj["models"]:
            if m["status"] == "active":
                continue
            color = status_colors.get(m["status"], "#6c757d")
            days = str(m["days_until"]) if m["days_until"] is not None else "?"
            repl = m["replacement"] or "-"
            cost = m.get("cost_summary", "") or "-"
            review = "Yes" if m.get("manual_review_required") else "No"
            risk = m.get("risk_summary") or "-"
            file_escaped = _escape_js_string(m["file"])

            # Action button is shown only if we have a file path
            action_btn = (
                f'<button class="btn-action" onclick="openInEditor(\'{file_escaped}\')">'
                f'✏️ Open in Editor</button>'
                if m["file"] else "-"
            )

            rows_html.append(
                f"<tr>"
                f"<td>{proj['name']}</td>"
                f"<td><code class='highlight-var'>{m['variable']}</code></td>"
                f"<td><code class='highlight-model'>{m['model']}</code></td>"
                f'<td><span class="badge" style="background-color:{color};'
                f'color:#ffffff;font-weight:bold">{m["status"]}</span></td>'
                f"<td>{m['sunset_date'] or '-'}</td>"
                f"<td>{days}</td>"
                f"<td>{repl}</td>"
                f"<td>{cost}</td>"
                f"<td>{review}</td>"
                f"<td>{risk}</td>"
                f"<td>{action_btn}</td>"
                f"</tr>"
            )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Chowkidar Deprecation Report</title>
<style>
  :root {{
    --bg-color: #ffffff;
    --text-color: #1a1a2e;
    --border-color: #dee2e6;
    --header-bg: #f8f9fa;
    --row-even-bg: #f8f9fa;
    --highlight-var-color: #0d6efd;
    --highlight-model-color: #d63384;
    --btn-bg: #0d6efd;
    --btn-hover: #0b5ed7;
    --toast-success: #198754;
    --toast-error: #dc3545;
  }}
  @media (prefers-color-scheme: dark) {{
    :root {{
      --bg-color: #121212;
      --text-color: #e0e0e0;
      --border-color: #333333;
      --header-bg: #1a1a1a;
      --row-even-bg: #181a1b;
      --highlight-var-color: #58a6ff;
      --highlight-model-color: #ff7b72;
      --btn-bg: #21262d;
      --btn-hover: #30363d;
    }}
  }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    max-width: 1200px;
    margin: 2rem auto;
    padding: 0 1.5rem;
    color: var(--text-color);
    background-color: var(--bg-color);
    line-height: 1.5;
  }}
  h1 {{
    border-bottom: 3px solid #e63946;
    padding-bottom: 0.5rem;
    margin-bottom: 0.5rem;
  }}
  .meta {{
    color: #6c757d;
    font-size: 0.9em;
    margin-bottom: 2rem;
  }}
  table {{
    width: 100%;
    border-collapse: collapse;
    margin: 1.5rem 0;
    box-shadow: 0 1px 3px rgba(0,0,0,0.1);
  }}
  th, td {{
    padding: 0.75rem 1rem;
    border: 1px solid var(--border-color);
    text-align: left;
  }}
  th {{
    background-color: var(--header-bg);
    font-weight: 600;
  }}
  tr:nth-child(even) {{
    background-color: var(--row-even-bg);
  }}
  code {{
    background-color: rgba(175, 184, 193, 0.2);
    padding: 0.2rem 0.4rem;
    border-radius: 4px;
    font-size: 0.9em;
  }}
  .highlight-var {{
    color: var(--highlight-var-color);
    font-weight: 600;
  }}
  .highlight-model {{
    color: var(--highlight-model-color);
    font-weight: 600;
  }}
  .badge {{
    display: inline-block;
    padding: 0.25em 0.6em;
    font-size: 0.75em;
    font-weight: 700;
    line-height: 1;
    text-align: center;
    white-space: nowrap;
    vertical-align: baseline;
    border-radius: 0.25rem;
    text-transform: uppercase;
  }}
  .btn-action {{
    background-color: var(--btn-bg);
    color: #ffffff;
    border: 1px solid var(--border-color);
    padding: 0.4rem 0.8rem;
    font-size: 0.85em;
    border-radius: 4px;
    cursor: pointer;
    font-weight: 500;
    transition: background-color 0.2s;
  }}
  .btn-action:hover {{
    background-color: var(--btn-hover);
  }}
  /* Toast styles */
  .toast {{
    position: fixed;
    bottom: 20px;
    right: 20px;
    padding: 1rem 1.5rem;
    border-radius: 4px;
    color: #ffffff;
    font-weight: 500;
    opacity: 0;
    transition: opacity 0.3s ease-in-out;
    z-index: 1000;
  }}
  .toast-success {{
    background-color: var(--toast-success);
  }}
  .toast-error {{
    background-color: var(--toast-error);
  }}
</style>
</head>
<body>
<h1>Chowkidar Deprecation Report</h1>
<p class="meta">Generated: {now.strftime('%Y-%m-%d %H:%M UTC')}</p>

<h2>Workspace / Project Summary</h2>
{"".join(projects_html)}

<h2>Deprecated Models</h2>
<table>
<thead>
<tr>
  <th>Project</th>
  <th>Variable</th>
  <th>Model</th>
  <th>Status</th>
  <th>Sunset Date</th>
  <th>Days Left</th>
  <th>Replacement</th>
  <th>Cost Impact</th>
  <th>Manual Review</th>
  <th>Risk</th>
  <th>Action</th>
</tr>
</thead>
<tbody>
{"".join(rows_html) if rows_html else
 '<tr><td colspan="11" style="text-align:center;">No deprecated models found.</td></tr>'}
</tbody>
</table>
<p class="meta">Report by Chowkidar — local-first LLM deprecation watchdog</p>

<div id="toast" class="toast"></div>

<script>
async function openInEditor(filePath) {{
  const toast = document.getElementById("toast");
  try {{
    const response = await fetch(`/open-editor?path=${{encodeURIComponent(filePath)}}`);
    const data = await response.json();
    if (data.success) {{
      showToast("Successfully opened " + filePath.split(/[\\\\/]/).pop() + " in default editor!", true);
    }} else {{
      showToast("Failed to open: " + data.message, false);
    }}
  }} catch (err) {{
    showToast("Error: " + err.message, false);
  }}
}}

function showToast(message, isSuccess) {{
  const toast = document.getElementById("toast");
  toast.innerText = message;
  toast.className = "toast " + (isSuccess ? "toast-success" : "toast-error");
  toast.style.opacity = "1";
  setTimeout(() => {{
    toast.style.opacity = "0";
  }}, 3000);
}}
</script>
</body>
</html>"""
