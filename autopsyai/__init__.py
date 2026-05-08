"""
autopsyai — Local-first agent run debugger.

Record every step of your LLM agent, replay failures frame-by-frame,
and get automated analysis of what went wrong and why.

Quick start::

    from autopsyai import Tracer, analyze
    from autopsyai.models import SpanKind

    tracer = Tracer()

    async def run():
        async with tracer.trace("my-agent") as trace:
            with tracer.span("llm-call", kind=SpanKind.LLM) as span:
                span.response_text = "Hello!"

        analysis = analyze(trace)
        for f in analysis.findings:
            print(f.code, f.message)
"""

from __future__ import annotations

__version__ = "0.1.0"
__author__ = "Kaparthy Reddy"
__license__ = "MIT"

from autopsyai.analyzers import analyze
from autopsyai.core.replay import TraceReplayer
from autopsyai.core.store import TraceStore
from autopsyai.core.tracer import Tracer
from autopsyai.integrations.raw_integration import trace_llm, trace_tool
from autopsyai.models import Span, SpanKind, SpanStatus, Trace, TraceStatus

__all__ = [
    "Span",
    "SpanKind",
    "SpanStatus",
    "Trace",
    "TraceReplayer",
    "TraceStatus",
    "TraceStore",
    "Tracer",
    "__version__",
    "analyze",
    "trace_llm",
    "trace_tool",
]
