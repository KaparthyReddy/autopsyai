"""Abstract base analyzer and registry."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import ClassVar

from autopsyai.models.analysis import Finding, TraceAnalysis
from autopsyai.models.trace import Trace


class BaseAnalyzer(ABC):
    """All analyzers must subclass this."""

    analyzer_name: str

    @abstractmethod
    def analyze(self, trace: Trace, analysis: TraceAnalysis) -> list[Finding]:
        """
        Inspect the trace and return a list of findings.

        Analyzers are pure functions — they must not mutate the trace.
        They append findings to ``analysis`` via the returned list.
        """


class AnalyzerRegistry:
    """Maps analyzer names to instances."""

    _registry: ClassVar[dict[str, BaseAnalyzer]] = {}
    _bootstrapped: ClassVar[bool] = False

    @classmethod
    def _bootstrap(cls) -> None:
        if cls._bootstrapped:
            return
        cls._bootstrapped = True
        from autopsyai.analyzers.cost_analyzer import CostAnalyzer
        from autopsyai.analyzers.failure_analyzer import FailureAnalyzer
        from autopsyai.analyzers.latency_analyzer import LatencyAnalyzer
        from autopsyai.analyzers.loop_detector import LoopDetector

        for a in [FailureAnalyzer(), CostAnalyzer(), LatencyAnalyzer(), LoopDetector()]:
            cls._registry[a.analyzer_name] = a

    @classmethod
    def get(cls, name: str) -> BaseAnalyzer:
        cls._bootstrap()
        if name not in cls._registry:
            raise KeyError(f"No analyzer registered for '{name}'. Available: {list(cls._registry)}")
        return cls._registry[name]

    @classmethod
    def all(cls) -> list[BaseAnalyzer]:
        cls._bootstrap()
        return list(cls._registry.values())

    @classmethod
    def register(cls, analyzer: BaseAnalyzer) -> None:
        cls._registry[analyzer.analyzer_name] = analyzer
