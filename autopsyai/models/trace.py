"""Trace — a full agent run session containing all spans."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
import uuid

from pydantic import BaseModel, Field, computed_field

from autopsyai.models.span import Span, SpanKind


class TraceStatus(str, Enum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class Trace(BaseModel):
    """
    A complete agent run — a named session containing all recorded spans.

    Spans are stored flat and linked by parent_id. Use root_spans() and
    children_of() to reconstruct the hierarchy for display or analysis.
    """

    trace_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    status: TraceStatus = TraceStatus.RUNNING
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    finished_at: datetime | None = None
    spans: list[Span] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def duration_ms(self) -> float:
        if self.finished_at is None:
            return 0.0
        return (self.finished_at - self.started_at).total_seconds() * 1000

    @computed_field  # type: ignore[prop-decorator]
    @property
    def span_count(self) -> int:
        return len(self.spans)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def failed_spans(self) -> list[Span]:
        return [s for s in self.spans if s.failed]

    @computed_field  # type: ignore[prop-decorator]
    @property
    def llm_spans(self) -> list[Span]:
        return [s for s in self.spans if s.kind == SpanKind.LLM]

    @computed_field  # type: ignore[prop-decorator]
    @property
    def tool_spans(self) -> list[Span]:
        return [s for s in self.spans if s.kind == SpanKind.TOOL]

    @computed_field  # type: ignore[prop-decorator]
    @property
    def total_tokens(self) -> int:
        return sum(s.usage.total_tokens for s in self.llm_spans if s.usage)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def total_prompt_tokens(self) -> int:
        return sum(s.usage.prompt_tokens for s in self.llm_spans if s.usage)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def total_completion_tokens(self) -> int:
        return sum(s.usage.completion_tokens for s in self.llm_spans if s.usage)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def succeeded(self) -> bool:
        return self.status == TraceStatus.COMPLETED

    def root_spans(self) -> list[Span]:
        """Return top-level spans (those with no parent)."""
        return [s for s in self.spans if s.is_root]

    def children_of(self, span_id: str) -> list[Span]:
        """Return all direct children of a given span."""
        return [s for s in self.spans if s.parent_id == span_id]

    def get_span(self, span_id: str) -> Span | None:
        """Look up a span by ID."""
        return next((s for s in self.spans if s.span_id == span_id), None)

    def finish(self, status: TraceStatus = TraceStatus.COMPLETED) -> None:
        """Mark the trace as finished."""
        self.status = status
        self.finished_at = datetime.now(timezone.utc)
