"""Unit tests for TraceStore (uses a temporary SQLite database)."""

from __future__ import annotations

from pathlib import Path

import pytest

from autopsyai.core.store import TraceStore
from autopsyai.models.trace import Trace


@pytest.fixture
async def store(tmp_path: Path) -> TraceStore:
    async with TraceStore(db_path=tmp_path / "test.db") as s:
        yield s  # type: ignore[misc]


class TestTraceStore:
    @pytest.mark.asyncio
    async def test_save_and_get_trace(self, tmp_path: Path, simple_trace: Trace) -> None:
        async with TraceStore(db_path=tmp_path / "db.sqlite") as store:
            await store.save_trace(simple_trace)
            loaded = await store.get_trace(simple_trace.trace_id)
        assert loaded is not None
        assert loaded.trace_id == simple_trace.trace_id
        assert loaded.name == simple_trace.name
        assert len(loaded.spans) == len(simple_trace.spans)

    @pytest.mark.asyncio
    async def test_get_nonexistent_returns_none(self, tmp_path: Path) -> None:
        async with TraceStore(db_path=tmp_path / "db.sqlite") as store:
            result = await store.get_trace("nonexistent-id")
        assert result is None

    @pytest.mark.asyncio
    async def test_list_traces(
        self, tmp_path: Path, simple_trace: Trace, failed_trace: Trace
    ) -> None:
        async with TraceStore(db_path=tmp_path / "db.sqlite") as store:
            await store.save_trace(simple_trace)
            await store.save_trace(failed_trace)
            traces = await store.list_traces()
        assert len(traces) == 2
        ids = {t["trace_id"] for t in traces}
        assert simple_trace.trace_id in ids
        assert failed_trace.trace_id in ids

    @pytest.mark.asyncio
    async def test_list_traces_filter_by_status(
        self, tmp_path: Path, simple_trace: Trace, failed_trace: Trace
    ) -> None:
        async with TraceStore(db_path=tmp_path / "db.sqlite") as store:
            await store.save_trace(simple_trace)
            await store.save_trace(failed_trace)
            completed = await store.list_traces(status="completed")
            failed = await store.list_traces(status="failed")
        assert len(completed) == 1
        assert len(failed) == 1

    @pytest.mark.asyncio
    async def test_delete_trace(self, tmp_path: Path, simple_trace: Trace) -> None:
        async with TraceStore(db_path=tmp_path / "db.sqlite") as store:
            await store.save_trace(simple_trace)
            deleted = await store.delete_trace(simple_trace.trace_id)
            found = await store.get_trace(simple_trace.trace_id)
        assert deleted is True
        assert found is None

    @pytest.mark.asyncio
    async def test_delete_nonexistent_returns_false(self, tmp_path: Path) -> None:
        async with TraceStore(db_path=tmp_path / "db.sqlite") as store:
            result = await store.delete_trace("ghost-id")
        assert result is False

    @pytest.mark.asyncio
    async def test_stats(self, tmp_path: Path, simple_trace: Trace) -> None:
        async with TraceStore(db_path=tmp_path / "db.sqlite") as store:
            await store.save_trace(simple_trace)
            s = await store.stats()
        assert s["traces"] == 1
        assert s["spans"] == 3

    @pytest.mark.asyncio
    async def test_spans_preserved_on_roundtrip(self, tmp_path: Path, simple_trace: Trace) -> None:
        async with TraceStore(db_path=tmp_path / "db.sqlite") as store:
            await store.save_trace(simple_trace)
            loaded = await store.get_trace(simple_trace.trace_id)
        assert loaded is not None
        original_ids = {s.span_id for s in simple_trace.spans}
        loaded_ids = {s.span_id for s in loaded.spans}
        assert original_ids == loaded_ids
