"""
SQLite trace store — persists and retrieves traces and spans.

Uses WAL mode for concurrent writes. Each trace is stored as a JSON
blob with span-level indexing for fast lookups by trace_id, kind, and status.
"""

from __future__ import annotations

from datetime import datetime
import json
import logging
from pathlib import Path
import time
from typing import Any

import aiosqlite

from autopsyai.config import get_settings
from autopsyai.models.span import Span
from autopsyai.models.trace import Trace, TraceStatus

_log = logging.getLogger(__name__)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS traces (
    trace_id    TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    status      TEXT NOT NULL,
    started_at  TEXT NOT NULL,
    finished_at TEXT,
    tags        TEXT DEFAULT '[]',
    metadata    TEXT DEFAULT '{}',
    created_at  REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS spans (
    span_id    TEXT PRIMARY KEY,
    trace_id   TEXT NOT NULL REFERENCES traces(trace_id) ON DELETE CASCADE,
    parent_id  TEXT,
    name       TEXT NOT NULL,
    kind       TEXT NOT NULL,
    status     TEXT NOT NULL,
    started_at TEXT NOT NULL,
    ended_at   TEXT,
    data       TEXT NOT NULL,   -- full Span JSON
    created_at REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_spans_trace ON spans(trace_id);
CREATE INDEX IF NOT EXISTS idx_spans_kind  ON spans(kind);
CREATE INDEX IF NOT EXISTS idx_spans_status ON spans(status);
CREATE INDEX IF NOT EXISTS idx_traces_status ON traces(status);
"""


class TraceStore:
    """
    Async SQLite-backed store for traces and spans.

    Use as an async context manager::

        async with TraceStore() as store:
            await store.save_trace(trace)
            traces = await store.list_traces()
    """

    def __init__(self, db_path: Path | None = None) -> None:
        self._db_path = (db_path or get_settings().db_path).expanduser().resolve()
        self._conn: aiosqlite.Connection | None = None

    async def __aenter__(self) -> TraceStore:
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = await aiosqlite.connect(self._db_path)
        await self._conn.execute("PRAGMA journal_mode=WAL;")
        await self._conn.execute("PRAGMA foreign_keys=ON;")
        await self._conn.executescript(_SCHEMA)
        await self._conn.commit()
        return self

    async def __aexit__(self, *_: Any) -> None:
        if self._conn:
            await self._conn.close()
            self._conn = None

    # ── Write ─────────────────────────────────────────────────────────────────

    async def save_trace(self, trace: Trace) -> None:
        """Upsert a trace and all its spans."""
        assert self._conn is not None
        now = time.time()
        await self._conn.execute(
            """INSERT OR REPLACE INTO traces
               (trace_id, name, status, started_at, finished_at, tags, metadata, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                trace.trace_id,
                trace.name,
                trace.status.value,
                trace.started_at.isoformat(),
                trace.finished_at.isoformat() if trace.finished_at else None,
                json.dumps(trace.tags),
                json.dumps(trace.metadata),
                now,
            ),
        )
        for span in trace.spans:
            await self._upsert_span(span, now)
        await self._conn.commit()

    async def _upsert_span(self, span: Span, now: float) -> None:
        assert self._conn is not None
        await self._conn.execute(
            """INSERT OR REPLACE INTO spans
               (span_id, trace_id, parent_id, name, kind, status,
                started_at, ended_at, data, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                span.span_id,
                span.trace_id,
                span.parent_id,
                span.name,
                span.kind.value,
                span.status.value,
                span.started_at.isoformat(),
                span.ended_at.isoformat() if span.ended_at else None,
                span.model_dump_json(),
                now,
            ),
        )

    async def delete_trace(self, trace_id: str) -> bool:
        """Delete a trace and all its spans. Returns True if found."""
        assert self._conn is not None
        async with self._conn.execute(
            "DELETE FROM traces WHERE trace_id = ?", (trace_id,)
        ) as cur:
            deleted = cur.rowcount > 0
        await self._conn.commit()
        return deleted

    # ── Read ──────────────────────────────────────────────────────────────────

    async def get_trace(self, trace_id: str) -> Trace | None:
        """Load a full trace including all its spans."""
        assert self._conn is not None
        async with self._conn.execute(
            "SELECT name, status, started_at, finished_at, tags, metadata "
            "FROM traces WHERE trace_id = ?",
            (trace_id,),
        ) as cur:
            row = await cur.fetchone()
        if row is None:
            return None

        name, status, started_at, finished_at, tags, metadata = row
        spans = await self._load_spans(trace_id)

        return Trace(
            trace_id=trace_id,
            name=name,
            status=TraceStatus(status),
            started_at=datetime.fromisoformat(started_at),
            finished_at=datetime.fromisoformat(finished_at) if finished_at else None,
            spans=spans,
            tags=json.loads(tags),
            metadata=json.loads(metadata),
        )

    async def _load_spans(self, trace_id: str) -> list[Span]:
        assert self._conn is not None
        async with self._conn.execute(
            "SELECT data FROM spans WHERE trace_id = ? ORDER BY started_at ASC",
            (trace_id,),
        ) as cur:
            rows = await cur.fetchall()
        return [Span.model_validate_json(row[0]) for row in rows]

    async def list_traces(
        self,
        limit: int = 50,
        status: str | None = None,
        tag: str | None = None,
    ) -> list[dict[str, Any]]:
        """Return a summary list of traces (no spans loaded)."""
        assert self._conn is not None
        query = "SELECT trace_id, name, status, started_at, finished_at FROM traces"
        params: list[Any] = []
        conditions: list[str] = []
        if status:
            conditions.append("status = ?")
            params.append(status)
        if tag:
            conditions.append("tags LIKE ?")
            params.append(f'%"{tag}"%')
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        async with self._conn.execute(query, params) as cur:
            rows = await cur.fetchall()
        return [
            {
                "trace_id": r[0],
                "name": r[1],
                "status": r[2],
                "started_at": r[3],
                "finished_at": r[4],
            }
            for r in rows
        ]

    async def stats(self) -> dict[str, Any]:
        """Return store-level statistics."""
        assert self._conn is not None
        async with self._conn.execute("SELECT COUNT(*) FROM traces") as cur:
            trace_count: int = (await cur.fetchone())[0]  # type: ignore[index]
        async with self._conn.execute("SELECT COUNT(*) FROM spans") as cur:
            span_count: int = (await cur.fetchone())[0]  # type: ignore[index]
        return {"traces": trace_count, "spans": span_count, "db": str(self._db_path)}
