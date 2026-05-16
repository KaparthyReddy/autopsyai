"""Integration tests for Tracer — tests the full span recording loop."""

from __future__ import annotations

import pytest

from autopsyai.core.tracer import Tracer
from autopsyai.models.span import SpanKind, SpanStatus
from autopsyai.models.trace import TraceStatus


class TestTracer:
    @pytest.mark.asyncio
    async def test_trace_context_records_spans(self) -> None:
        tracer = Tracer()
        async with tracer.trace("test-run") as trace:
            with tracer.span("step-1", kind=SpanKind.LLM) as span:
                span.response_text = "hello"
            with tracer.span("step-2", kind=SpanKind.TOOL) as span:
                span.tool_name = "calculator"

        assert trace.status == TraceStatus.COMPLETED
        assert len(trace.spans) == 2
        assert trace.spans[0].name == "step-1"
        assert trace.spans[1].name == "step-2"

    @pytest.mark.asyncio
    async def test_span_parent_child_relationship(self) -> None:
        tracer = Tracer()
        async with tracer.trace("parent-child") as trace:
            with tracer.span("parent", kind=SpanKind.AGENT) as parent:
                with tracer.span("child", kind=SpanKind.LLM) as child:
                    child.response_text = "response"

        assert len(trace.spans) == 2
        child_span = trace.get_span(child.span_id)
        assert child_span is not None
        assert child_span.parent_id == parent.span_id

    @pytest.mark.asyncio
    async def test_failed_span_records_error(self) -> None:
        tracer = Tracer()
        trace = None
        span = None

        async def _run() -> None:
            nonlocal trace, span
            async with tracer.trace("error-run") as t:
                trace = t
                with tracer.span("bad-step") as s:
                    span = s
                    raise ValueError("intentional")

        with pytest.raises(ValueError, match="intentional"):
            await _run()

        assert trace is not None
        assert trace.status == TraceStatus.FAILED
        assert span is not None
        assert span.status == SpanStatus.ERROR
        assert span.error == "intentional"
        assert span.error_type == "ValueError"

    @pytest.mark.asyncio
    async def test_trace_completion_on_success(self) -> None:
        tracer = Tracer()
        async with tracer.trace("success-run") as t:
            with tracer.span("ok-step"):
                pass

        assert t.status == TraceStatus.COMPLETED
        assert t.finished_at is not None

    @pytest.mark.asyncio
    async def test_span_duration_is_positive(self) -> None:
        tracer = Tracer()
        async with tracer.trace("timing"):
            with tracer.span("measured") as span:
                import asyncio
                await asyncio.sleep(0.01)

        assert span.duration_ms > 0

    @pytest.mark.asyncio
    async def test_no_active_trace_raises(self) -> None:
        tracer = Tracer()
        with pytest.raises(RuntimeError, match="No active trace"), tracer.span("orphan"):
            pass

    @pytest.mark.asyncio
    async def test_current_trace_accessor(self) -> None:
        tracer = Tracer()
        assert Tracer.current_trace() is None
        async with tracer.trace("current-test") as trace:
            assert Tracer.current_trace() is trace
