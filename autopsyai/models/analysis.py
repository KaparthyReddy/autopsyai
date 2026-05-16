"""Analysis result models produced by the analyzer layer."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class Severity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class Finding(BaseModel):
    """A single finding from an analyzer."""

    code: str  # e.g. "LOOP_DETECTED", "HIGH_LATENCY_SPAN"
    severity: Severity
    message: str
    span_id: str | None = None  # The span this finding relates to (if any)
    metadata: dict[str, Any] = Field(default_factory=dict)


class CostBreakdown(BaseModel):
    """Per-model token cost breakdown for a trace."""

    model: str
    provider: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    estimated_cost_usd: float = 0.0


class LatencyBreakdown(BaseModel):
    """Latency stats for a category of spans."""

    kind: str
    count: int
    total_ms: float
    mean_ms: float
    max_ms: float
    slowest_span_id: str | None = None


class TraceAnalysis(BaseModel):
    """Full analysis result for a single trace."""

    trace_id: str
    trace_name: str
    findings: list[Finding] = Field(default_factory=list)
    cost_breakdown: list[CostBreakdown] = Field(default_factory=list)
    latency_breakdown: list[LatencyBreakdown] = Field(default_factory=list)
    total_cost_usd: float = 0.0
    total_tokens: int = 0
    loop_detected: bool = False
    failure_root_cause: str | None = None

    @property
    def critical_findings(self) -> list[Finding]:
        return [f for f in self.findings if f.severity == Severity.CRITICAL]

    @property
    def errors(self) -> list[Finding]:
        return [f for f in self.findings if f.severity in {Severity.ERROR, Severity.CRITICAL}]

    @property
    def has_issues(self) -> bool:
        return bool(self.errors)
