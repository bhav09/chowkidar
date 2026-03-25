"""Multi-repo dashboard — TUI view of deprecation status across projects."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from rich.console import Console
from rich.table import Table

from .registry.db import Registry
from .scanner import scan_directory


def _build_dashboard_table(
    registry: Registry,
    projects: list[str],
) -> Table:
    """Build a rich table showing deprecation status across all watched projects."""
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    table = Table(
        title="Chowkidar Dashboard — Multi-Repo Deprecation Status",
        show_lines=True,
    )
    table.add_column("Project", style="cyan", width=25)
    table.add_column("Models", justify="right")
    table.add_column("Deprecated", justify="right")
    table.add_column("Critical", justify="right", style="red")
    table.add_column("Warning", justify="right", style="yellow")
    table.add_column("Status")

    total_models = 0
    total_deprecated = 0
    total_critical = 0

    for project_path in projects:
        p = Path(project_path)
        if not p.is_dir():
            table.add_row(p.name, "-", "-", "-", "-", "[dim]not found[/dim]")
            continue

        try:
            scan_result = scan_directory(p)
        except Exception:
            table.add_row(p.name, "-", "-", "-", "-", "[red]scan error[/red]")
            continue

        deprecated = 0
        critical = 0
        warning = 0

        for m in scan_result.all_models:
            canonical = m["canonical"]
            record = registry.get_model(canonical)
            if record and record.sunset_date:
                try:
                    sunset = datetime.fromisoformat(record.sunset_date)
                    days = (sunset - now).days
                except ValueError:
                    continue
                deprecated += 1
                if days <= 7:
                    critical += 1
                elif days <= 30:
                    warning += 1

        total_models += scan_result.total_count
        total_deprecated += deprecated
        total_critical += critical

        if critical > 0:
            status = "[bold red]CRITICAL[/bold red]"
        elif warning > 0:
            status = "[yellow]WARNING[/yellow]"
        elif deprecated > 0:
            status = "[dim]deprecating[/dim]"
        else:
            status = "[green]OK[/green]"

        table.add_row(
            p.name,
            str(scan_result.total_count),
            str(deprecated),
            str(critical),
            str(warning),
            status,
        )

    table.add_section()
    summary_status = "[bold red]ISSUES[/bold red]" if total_critical > 0 else "[green]OK[/green]"
    table.add_row(
        "[bold]TOTAL[/bold]",
        f"[bold]{total_models}[/bold]",
        f"[bold]{total_deprecated}[/bold]",
        f"[bold]{total_critical}[/bold]",
        "-",
        summary_status,
    )
    return table


def run_dashboard(registry: Registry | None = None) -> None:
    """Display a TUI dashboard of all watched projects."""
    if registry is None:
        registry = Registry()
        registry.init_db()

    projects = registry.get_watched_projects()
    console = Console()

    if not projects:
        console.print("[yellow]No watched projects.[/yellow] Run 'chowkidar watch <path>' first.")
        return

    table = _build_dashboard_table(registry, projects)
    console.print(table)
    console.print(f"\n[dim]{len(projects)} project(s) monitored[/dim]")
