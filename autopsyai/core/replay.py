"""
Replay engine — step through a recorded trace for debugging.

Allows developers to re-examine each span in sequence, inspect inputs/outputs,
and understand exactly where and why an agent run went wrong.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from autopsyai.models.span import Span
    from autopsyai.models.trace import Trace

_log = logging.getLogger(__name__)


@dataclass
class ReplayFrame:
    """A single frame in a trace replay — one span and its context."""

    index: int
    span: Span
    depth: int  # nesting depth in the span tree
    children: list[Span] = field(default_factory=list)
    siblings_before: int = 0
    siblings_after: int = 0


class TraceReplayer:
    """
    Steps through a recorded trace span-by-span.

    Usage::

        replayer = TraceReplayer(trace)
        for frame in replayer.frames():
            print(f"[{frame.index}] {frame.span.name} ({frame.span.duration_ms:.0f}ms)")
            if frame.span.failed:
                print(f"  ERROR: {frame.span.error}")
    """

    def __init__(self, trace: Trace) -> None:
        self.trace = trace
        self._frames: list[ReplayFrame] = []
        self._built = False

    def _build(self) -> None:
        if self._built:
            return
        self._frames = list(self._walk(None, depth=0))
        self._built = True

    def _walk(self, parent_id: str | None, depth: int) -> list[ReplayFrame]:
        children = [s for s in self.trace.spans if s.parent_id == parent_id]
        frames: list[ReplayFrame] = []
        for i, span in enumerate(children):
            child_spans = [s for s in self.trace.spans if s.parent_id == span.span_id]
            frames.append(
                ReplayFrame(
                    index=len(frames),
                    span=span,
                    depth=depth,
                    children=child_spans,
                    siblings_before=i,
                    siblings_after=len(children) - i - 1,
                )
            )
            frames.extend(self._walk(span.span_id, depth + 1))
        # Re-index after full build
        for j, f in enumerate(frames):
            f.index = j
        return frames

    def frames(self) -> list[ReplayFrame]:
        """Return all frames in DFS order (root → leaves)."""
        self._build()
        return self._frames

    def frame_at(self, index: int) -> ReplayFrame:
        """Get a specific frame by index."""
        self._build()
        if index < 0 or index >= len(self._frames):
            raise IndexError(f"Frame index {index} out of range (0-{len(self._frames) - 1})")
        return self._frames[index]

    def failure_frames(self) -> list[ReplayFrame]:
        """Return only frames where the span failed or errored."""
        return [f for f in self.frames() if f.span.failed]

    def first_failure(self) -> ReplayFrame | None:
        """Return the first frame that failed — the likely root cause."""
        failures = self.failure_frames()
        return failures[0] if failures else None

    def summary(self) -> dict[str, Any]:
        """Return a concise summary of the replay."""
        frames = self.frames()
        failures = self.failure_frames()
        return {
            "trace_id": self.trace.trace_id,
            "name": self.trace.name,
            "total_frames": len(frames),
            "failures": len(failures),
            "first_failure": failures[0].span.name if failures else None,
            "first_failure_error": failures[0].span.error if failures else None,
            "duration_ms": self.trace.duration_ms,
            "total_tokens": self.trace.total_tokens,
        }

    def path_to_failure(self) -> list[ReplayFrame]:
        """
        Return the ancestor chain from root to the first failing span.
        Useful for understanding the causal path to a failure.
        """
        first = self.first_failure()
        if first is None:
            return []

        path: list[ReplayFrame] = [first]
        current_id = first.span.parent_id
        frame_by_span = {f.span.span_id: f for f in self.frames()}

        while current_id is not None:
            parent_frame = frame_by_span.get(current_id)
            if parent_frame is None:
                break
            path.insert(0, parent_frame)
            current_id = parent_frame.span.parent_id

        return path
