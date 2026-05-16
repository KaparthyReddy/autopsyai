"""Cost analyzer — breaks down token usage and estimates spend per model."""

from __future__ import annotations

from typing import TYPE_CHECKING

from autopsyai.analyzers.base import BaseAnalyzer
from autopsyai.models.analysis import CostBreakdown, Finding, Severity, TraceAnalysis

if TYPE_CHECKING:
    from autopsyai.models.trace import Trace

# Rough pricing per 1M tokens (input / output) as of mid-2024
# Format: {model_substring: (prompt_per_1m, completion_per_1m)}
_PRICING: dict[str, tuple[float, float]] = {
    "gpt-4o":            (5.00,   15.00),
    "gpt-4-turbo":       (10.00,  30.00),
    "gpt-4":             (30.00,  60.00),
    "gpt-3.5":           (0.50,   1.50),
    "claude-3-5-sonnet": (3.00,   15.00),
    "claude-3-5-haiku":  (0.80,   4.00),
    "claude-3-opus":     (15.00,  75.00),
    "claude-3-sonnet":   (3.00,   15.00),
    "claude-3-haiku":    (0.25,   1.25),
    "gemini-1.5-pro":    (3.50,   10.50),
    "gemini-1.5-flash":  (0.35,   1.05),
}

_HIGH_COST_THRESHOLD_USD = 0.10
_HIGH_TOKEN_THRESHOLD = 50_000


def _estimate_cost(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    model_lower = model.lower()
    for key, (p_price, c_price) in _PRICING.items():
        if key in model_lower:
            return (prompt_tokens * p_price + completion_tokens * c_price) / 1_000_000
    return 0.0


class CostAnalyzer(BaseAnalyzer):
    """
    Aggregates token usage per model and estimates total spend.

    Findings produced:
    - HIGH_TOTAL_COST   — trace exceeds $0.10 estimated cost
    - HIGH_TOKEN_COUNT  — trace exceeds 50k total tokens
    - EXPENSIVE_SPAN    — a single LLM span costs more than $0.05
    """

    analyzer_name = "cost"

    def analyze(self, trace: Trace, analysis: TraceAnalysis) -> list[Finding]:
        findings: list[Finding] = []
        model_buckets: dict[str, CostBreakdown] = {}

        for span in trace.llm_spans:
            if span.usage is None:
                continue
            key = f"{span.usage.provider}::{span.usage.model}"
            if key not in model_buckets:
                model_buckets[key] = CostBreakdown(
                    model=span.usage.model,
                    provider=span.usage.provider,
                )
            bucket = model_buckets[key]
            bucket.prompt_tokens += span.usage.prompt_tokens
            bucket.completion_tokens += span.usage.completion_tokens
            bucket.total_tokens += span.usage.total_tokens
            span_cost = _estimate_cost(
                span.usage.model,
                span.usage.prompt_tokens,
                span.usage.completion_tokens,
            )
            bucket.estimated_cost_usd += span_cost

            if span_cost > 0.05:  # noqa: PLR2004
                findings.append(Finding(
                    code="EXPENSIVE_SPAN",
                    severity=Severity.WARNING,
                    message=(
                        f"Span '{span.name}' cost ~${span_cost:.4f}"
                        f" ({span.usage.total_tokens} tokens)"
                    ),
                    span_id=span.span_id,
                    metadata={"cost_usd": span_cost, "tokens": span.usage.total_tokens},
                ))

        analysis.cost_breakdown = list(model_buckets.values())
        analysis.total_cost_usd = sum(b.estimated_cost_usd for b in model_buckets.values())
        analysis.total_tokens = sum(b.total_tokens for b in model_buckets.values())

        if analysis.total_cost_usd > _HIGH_COST_THRESHOLD_USD:
            findings.append(Finding(
                code="HIGH_TOTAL_COST",
                severity=Severity.WARNING,
                message=(
                    f"Trace cost ~${analysis.total_cost_usd:.4f}"
                    " — consider caching or cheaper models"
                ),
                metadata={"cost_usd": analysis.total_cost_usd},
            ))

        if analysis.total_tokens > _HIGH_TOKEN_THRESHOLD:
            findings.append(Finding(
                code="HIGH_TOKEN_COUNT",
                severity=Severity.WARNING,
                message=f"Trace used {analysis.total_tokens:,} tokens — check for context bloat",
                metadata={"total_tokens": analysis.total_tokens},
            ))

        return findings
