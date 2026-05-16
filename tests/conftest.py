"""Shared pytest fixtures."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from autopsyai.models.span import LLMUsage, Span, SpanKind, SpanStatus
from autopsyai.models.trace import Trace, TraceStatus


def _make_span(
    trace_id: str,
    name: str,
    kind: SpanKind = SpanKind.CUSTOM,
    status: SpanStatus = SpanStatus.OK,
    parent_id: str | None = None,
    duration_ms: float = 100.0,
    tool_name: str = "",
    tool_args: dict | None = None,
    usage: LLMUsage | None = None,
    error: str | None = None,
    error_type: str | None = None,
) -> Span:
    started = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    from datetime import timedelta
    ended = started + timedelta(milliseconds=duration_ms)
    return Span(
        trace_id=trace_id,
        parent_id=parent_id,
        name=name,
        kind=kind,
        status=status,
        started_at=started,
        ended_at=ended,
        tool_name=tool_name,
        tool_args=tool_args or {},
        usage=usage,
        error=error,
        error_type=error_type or ("RuntimeError" if error else None),
    )


@pytest.fixture
def simple_trace() -> Trace:
    t = Trace(name="simple-trace")
    s1 = _make_span(t.trace_id, "agent-step", SpanKind.AGENT)
    s2 = _make_span(t.trace_id, "llm-call", SpanKind.LLM, parent_id=s1.span_id,
                    usage=LLMUsage(prompt_tokens=100, completion_tokens=50, model="gpt-4o-mini", provider="openai"))  # noqa: E501
    s3 = _make_span(t.trace_id, "tool-call", SpanKind.TOOL, parent_id=s1.span_id,
                    tool_name="web_search", tool_args={"query": "test"})
    t.spans = [s1, s2, s3]
    t.finish(TraceStatus.COMPLETED)
    return t


@pytest.fixture
def failed_trace() -> Trace:
    t = Trace(name="failed-trace")
    s1 = _make_span(t.trace_id, "agent-step", SpanKind.AGENT)
    s2 = _make_span(t.trace_id, "llm-call", SpanKind.LLM, parent_id=s1.span_id,
                    usage=LLMUsage(prompt_tokens=200, completion_tokens=10, model="gpt-4o", provider="openai"))  # noqa: E501
    s3 = _make_span(t.trace_id, "tool-call", SpanKind.TOOL, parent_id=s1.span_id,
                    status=SpanStatus.ERROR, tool_name="file_read",
                    error="FileNotFoundError: config.yaml not found",
                    error_type="FileNotFoundError")
    t.spans = [s1, s2, s3]
    t.finish(TraceStatus.FAILED)
    return t


@pytest.fixture
def loop_trace() -> Trace:
    t = Trace(name="loop-trace")
    root = _make_span(t.trace_id, "agent", SpanKind.AGENT)
    spans = [root, *[
        _make_span(
            t.trace_id, f"search-{i}", SpanKind.TOOL,
            parent_id=root.span_id,
            tool_name="web_search",
            tool_args={"query": "same query every time"},
        )
        for i in range(5)
    ]]
    t.spans = spans
    t.finish(TraceStatus.FAILED)
    return t
