"""Rich terminal reporter — renders a trace as a visual timeline."""

from __future__ import annotations

from typing import TYPE_CHECKING

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from autopsyai.models.span import SpanKind, SpanStatus
from autopsyai.models.trace import Trace

if TYPE_CHECKING:
    from autopsyai.models.analysis import TraceAnalysis

_KIND_ICON: dict[SpanKind, str] = {
    SpanKind.LLM:       "🤖",
    SpanKind.TOOL:      "🔧",
    SpanKind.AGENT:     "🧠",
    SpanKind.CHAIN:     "⛓",
    SpanKind.RETRIEVAL: "🔍",
    SpanKind.CUSTOM:    "◆",
}

_STATUS_STYLE: dict[SpanStatus, tuple[str, str]] = {
    SpanStatus.OK:      ("✓", "green"),
    SpanStatus.ERROR:   ("✗", "bold red"),
    SpanStatus.TIMEOUT: ("⏱", "yellow"),
}


class TerminalReporter:
    """Renders traces and analysis results to the terminal using Rich."""

    def __init__(self, color: bool = True) -> None:
        self.console = Console(highlight=False, force_terminal=color)

    def report_trace(self, trace: Trace, show_io: bool = False) -> None:
        """Print a full trace timeline."""
        status_color = "green" if trace.succeeded else "red"
        self.console.print(Panel(
            f"[bold cyan]autopsyai[/] — [italic]{trace.name}[/]  "
            f"[{status_color}]{trace.status.value.upper()}[/]  "
            f"[dim]{trace.duration_ms:.0f}ms · {trace.span_count} spans · {trace.total_tokens} tokens[/]",
            expand=False,
        ))
        self._print_span_tree(trace, show_io)

    def _print_span_tree(self, trace: Trace, show_io: bool, parent_id: str | None = None, depth: int = 0) -> None:
        spans = [s for s in trace.spans if s.parent_id == parent_id]
        for span in spans:
            icon = _KIND_ICON.get(span.kind, "◆")
            status_icon, style = _STATUS_STYLE[span.status]
            indent = "  " * depth + ("└─ " if depth > 0 else "")
            line = Text()
            line.append(indent)
            line.append(f"{icon} ", style="bold")
            line.append(f"{span.name}", style="bold white")
            line.append(f"  {status_icon} ", style=style)
            line.append(f"{span.duration_ms:.0f}ms", style="dim")
            if span.usage:
                line.append(f"  [{span.usage.total_tokens} tok]", style="dim cyan")
            if span.tool_name:
                line.append(f"  tool={span.tool_name}", style="dim magenta")
            if span.failed and span.error:
                line.append(f"\n{' ' * (len(indent) + 3)}[red]{span.error[:120]}[/]")
            self.console.print(line)
            if show_io and span.inputs:
                self.console.print(f"{'  ' * (depth + 2)}[dim]in:[/] {str(span.inputs)[:100]}")
            if show_io and span.outputs:
                self.console.print(f"{'  ' * (depth + 2)}[dim]out:[/] {str(span.outputs)[:100]}")
            self._print_span_tree(trace, show_io, parent_id=span.span_id, depth=depth + 1)

    def report_analysis(self, analysis: TraceAnalysis) -> None:
        """Print analyzer findings."""
        if not analysis.findings:
            self.console.print("[green]✓ No issues found.[/]")
            return

        table = Table(box=box.ROUNDED, show_header=True, header_style="bold magenta", expand=True)
        table.add_column("Severity", width=10)
        table.add_column("Code", width=24)
        table.add_column("Message", ratio=1)
        table.add_column("Span", width=36, style="dim")

        severity_style = {"critical": "bold red", "error": "red", "warning": "yellow", "info": "dim"}
        for f in sorted(analysis.findings, key=lambda x: x.severity.value):
            style = severity_style.get(f.severity.value, "")
            table.add_row(
                Text(f.severity.value.upper(), style=style),
                f.code,
                f.message,
                f.span_id or "",
            )
        self.console.print(table)

        if analysis.cost_breakdown:
            self.console.print(f"\n[bold]Cost:[/] ~${analysis.total_cost_usd:.5f}  "
                               f"[dim]{analysis.total_tokens:,} tokens[/]")
        if analysis.failure_root_cause:
            self.console.print(f"[bold red]Root cause:[/] {analysis.failure_root_cause}")
        if analysis.loop_detected:
            self.console.print("[bold red]⚠ Loop detected[/]")
