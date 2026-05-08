"""Span — a single recorded step in an agent run."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
import uuid

from pydantic import BaseModel, Field, computed_field


class SpanKind(str, Enum):
    LLM = "llm"
    TOOL = "tool"
    AGENT = "agent"
    CHAIN = "chain"
    RETRIEVAL = "retrieval"
    CUSTOM = "custom"


class SpanStatus(str, Enum):
    OK = "ok"
    ERROR = "error"
    TIMEOUT = "timeout"


class LLMUsage(BaseModel):
    """Token usage for a single LLM call."""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    model: str = ""
    provider: str = ""

    @computed_field  # type: ignore[prop-decorator]
    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens


class Span(BaseModel):
    """
    A single recorded step in an agent trace.

    Spans form a tree via parent_id. A root span has parent_id=None.
    Every agent action, LLM call, tool invocation, and retrieval step
    is captured as a Span and stored in the trace store.
    """

    span_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    trace_id: str
    parent_id: str | None = None
    name: str
    kind: SpanKind = SpanKind.CUSTOM
    status: SpanStatus = SpanStatus.OK
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    ended_at: datetime | None = None

    # Inputs / outputs
    inputs: dict[str, Any] = Field(default_factory=dict)
    outputs: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None
    error_type: str | None = None

    # LLM-specific (populated for SpanKind.LLM)
    usage: LLMUsage | None = None
    messages: list[dict[str, str]] = Field(default_factory=list)
    response_text: str = ""

    # Tool-specific (populated for SpanKind.TOOL)
    tool_name: str = ""
    tool_args: dict[str, Any] = Field(default_factory=dict)
    tool_result: Any = None

    # User-attached metadata
    attributes: dict[str, Any] = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def duration_ms(self) -> float:
        if self.ended_at is None:
            return 0.0
        return (self.ended_at - self.started_at).total_seconds() * 1000

    @computed_field  # type: ignore[prop-decorator]
    @property
    def is_root(self) -> bool:
        return self.parent_id is None

    @computed_field  # type: ignore[prop-decorator]
    @property
    def failed(self) -> bool:
        return self.status != SpanStatus.OK

    def end(
        self,
        status: SpanStatus = SpanStatus.OK,
        error: str | None = None,
        error_type: str | None = None,
    ) -> None:
        """Mark the span as complete."""
        self.ended_at = datetime.now(timezone.utc)
        self.status = status
        if error:
            self.error = error
        if error_type:
            self.error_type = error_type
