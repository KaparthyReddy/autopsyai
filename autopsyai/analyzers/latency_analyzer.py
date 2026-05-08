"""Latency analyzer — identifies slow spans and aggregates timing stats."""

from __future__ import annotations

from collections import defaultdict

from autopsyai.analyzers.base import BaseAnalyzer
from autopsyai.models.analysis import Finding, LatencyBreakdown, Severity, TraceAnalysis
from autopsyai.models.trace import Trace

_SLOW_SPAN_MS = 5_000   # 5 seconds — single span threshold
_SLOW_TOTAL_MS = 30_000  # 30 seconds — total trace threshold


class LatencyAnalyzer(BaseAnalyzer):
    """
    Aggregates latency per span kind and flags slow spans.

    Findings produced:
    - SLOW_SPAN         — a single span took more than 5 seconds
    - SLOW_TRACE        — total trace duration exceeds 30 seconds
    - LATENCY_OUTLIER   — a span took >3x the mean for its kind
    """

    analyzer_name = "latency"

    def analyze(self, trace: Trace, analysis: TraceAnalysis) -> list[Finding]:
        findings: list[Finding] = []
        by_kind: dict[str, list[tuple[float, str]]] = defaultdict(list)

        for span in trace.spans:
            if span.ended_at is None:
                continue
            ms = span.duration_ms
            by_kind[span.kind.value].append((ms, span.span_id))

            if ms > _SLOW_SPAN_MS:
                findings.append(Finding(
                    code="SLOW_SPAN",
                    severity=Severity.WARNING,
                    message=f"Span '{span.name}' took {ms:.0f}ms (>{_SLOW_SPAN_MS}ms threshold)",
                    span_id=span.span_id,
                    metadata={"duration_ms": ms},
                ))

        # Build latency breakdowns
        breakdowns: list[LatencyBreakdown] = []
        for kind, entries in by_kind.items():
            durations = [e[0] for e in entries]
            total = sum(durations)
            mean = total / len(durations)
            max_ms = max(durations)
            slowest_id = max(entries, key=lambda e: e[0])[1]
            breakdowns.append(LatencyBreakdown(
                kind=kind,
                count=len(entries),
                total_ms=total,
                mean_ms=mean,
                max_ms=max_ms,
                slowest_span_id=slowest_id,
            ))

            # Flag outliers: spans >3x mean for their kind
            for ms, span_id in entries:
                if len(durations) > 1 and ms > mean * 3:
                    span = trace.get_span(span_id)
                    name = span.name if span else span_id
                    findings.append(Finding(
                        code="LATENCY_OUTLIER",
                        severity=Severity.INFO,
                        message=(
                            f"Span '{name}' took {ms:.0f}ms — "
                            f"{ms / mean:.1f}x the mean for {kind} spans ({mean:.0f}ms)"
                        ),
                        span_id=span_id,
                        metadata={"duration_ms": ms, "mean_ms": mean, "kind": kind},
                    ))

        analysis.latency_breakdown = breakdowns

        if trace.duration_ms > _SLOW_TOTAL_MS:
            findings.append(Finding(
                code="SLOW_TRACE",
                severity=Severity.WARNING,
                message=f"Total trace took {trace.duration_ms / 1000:.1f}s (>{_SLOW_TOTAL_MS / 1000}s threshold)",
                metadata={"duration_ms": trace.duration_ms},
            ))

        return findings
