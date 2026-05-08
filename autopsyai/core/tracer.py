"""
Tracer — the central recording engine for autopsyai.

Provides an async-safe, context-variable-based span tree builder.
Every integration (OpenAI, Anthropic, LangChain, raw decorator) funnels
through here to record spans into the active trace.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator, Generator
from contextlib import asynccontextmanager, contextmanager
import contextvars
import logging
from typing import Any, ClassVar

from autopsyai.core.store import TraceStore
from autopsyai.models.span import Span, SpanKind, SpanStatus
from autopsyai.models.trace import Trace, TraceStatus

_log = logging.getLogger(__name__)

# Context vars — async-safe, propagated into subtasks automatically
_active_trace: contextvars.ContextVar[Trace | None] = contextvars.ContextVar(
    "active_trace", default=None
)
_active_span: contextvars.ContextVar[Span | None] = contextvars.ContextVar(
    "active_span", default=None
)


class Tracer:
    """
    Central tracing engine.

    Usage — as async context manager::

        async with Tracer.start("my-agent-run") as tracer:
            with tracer.span("llm-call", kind=SpanKind.LLM) as span:
                response = await client.chat(...)
                span.response_text = response.content

    Usage — manual::

        tracer = Tracer()
        trace = tracer.begin("my-run")
        span = tracer.start_span("step-1")
        # ... do work ...
        tracer.end_span(span)
        await tracer.flush()
    """

    _instances: ClassVar[dict[str, Tracer]] = {}

    def __init__(self, store: TraceStore | None = None) -> None:
        self._store = store
        self._trace: Trace | None = None

    # ── High-level async context manager API ──────────────────────────────────

    @asynccontextmanager
    async def trace(
        self,
        name: str,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AsyncGenerator[Trace, None]:
        """
        Start a new trace and yield it. Saves to store on exit.

        Example::

            async with tracer.trace("search-agent") as t:
                ...  # all spans recorded here belong to t
        """
        trace = Trace(
            name=name,
            tags=tags or [],
            metadata=metadata or {},
        )
        self._trace = trace
        token_trace = _active_trace.set(trace)
        try:
            yield trace
            trace.finish(TraceStatus.COMPLETED)
        except Exception as exc:
            trace.finish(TraceStatus.FAILED)
            _log.debug("Trace %s failed: %s", trace.trace_id, exc)
            raise
        finally:
            _active_trace.reset(token_trace)
            if self._store:
                await self._store.save_trace(trace)

    # ── Span context manager ──────────────────────────────────────────────────

    @contextmanager
    def span(
        self,
        name: str,
        kind: SpanKind = SpanKind.CUSTOM,
        attributes: dict[str, Any] | None = None,
    ) -> Generator[Span, None, None]:
        """
        Start a child span within the active trace.

        Automatically resolves trace_id and parent_id from context vars.

        Example::

            with tracer.span("tool-call", kind=SpanKind.TOOL) as s:
                s.tool_name = "web_search"
                result = search(query)
                s.tool_result = result
        """
        trace = _active_trace.get()
        if trace is None:
            raise RuntimeError(
                "No active trace. Start a trace with `async with tracer.trace(...)`."
            )

        parent = _active_span.get()
        span = Span(
            trace_id=trace.trace_id,
            parent_id=parent.span_id if parent else None,
            name=name,
            kind=kind,
            attributes=attributes or {},
        )
        trace.spans.append(span)
        token_span = _active_span.set(span)

        try:
            yield span
            if not span.ended_at:
                span.end(SpanStatus.OK)
        except Exception as exc:
            if not span.ended_at:
                span.end(
                    status=SpanStatus.ERROR,
                    error=str(exc),
                    error_type=type(exc).__name__,
                )
            raise
        finally:
            _active_span.reset(token_span)

    # ── Manual API ────────────────────────────────────────────────────────────

    def begin(
        self,
        name: str,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Trace:
        """Create and activate a new trace without a context manager."""
        trace = Trace(name=name, tags=tags or [], metadata=metadata or {})
        self._trace = trace
        _active_trace.set(trace)
        return trace

    def start_span(
        self,
        name: str,
        kind: SpanKind = SpanKind.CUSTOM,
        parent_id: str | None = None,
    ) -> Span:
        """Manually start a span. You must call end_span() when done."""
        trace = _active_trace.get()
        if trace is None:
            raise RuntimeError("No active trace. Call begin() first.")
        parent = _active_span.get()
        span = Span(
            trace_id=trace.trace_id,
            parent_id=parent_id or (parent.span_id if parent else None),
            name=name,
            kind=kind,
        )
        trace.spans.append(span)
        _active_span.set(span)
        return span

    def end_span(
        self,
        span: Span,
        status: SpanStatus = SpanStatus.OK,
        error: str | None = None,
    ) -> None:
        """Manually end a span."""
        span.end(status=status, error=error)

    async def flush(self) -> None:
        """Persist the current trace to the store (if store is configured)."""
        trace = _active_trace.get() or self._trace
        if trace and self._store:
            await self._store.save_trace(trace)

    # ── Current context accessors ─────────────────────────────────────────────

    @staticmethod
    def current_trace() -> Trace | None:
        return _active_trace.get()

    @staticmethod
    def current_span() -> Span | None:
        return _active_span.get()
