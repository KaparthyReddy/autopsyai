"""Unit tests for Span, Trace, and Analysis models."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from autopsyai.models.analysis import Finding, Severity, TraceAnalysis
from autopsyai.models.span import LLMUsage, Span, SpanKind, SpanStatus
from autopsyai.models.trace import Trace, TraceStatus


class TestLLMUsage:
    def test_total_tokens(self) -> None:
        u = LLMUsage(prompt_tokens=100, completion_tokens=50)
        assert u.total_tokens == 150

    def test_zero_tokens(self) -> None:
        u = LLMUsage()
        assert u.total_tokens == 0


class TestSpan:
    def test_duration_ms_when_ended(self) -> None:
        started = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        ended = started + timedelta(milliseconds=250)
        span = Span(
            trace_id="t1", name="test",
            started_at=started, ended_at=ended,
        )
        assert abs(span.duration_ms - 250.0) < 1.0

    def test_duration_ms_when_not_ended(self) -> None:
        span = Span(trace_id="t1", name="test")
        assert span.duration_ms == 0.0

    def test_is_root_no_parent(self) -> None:
        span = Span(trace_id="t1", name="root")
        assert span.is_root is True

    def test_is_root_with_parent(self) -> None:
        span = Span(trace_id="t1", name="child", parent_id="parent-id")
        assert span.is_root is False

    def test_failed_on_error_status(self) -> None:
        span = Span(trace_id="t1", name="s", status=SpanStatus.ERROR)
        assert span.failed is True

    def test_not_failed_on_ok(self) -> None:
        span = Span(trace_id="t1", name="s", status=SpanStatus.OK)
        assert span.failed is False

    def test_end_sets_status_and_time(self) -> None:
        span = Span(trace_id="t1", name="s")
        span.end(SpanStatus.ERROR, error="boom", error_type="ValueError")
        assert span.status == SpanStatus.ERROR
        assert span.error == "boom"
        assert span.error_type == "ValueError"
        assert span.ended_at is not None

    def test_span_kind_defaults_to_custom(self) -> None:
        span = Span(trace_id="t1", name="s")
        assert span.kind == SpanKind.CUSTOM


class TestTrace:
    def test_total_tokens(self, simple_trace: Trace) -> None:
        assert simple_trace.total_tokens == 150  # 100 + 50

    def test_llm_spans(self, simple_trace: Trace) -> None:
        assert len(simple_trace.llm_spans) == 1
        assert simple_trace.llm_spans[0].name == "llm-call"

    def test_tool_spans(self, simple_trace: Trace) -> None:
        assert len(simple_trace.tool_spans) == 1
        assert simple_trace.tool_spans[0].name == "tool-call"

    def test_failed_spans_empty_on_success(self, simple_trace: Trace) -> None:
        assert simple_trace.failed_spans == []

    def test_failed_spans_on_failure(self, failed_trace: Trace) -> None:
        assert len(failed_trace.failed_spans) == 1
        assert failed_trace.failed_spans[0].name == "tool-call"

    def test_root_spans(self, simple_trace: Trace) -> None:
        roots = simple_trace.root_spans()
        assert len(roots) == 1
        assert roots[0].name == "agent-step"

    def test_children_of(self, simple_trace: Trace) -> None:
        root = simple_trace.root_spans()[0]
        children = simple_trace.children_of(root.span_id)
        assert len(children) == 2

    def test_get_span(self, simple_trace: Trace) -> None:
        root = simple_trace.root_spans()[0]
        found = simple_trace.get_span(root.span_id)
        assert found is not None
        assert found.span_id == root.span_id

    def test_get_span_missing(self, simple_trace: Trace) -> None:
        assert simple_trace.get_span("nonexistent") is None

    def test_finish_sets_status(self) -> None:
        t = Trace(name="t")
        t.finish(TraceStatus.FAILED)
        assert t.status == TraceStatus.FAILED
        assert t.finished_at is not None

    def test_succeeded(self, simple_trace: Trace) -> None:
        assert simple_trace.succeeded is True

    def test_span_count(self, simple_trace: Trace) -> None:
        assert simple_trace.span_count == 3


class TestTraceAnalysis:
    def test_has_issues_false_when_no_errors(self) -> None:
        a = TraceAnalysis(trace_id="t1", trace_name="test")
        assert a.has_issues is False

    def test_has_issues_true_with_error_finding(self) -> None:
        a = TraceAnalysis(
            trace_id="t1",
            trace_name="test",
            findings=[Finding(code="ERR", severity=Severity.ERROR, message="bad")],
        )
        assert a.has_issues is True

    def test_critical_findings_filter(self) -> None:
        a = TraceAnalysis(
            trace_id="t1",
            trace_name="test",
            findings=[
                Finding(code="A", severity=Severity.CRITICAL, message="critical"),
                Finding(code="B", severity=Severity.WARNING, message="warn"),
            ],
        )
        assert len(a.critical_findings) == 1
        assert a.critical_findings[0].code == "A"
