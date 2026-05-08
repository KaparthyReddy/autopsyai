# autopsyai

> **Local-first agent run debugger — record, replay, and diagnose multi-step LLM agent failures.**

Your multi-step agent failed. Again. Somewhere between step 3 and step 7, something went wrong. Was it the tool call? The LLM's reasoning? A prompt that truncated? You have no idea.

`autopsyai` gives you a structured trace of every span, a replay engine to step through them, and automated analyzers that tell you exactly what went wrong and why.

[![PyPI](https://img.shields.io/pypi/v/autopsyai)](https://pypi.org/project/autopsyai/)
[![Python](https://img.shields.io/pypi/pyversions/autopsyai)](https://pypi.org/project/autopsyai/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![CI](https://github.com/KaparthyReddy/autopsyai/actions/workflows/ci.yml/badge.svg)](https://github.com/KaparthyReddy/autopsyai/actions)
[![mypy: strict](https://img.shields.io/badge/mypy-strict-blue)](https://mypy.readthedocs.io)
[![ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)

---

## The problem

Cloud-based observability tools (LangSmith, Arize, Weights & Biases) are great — but they require API keys, send your data to a third party, and cost money. For most developers iterating locally, that's overkill.

`autopsyai` is fully local. SQLite. No servers. No keys. No data leaves your machine.

---

## Features

- **Span-based tracer** — async-safe, context-variable-based tree builder. Works with any Python code.
- **4 integrations** — OpenAI, Anthropic, LangChain callback handler, and a raw decorator API for anything else
- **SQLite trace store** — WAL mode, foreign key constraints, indexed by kind/status
- **Replay engine** — step through any recorded trace frame-by-frame to find the failure path
- **4 analyzers** — failure pattern detection, token cost estimation, latency profiling, loop detection
- **3 reporters** — rich terminal timeline, self-contained HTML visualiser, JSON export
- **Zero infra** — SQLite only. Works offline. No accounts. No API keys.
- **Strict typing** — `mypy --strict` clean, `ruff` clean

---

## Install

```bash
pip install autopsyai

# With provider integrations
pip install "autopsyai[openai]"
pip install "autopsyai[anthropic]"
pip install "autopsyai[all]"
```

---

## Quickstart — 30 seconds

```python
import asyncio
from autopsyai import Tracer, analyze
from autopsyai.models import SpanKind
from autopsyai.reporters import TerminalReporter

tracer = Tracer()

async def main():
    async with tracer.trace("my-agent") as trace:
        with tracer.span("llm-call", kind=SpanKind.LLM) as span:
            span.response_text = await call_my_llm("What to do next?")

        with tracer.span("tool-call", kind=SpanKind.TOOL) as span:
            span.tool_name = "web_search"
            span.tool_result = await search("autopsyai")

    TerminalReporter().report_trace(trace)
    analysis = analyze(trace)
    TerminalReporter().report_analysis(analysis)

asyncio.run(main())
```

---

## Raw decorator API

For any function — no SDK required:

```python
from autopsyai import trace_llm, trace_tool

@trace_llm("my-model-call")
async def call_model(prompt: str) -> str:
    ...  # your LLM call here

@trace_tool("web-search")
def search(query: str) -> list[str]:
    ...  # your tool call here
```

---

## Replay engine

Step through a recorded trace to find the exact failure point:

```python
from autopsyai import TraceReplayer

replayer = TraceReplayer(trace)

# Print every frame
for frame in replayer.frames():
    indent = "  " * frame.depth
    status = "FAIL" if frame.span.failed else "OK"
    print(f"{indent}[{status}] {frame.span.name} ({frame.span.duration_ms:.0f}ms)")

# Jump straight to the root cause
first_fail = replayer.first_failure()
if first_fail:
    print(f"Root cause: {first_fail.span.name} — {first_fail.span.error}")

# Get the full ancestor chain to the failure
path = replayer.path_to_failure()
for frame in path:
    print(f"→ {frame.span.name}")
```

---

## Analyzers

| Analyzer | What it detects |
|---|---|
| `failure` | Error spans, classifies by type (tool/LLM/chain), identifies root cause |
| `cost` | Per-model token aggregation, spend estimation, expensive span detection |
| `latency` | Slow spans, latency outliers (>3x mean), total trace timing |
| `loop` | Consecutive tool repetition, identical call signatures, fixation patterns |

```python
from autopsyai import analyze

analysis = analyze(trace)
for finding in analysis.findings:
    print(f"[{finding.severity.value}] {finding.code}: {finding.message}")

print(f"Root cause: {analysis.failure_root_cause}")
print(f"Loop detected: {analysis.loop_detected}")
print(f"Total cost: ~${analysis.total_cost_usd:.5f}")
```

---

## CLI

```bash
# List all stored traces
autopsyai list

# Show a trace timeline
autopsyai show <trace-id>

# Show with I/O and analysis
autopsyai show <trace-id> --io --analyze

# Run analyzers standalone
autopsyai analyze <trace-id>

# Export to HTML or JSON
autopsyai export <trace-id> --format html --output report.html

# Database stats + health check
autopsyai doctor

# Delete failed traces
autopsyai clean --status failed --yes
```

---

## Project structure

```
autopsyai/
├── autopsyai/
│   ├── core/
│   │   ├── tracer.py          # Async-safe context-propagating tracer
│   │   ├── store.py           # SQLite trace store (WAL mode)
│   │   └── replay.py          # Frame-by-frame trace replayer
│   ├── analyzers/
│   │   ├── failure_analyzer.py
│   │   ├── cost_analyzer.py
│   │   ├── latency_analyzer.py
│   │   └── loop_detector.py
│   ├── integrations/
│   │   └── raw_integration.py  # @trace_llm / @trace_tool decorators
│   ├── reporters/
│   │   ├── terminal.py         # Rich timeline reporter
│   │   ├── html_reporter.py    # Self-contained HTML visualiser
│   │   └── json_reporter.py    # Machine-readable JSON
│   └── models/
│       ├── span.py             # Span, SpanKind, SpanStatus, LLMUsage
│       ├── trace.py            # Trace, TraceStatus
│       └── analysis.py         # TraceAnalysis, Finding, Severity
├── tests/
│   ├── unit/
│   │   ├── test_models.py      # 19 tests
│   │   ├── test_analyzers.py   # 15 tests
│   │   └── test_store.py       # 8 tests
│   └── integration/
│       └── test_tracer.py      # 7 tests
└── examples/
    └── simple_agent.py
```

---

## Roadmap

This is project 2 of 4. The end goal is a unified developer intelligence platform:

- **promptdiff** — prompt regression testing ✅ [shipped](https://github.com/KaparthyReddy/promptdiff)
- **autopsyai** — agent run debugger ← *you are here*
- **tokenlens** — LLM cost profiler (flamegraph-style token breakdown)
- **contextkit** — intelligent context budget manager

---

## Contributing

```bash
git clone https://github.com/KaparthyReddy/autopsyai
cd autopsyai
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[all,dev]"
pre-commit install
make test
```

---

## License

MIT — see [LICENSE](LICENSE).
