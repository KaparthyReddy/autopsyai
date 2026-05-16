"""JSON reporter — machine-readable trace and analysis export."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from autopsyai.models.analysis import TraceAnalysis
    from autopsyai.models.trace import Trace


class JSONReporter:
    """Serialises traces and analysis results to JSON."""

    SCHEMA_VERSION = 1

    def render_trace(self, trace: Trace, indent: int = 2) -> str:
        payload = {"schema_version": self.SCHEMA_VERSION, **trace.model_dump(mode="json")}
        return json.dumps(payload, indent=indent, ensure_ascii=False, default=str)

    def render_analysis(self, analysis: TraceAnalysis, indent: int = 2) -> str:
        payload = {"schema_version": self.SCHEMA_VERSION, **analysis.model_dump(mode="json")}
        return json.dumps(payload, indent=indent, ensure_ascii=False, default=str)

    def write_trace(self, trace: Trace, path: Path) -> None:
        Path(path).write_text(self.render_trace(trace), encoding="utf-8")

    def write_analysis(self, analysis: TraceAnalysis, path: Path) -> None:
        Path(path).write_text(self.render_analysis(analysis), encoding="utf-8")
