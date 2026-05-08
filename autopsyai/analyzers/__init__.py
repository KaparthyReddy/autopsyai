from autopsyai.analyzers.base import AnalyzerRegistry, BaseAnalyzer
from autopsyai.analyzers.cost_analyzer import CostAnalyzer
from autopsyai.analyzers.failure_analyzer import FailureAnalyzer
from autopsyai.analyzers.latency_analyzer import LatencyAnalyzer
from autopsyai.analyzers.loop_detector import LoopDetector
from autopsyai.models.analysis import TraceAnalysis
from autopsyai.models.trace import Trace


def analyze(trace: Trace) -> TraceAnalysis:
    """
    Run all registered analyzers against a trace and return a full TraceAnalysis.

    This is the main entry point for the analysis layer::

        analysis = analyze(trace)
        for finding in analysis.findings:
            print(finding.code, finding.message)
    """
    result = TraceAnalysis(trace_id=trace.trace_id, trace_name=trace.name)
    for analyzer in AnalyzerRegistry.all():
        findings = analyzer.analyze(trace, result)
        result.findings.extend(findings)
    return result


__all__ = [
    "AnalyzerRegistry",
    "BaseAnalyzer",
    "CostAnalyzer",
    "FailureAnalyzer",
    "LatencyAnalyzer",
    "LoopDetector",
    "TraceAnalysis",
    "analyze",
]
