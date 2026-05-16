"""
Raw integration — framework-agnostic function decorators.

Works with any Python code, no LangChain or provider SDK required.
The simplest way to add autopsyai tracing to any function.
"""

from __future__ import annotations

from collections.abc import Callable
import functools
from typing import Any, TypeVar

from autopsyai.core.tracer import Tracer
from autopsyai.models.span import SpanKind

F = TypeVar("F", bound=Callable[..., Any])


def trace_llm(
    name: str | None = None,
    tracer: Tracer | None = None,
) -> Callable[[F], F]:
    """
    Decorator — records an LLM call span.

    Usage::

        @trace_llm("my-llm-call")
        async def call_model(prompt: str) -> str:
            ...
    """
    _tracer = tracer or Tracer()

    def decorator(fn: F) -> F:
        span_name = name or fn.__name__

        @functools.wraps(fn)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            with _tracer.span(span_name, kind=SpanKind.LLM) as span:
                span.inputs = {"args": str(args)[:200], "kwargs": str(kwargs)[:200]}
                result = await fn(*args, **kwargs)
                if isinstance(result, str):
                    span.response_text = result[:500]
                span.outputs = {"result": str(result)[:200]}
                return result

        @functools.wraps(fn)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            with _tracer.span(span_name, kind=SpanKind.LLM) as span:
                span.inputs = {"args": str(args)[:200], "kwargs": str(kwargs)[:200]}
                result = fn(*args, **kwargs)
                if isinstance(result, str):
                    span.response_text = result[:500]
                span.outputs = {"result": str(result)[:200]}
                return result

        import asyncio

        if asyncio.iscoroutinefunction(fn):
            return async_wrapper  # type: ignore[return-value]
        return sync_wrapper  # type: ignore[return-value]

    return decorator


def trace_tool(
    name: str | None = None,
    tracer: Tracer | None = None,
) -> Callable[[F], F]:
    """
    Decorator — records a tool call span.

    Usage::

        @trace_tool("web-search")
        def search(query: str) -> list[str]:
            ...
    """
    _tracer = tracer or Tracer()

    def decorator(fn: F) -> F:
        span_name = name or fn.__name__

        @functools.wraps(fn)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            with _tracer.span(span_name, kind=SpanKind.TOOL) as span:
                span.tool_name = span_name
                span.tool_args = kwargs
                result = await fn(*args, **kwargs)
                span.tool_result = str(result)[:500]
                return result

        @functools.wraps(fn)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            with _tracer.span(span_name, kind=SpanKind.TOOL) as span:
                span.tool_name = span_name
                span.tool_args = kwargs
                result = fn(*args, **kwargs)
                span.tool_result = str(result)[:500]
                return result

        import asyncio

        if asyncio.iscoroutinefunction(fn):
            return async_wrapper  # type: ignore[return-value]
        return sync_wrapper  # type: ignore[return-value]

    return decorator
