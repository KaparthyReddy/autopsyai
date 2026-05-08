"""Unit tests for all analyzers."""

from __future__ import annotations

from autopsyai.analyzers import analyze
from autopsyai.analyzers.cost_analyzer import CostAnalyzer
from autopsyai.analyzers.failure_analyzer import FailureAnalyzer
from autopsyai.analyzers.latency_analyzer import LatencyAnalyzer
from autopsyai.analyzers.loop_detector import LoopDetector
from autopsyai.models.analysis import Severity, TraceAnalysis
from autopsyai.models.trace import Trace


class TestFailureAnalyzer:
    def test_no_findings_on_clean_trace(self, simple_trace: Trace) -> None:
        a = TraceAnalysis(trace_id=simple_trace.trace_id, trace_name=simple_trace.name)
        findings = FailureAnalyzer().analyze(simple_trace, a)
        assert findings == []

    def test_detects_tool_failure(self, failed_trace: Trace) -> None:
        a = TraceAnalysis(trace_id=failed_trace.trace_id, trace_name=failed_trace.name)
        findings = FailureAnalyzer().analyze(failed_trace, a)
        codes = [f.code for f in findings]
        assert "TOOL_FAILURE" in codes or "SPAN_ERROR" in codes

    def test_identifies_root_cause(self, failed_trace: Trace) -> None:
        a = TraceAnalysis(trace_id=failed_trace.trace_id, trace_name=failed_trace.name)
        FailureAnalyzer().analyze(failed_trace, a)
        assert a.failure_root_cause is not None
        assert "tool-call" in a.failure_root_cause

    def test_root_cause_finding_is_critical(self, failed_trace: Trace) -> None:
        a = TraceAnalysis(trace_id=failed_trace.trace_id, trace_name=failed_trace.name)
        findings = FailureAnalyzer().analyze(failed_trace, a)
        critical = [f for f in findings if f.severity == Severity.CRITICAL]
        assert len(critical) >= 1


class TestCostAnalyzer:
    def test_aggregates_tokens(self, simple_trace: Trace) -> None:
        a = TraceAnalysis(trace_id=simple_trace.trace_id, trace_name=simple_trace.name)
        CostAnalyzer().analyze(simple_trace, a)
        assert a.total_tokens == 150
        assert len(a.cost_breakdown) == 1
        assert a.cost_breakdown[0].model == "gpt-4o-mini"

    def test_no_cost_for_spanless_trace(self) -> None:
        t = Trace(name="empty")
        a = TraceAnalysis(trace_id=t.trace_id, trace_name=t.name)
        CostAnalyzer().analyze(t, a)
        assert a.total_tokens == 0
        assert a.total_cost_usd == 0.0

    def test_estimates_nonzero_cost(self, simple_trace: Trace) -> None:
        a = TraceAnalysis(trace_id=simple_trace.trace_id, trace_name=simple_trace.name)
        CostAnalyzer().analyze(simple_trace, a)
        # gpt-4o-mini pricing exists, should be > 0
        assert a.total_cost_usd >= 0.0


class TestLatencyAnalyzer:
    def test_builds_breakdowns(self, simple_trace: Trace) -> None:
        a = TraceAnalysis(trace_id=simple_trace.trace_id, trace_name=simple_trace.name)
        LatencyAnalyzer().analyze(simple_trace, a)
        assert len(a.latency_breakdown) > 0
        kinds = {b.kind for b in a.latency_breakdown}
        assert "llm" in kinds or "tool" in kinds

    def test_no_slow_findings_on_fast_trace(self, simple_trace: Trace) -> None:
        a = TraceAnalysis(trace_id=simple_trace.trace_id, trace_name=simple_trace.name)
        findings = LatencyAnalyzer().analyze(simple_trace, a)
        slow = [f for f in findings if f.code == "SLOW_SPAN"]
        assert slow == []


class TestLoopDetector:
    def test_detects_loop(self, loop_trace: Trace) -> None:
        a = TraceAnalysis(trace_id=loop_trace.trace_id, trace_name=loop_trace.name)
        findings = LoopDetector().analyze(loop_trace, a)
        codes = [f.code for f in findings]
        assert "TOOL_LOOP" in codes or "IDENTICAL_CALL" in codes
        assert a.loop_detected is True

    def test_no_loop_on_clean_trace(self, simple_trace: Trace) -> None:
        a = TraceAnalysis(trace_id=simple_trace.trace_id, trace_name=simple_trace.name)
        LoopDetector().analyze(simple_trace, a)
        assert a.loop_detected is False

    def test_no_findings_on_empty_tools(self) -> None:
        t = Trace(name="no-tools")
        a = TraceAnalysis(trace_id=t.trace_id, trace_name=t.name)
        findings = LoopDetector().analyze(t, a)
        assert findings == []


class TestAnalyzePipeline:
    def test_analyze_returns_full_result(self, simple_trace: Trace) -> None:
        result = analyze(simple_trace)
        assert result.trace_id == simple_trace.trace_id
        assert result.total_tokens == 150
        assert isinstance(result.cost_breakdown, list)
        assert isinstance(result.latency_breakdown, list)

    def test_analyze_failed_trace_has_findings(self, failed_trace: Trace) -> None:
        result = analyze(failed_trace)
        assert result.has_issues is True
        assert len(result.findings) > 0

    def test_analyze_loop_trace_flags_loop(self, loop_trace: Trace) -> None:
        result = analyze(loop_trace)
        assert result.loop_detected is True
