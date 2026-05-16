"""Loop detector — finds agents stuck in repetitive cycles."""

from __future__ import annotations

from collections import Counter
from typing import TYPE_CHECKING

from autopsyai.analyzers.base import BaseAnalyzer
from autopsyai.models.analysis import Finding, Severity, TraceAnalysis

if TYPE_CHECKING:
    from autopsyai.models.trace import Trace

_REPEAT_THRESHOLD = 3  # same tool called 3+ times in a row = likely loop
_SAME_INPUT_THRESHOLD = 2  # same tool called with identical args 2+ times = definite loop


class LoopDetector(BaseAnalyzer):
    """
    Detects repetitive agent behaviour patterns that indicate infinite loops.

    Patterns detected:
    - TOOL_LOOP          — same tool called 3+ consecutive times
    - IDENTICAL_CALL     — same tool called with same args 2+ times
    - HIGH_REPETITION    — any single tool makes up >60% of all tool calls
    """

    analyzer_name = "loop"

    def analyze(self, trace: Trace, analysis: TraceAnalysis) -> list[Finding]:
        findings: list[Finding] = []
        tool_spans = trace.tool_spans

        if not tool_spans:
            return findings

        # Check for consecutive repetitions
        max_consecutive = 1
        current_run = 1
        loop_tool: str | None = None

        for i in range(1, len(tool_spans)):
            if tool_spans[i].tool_name == tool_spans[i - 1].tool_name:
                current_run += 1
                if current_run > max_consecutive:
                    max_consecutive = current_run
                    loop_tool = tool_spans[i].tool_name
            else:
                current_run = 1

        if max_consecutive >= _REPEAT_THRESHOLD:
            analysis.loop_detected = True
            findings.append(
                Finding(
                    code="TOOL_LOOP",
                    severity=Severity.CRITICAL,
                    message=(
                        f"Tool '{loop_tool}' called {max_consecutive} times consecutively — "
                        f"agent is likely stuck in a loop"
                    ),
                    metadata={"tool": loop_tool, "consecutive_calls": max_consecutive},
                )
            )

        # Check for identical inputs (same tool + same args)
        call_signatures: Counter[str] = Counter()
        for span in tool_spans:
            import json

            sig = f"{span.tool_name}::{json.dumps(span.tool_args, sort_keys=True)}"
            call_signatures[sig] += 1

        for sig, count in call_signatures.items():
            if count >= _SAME_INPUT_THRESHOLD:
                tool_name = sig.split("::")[0]
                analysis.loop_detected = True
                findings.append(
                    Finding(
                        code="IDENTICAL_CALL",
                        severity=Severity.ERROR,
                        message=(
                            f"Tool '{tool_name}' called {count}x with identical arguments — "
                            f"no state change between calls"
                        ),
                        metadata={"tool": tool_name, "call_count": count},
                    )
                )

        # Check for high repetition of a single tool
        tool_counts: Counter[str] = Counter(s.tool_name for s in tool_spans)
        total = len(tool_spans)
        for tool_name, count in tool_counts.most_common(3):
            ratio = count / total
            if ratio > 0.6 and total > 4:  # noqa: PLR2004
                findings.append(
                    Finding(
                        code="HIGH_REPETITION",
                        severity=Severity.WARNING,
                        message=(
                            f"Tool '{tool_name}' accounts for {ratio:.0%} of all tool calls "
                            f"({count}/{total}) — possible fixation"
                        ),
                        metadata={"tool": tool_name, "ratio": ratio, "count": count},
                    )
                )

        return findings
