"""Failure analyzer — identifies error patterns and root causes."""

from __future__ import annotations

from typing import TYPE_CHECKING

from autopsyai.analyzers.base import BaseAnalyzer
from autopsyai.models.analysis import Finding, Severity, TraceAnalysis
from autopsyai.models.span import SpanKind, SpanStatus

if TYPE_CHECKING:
    from autopsyai.models.trace import Trace


class FailureAnalyzer(BaseAnalyzer):
    """
    Scans spans for errors and classifies failure patterns.

    Findings produced:
    - SPAN_ERROR          — a span ended with status=ERROR
    - TOOL_FAILURE        — a tool call failed
    - LLM_FAILURE         — an LLM call failed (rate limit, timeout, etc.)
    - CHAIN_FAILURE       — a chain step failed, masking downstream errors
    - UNHANDLED_EXCEPTION — error_type suggests an uncaught Python exception
    """

    analyzer_name = "failure"

    # Exception types that indicate unhandled errors (not expected API errors)
    _UNHANDLED_TYPES = frozenset({
        "AttributeError", "TypeError", "ValueError", "KeyError",
        "IndexError", "RuntimeError", "AssertionError", "NotImplementedError",
    })

    def analyze(self, trace: Trace, analysis: TraceAnalysis) -> list[Finding]:
        findings: list[Finding] = []

        findings.extend(
            self._classify(span)
            for span in trace.spans
            if span.status == SpanStatus.ERROR
        )

        # Identify root cause: the first error with no failed parent
        failed_ids = {s.span_id for s in trace.spans if s.status == SpanStatus.ERROR}
        for span in trace.spans:
            if span.span_id not in failed_ids:
                continue
            if span.parent_id not in failed_ids:
                # This span's parent succeeded — it's the origin of the failure chain
                analysis.failure_root_cause = (
                    f"{span.name}: {span.error or 'unknown error'}"
                )
                findings.append(Finding(
                    code="ROOT_CAUSE_IDENTIFIED",
                    severity=Severity.CRITICAL,
                    message=(
                        f"Root cause of failure: [{span.kind.value.upper()}] {span.name}"
                        + (f" — {span.error}" if span.error else "")
                    ),
                    span_id=span.span_id,
                    metadata={"error_type": span.error_type or ""},
                ))
                break

        return findings

    def _classify(self, span: object) -> Finding:
        from autopsyai.models.span import Span
        assert isinstance(span, Span)

        if span.error_type in self._UNHANDLED_TYPES:
            code = "UNHANDLED_EXCEPTION"
            severity = Severity.CRITICAL
        elif span.kind == SpanKind.TOOL:
            code = "TOOL_FAILURE"
            severity = Severity.ERROR
        elif span.kind == SpanKind.LLM:
            code = "LLM_FAILURE"
            severity = Severity.ERROR
        elif span.kind == SpanKind.CHAIN:
            code = "CHAIN_FAILURE"
            severity = Severity.WARNING
        else:
            code = "SPAN_ERROR"
            severity = Severity.ERROR

        return Finding(
            code=code,
            severity=severity,
            message=(
                f"[{span.kind.value.upper()}] {span.name} failed"
                + (f": {span.error}" if span.error else "")
            ),
            span_id=span.span_id,
            metadata={
                "error_type": span.error_type or "",
                "duration_ms": span.duration_ms,
            },
        )
