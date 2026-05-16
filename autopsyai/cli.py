"""
autopsyai CLI.

Commands:
    show      Display a recorded trace
    list      List stored traces
    analyze   Run analyzers on a trace and print findings
    export    Export a trace to JSON or HTML
    doctor    Check configuration
    clean     Delete old traces
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Annotated

from rich.console import Console
import typer

from autopsyai import __version__

app = typer.Typer(
    name="autopsyai",
    help="Local-first agent run debugger — record, replay, and diagnose LLM agent failures.",
    add_completion=True,
    rich_markup_mode="rich",
    no_args_is_help=True,
)

console = Console()


def _version_cb(value: bool) -> None:
    if value:
        console.print(f"autopsyai {__version__}")
        raise typer.Exit


@app.callback()
def main(
    version: Annotated[
        bool | None,
        typer.Option("--version", "-V", callback=_version_cb, is_eager=True),
    ] = None,
) -> None:
    pass


@app.command()
def show(
    trace_id: Annotated[str, typer.Argument(help="Trace ID to display.")],
    show_io: Annotated[bool, typer.Option("--io", help="Show span inputs/outputs.")] = False,
    analyze_flag: Annotated[
        bool, typer.Option("--analyze", "-a", help="Also run analyzers.")
    ] = False,
) -> None:
    """Display a recorded trace as a visual timeline."""
    from autopsyai.analyzers import analyze
    from autopsyai.core.store import TraceStore
    from autopsyai.reporters.terminal import TerminalReporter

    async def _run() -> None:
        async with TraceStore() as store:
            trace = await store.get_trace(trace_id)
        if trace is None:
            console.print(f"[red]Trace not found:[/] {trace_id}")
            raise typer.Exit(1)
        reporter = TerminalReporter()
        reporter.report_trace(trace, show_io=show_io)
        if analyze_flag:
            analysis = analyze(trace)
            console.print()
            reporter.report_analysis(analysis)

    asyncio.run(_run())


@app.command("list")
def list_traces(
    limit: Annotated[int, typer.Option("--limit", "-n")] = 20,
    status: Annotated[str | None, typer.Option("--status", "-s")] = None,
) -> None:
    """List stored traces."""
    from rich.table import Table

    from autopsyai.core.store import TraceStore

    async def _run() -> None:
        async with TraceStore() as store:
            traces = await store.list_traces(limit=limit, status=status)
        if not traces:
            console.print("[yellow]No traces found.[/]")
            return
        table = Table(title="Stored Traces", show_lines=True)
        table.add_column("Trace ID", style="dim", width=36)
        table.add_column("Name", style="bold")
        table.add_column("Status")
        table.add_column("Started")
        table.add_column("Finished")
        status_color = {"completed": "green", "failed": "red", "running": "yellow"}
        for t in traces:
            color = status_color.get(t["status"], "white")
            table.add_row(
                t["trace_id"],
                t["name"],
                f"[{color}]{t['status']}[/]",
                str(t["started_at"])[:19],
                str(t["finished_at"] or "—")[:19],
            )
        console.print(table)

    asyncio.run(_run())


@app.command()
def analyze(
    trace_id: Annotated[str, typer.Argument(help="Trace ID to analyze.")],
) -> None:
    """Run all analyzers on a trace and print findings."""
    from autopsyai import analyze as run_analyze
    from autopsyai.core.store import TraceStore
    from autopsyai.reporters.terminal import TerminalReporter

    async def _run() -> None:
        async with TraceStore() as store:
            trace = await store.get_trace(trace_id)
        if trace is None:
            console.print(f"[red]Trace not found:[/] {trace_id}")
            raise typer.Exit(1)
        analysis = run_analyze(trace)
        TerminalReporter().report_analysis(analysis)
        raise typer.Exit(1 if analysis.has_issues else 0)

    asyncio.run(_run())


@app.command()
def export(
    trace_id: Annotated[str, typer.Argument(help="Trace ID to export.")],
    output: Annotated[
        Path | None,
        typer.Option("--output", "-o", help="Output path (.json or .html)."),
    ] = None,
    fmt: Annotated[str, typer.Option("--format", "-f", help="json or html.")] = "json",
) -> None:
    """Export a trace to JSON or HTML."""
    from autopsyai import analyze as run_analyze
    from autopsyai.core.store import TraceStore
    from autopsyai.reporters.html_reporter import HTMLReporter
    from autopsyai.reporters.json_reporter import JSONReporter

    async def _run() -> None:
        async with TraceStore() as store:
            trace = await store.get_trace(trace_id)
        if trace is None:
            console.print(f"[red]Trace not found:[/] {trace_id}")
            raise typer.Exit(1)

        ext = ".html" if fmt == "html" else ".json"
        dest = output or Path(f"autopsyai_{trace_id[:8]}{ext}")

        if fmt == "html":
            analysis = run_analyze(trace)
            HTMLReporter().write(trace, dest, analysis)
        else:
            JSONReporter().write_trace(trace, dest)

        console.print(f"[green]Exported to:[/] {dest}")

    asyncio.run(_run())


@app.command()
def doctor() -> None:
    """Check configuration and database connectivity."""
    from autopsyai.config import get_settings
    from autopsyai.core.store import TraceStore

    async def _run() -> None:
        settings = get_settings()
        console.print("[bold]autopsyai doctor[/]\n")
        console.print(f"  DB path:   {settings.db_path}")

        async with TraceStore() as store:
            s = await store.stats()
        console.print(f"  Traces:    {s['traces']}")
        console.print(f"  Spans:     {s['spans']}")
        console.print("\n[green]All checks passed.[/]")

    asyncio.run(_run())


@app.command()
def clean(
    yes: Annotated[bool, typer.Option("--yes", "-y")] = False,
    status: Annotated[str, typer.Option("--status")] = "failed",
) -> None:
    """Delete traces by status (default: failed)."""
    from autopsyai.core.store import TraceStore

    if not yes:
        typer.confirm(f"Delete all '{status}' traces?", abort=True)

    async def _run() -> None:
        async with TraceStore() as store:
            traces = await store.list_traces(limit=10_000, status=status)
            count = 0
            for t in traces:
                await store.delete_trace(t["trace_id"])
                count += 1
        console.print(f"[green]Deleted {count} trace(s).[/]")

    asyncio.run(_run())


if __name__ == "__main__":
    app()
