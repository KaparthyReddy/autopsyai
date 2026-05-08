"""
Simple autopsyai example — trace a basic two-step agent without any LLM SDK.

Run with:
    python examples/simple_agent.py
"""

from __future__ import annotations

import asyncio

from autopsyai import Tracer, analyze
from autopsyai.models import SpanKind
from autopsyai.reporters import TerminalReporter


async def fake_llm_call(prompt: str) -> str:
    """Simulate an LLM call."""
    await asyncio.sleep(0.05)
    return f"Response to: {prompt}"


async def fake_tool_call(query: str) -> list[str]:
    """Simulate a web search tool."""
    await asyncio.sleep(0.02)
    return [f"Result 1 for {query}", f"Result 2 for {query}"]


async def main() -> None:
    tracer = Tracer()
    reporter = TerminalReporter()

    async with tracer.trace("simple-research-agent", tags=["example"]) as trace:
        with tracer.span("agent-loop", kind=SpanKind.AGENT):
            # Step 1: LLM decides what to search
            with tracer.span("decide-query", kind=SpanKind.LLM) as llm_span:
                response = await fake_llm_call("What should I search for?")
                llm_span.response_text = response
                llm_span.usage = None  # no real token counts in this example

            # Step 2: Tool call based on decision
            with tracer.span("web-search", kind=SpanKind.TOOL) as tool_span:
                tool_span.tool_name = "web_search"
                tool_span.tool_args = {"query": "autopsyai agent debugging"}
                results = await fake_tool_call("autopsyai agent debugging")
                tool_span.tool_result = results

            # Step 3: LLM synthesises answer
            with tracer.span("synthesise", kind=SpanKind.LLM) as synth_span:
                answer = await fake_llm_call(f"Synthesise: {results}")
                synth_span.response_text = answer

    # Display the trace
    reporter.report_trace(trace, show_io=True)

    # Analyze it
    analysis = analyze(trace)
    print()
    reporter.report_analysis(analysis)


if __name__ == "__main__":
    asyncio.run(main())
