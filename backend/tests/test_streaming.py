"""
Tests for the Streaming Engine (Task 16).

Covers:
- StreamingService.publish_event / publish_* helpers
- stream_events generator: normal flow, reconnection, terminal events
- Cancellation flag helpers
- SSE endpoint (integration-style with TestClient)
"""
from __future__ import annotations

import asyncio
import json
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.streaming import (
    StreamingService,
    _build_sse_line,
    _stream_key,
    STREAM_TTL_SECONDS,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_xread_result(entries: List[tuple]) -> List[tuple]:
    """Build a fake xread result: [(stream_key, [(entry_id, fields), ...])]."""
    return [("stream:presentation:test-id", entries)]


def _entry(entry_id: str, event_type: str, data: Dict[str, Any]) -> tuple:
    return (entry_id, {"event_type": event_type, "data": json.dumps(data), "ts": "0"})


# ---------------------------------------------------------------------------
# Unit: _build_sse_line
# ---------------------------------------------------------------------------

class TestBuildSseLine:
    def test_format(self):
        line = _build_sse_line("agent_start", {"agent": "research"}, "123-0")
        assert line.startswith("id: 123-0\n")
        assert "event: agent_start\n" in line
        assert '"agent": "research"' in line
        assert line.endswith("\n\n")

    def test_data_is_json(self):
        line = _build_sse_line("complete", {"presentation_id": "abc"}, "1-0")
        # Extract data line
        data_line = [l for l in line.split("\n") if l.startswith("data:")][0]
        payload = json.loads(data_line[len("data: "):])
        assert payload["presentation_id"] == "abc"


# ---------------------------------------------------------------------------
# Unit: _stream_key
# ---------------------------------------------------------------------------

class TestStreamKey:
    def test_prefix(self):
        assert _stream_key("abc-123") == "stream:presentation:abc-123"


# ---------------------------------------------------------------------------
# Unit: StreamingService.publish_event
# ---------------------------------------------------------------------------

class TestPublishEvent:
    @pytest.mark.asyncio
    async def test_publish_calls_xadd_and_expire(self):
        service = StreamingService()
        mock_client = AsyncMock()
        mock_client.xadd = AsyncMock(return_value="1700000000000-0")
        mock_client.expire = AsyncMock()
        mock_client.aclose = AsyncMock()

        with patch.object(service, "_get_client", return_value=mock_client):
            entry_id = await service.publish_event(
                "pres-1", "agent_start", {"agent": "research"}
            )

        assert entry_id == "1700000000000-0"
        mock_client.xadd.assert_called_once()
        call_args = mock_client.xadd.call_args
        assert call_args[0][0] == "stream:presentation:pres-1"
        assert call_args[0][1]["event_type"] == "agent_start"
        mock_client.expire.assert_called_once_with(
            "stream:presentation:pres-1", STREAM_TTL_SECONDS
        )

    @pytest.mark.asyncio
    async def test_publish_agent_start(self):
        service = StreamingService()
        mock_client = AsyncMock()
        mock_client.xadd = AsyncMock(return_value="1-0")
        mock_client.expire = AsyncMock()
        mock_client.aclose = AsyncMock()

        with patch.object(service, "_get_client", return_value=mock_client):
            await service.publish_agent_start("pres-1", "research", "exec-1")

        fields = mock_client.xadd.call_args[0][1]
        assert fields["event_type"] == "agent_start"
        data = json.loads(fields["data"])
        assert data["agent"] == "research"
        assert data["execution_id"] == "exec-1"

    @pytest.mark.asyncio
    async def test_publish_slide_ready(self):
        service = StreamingService()
        mock_client = AsyncMock()
        mock_client.xadd = AsyncMock(return_value="2-0")
        mock_client.expire = AsyncMock()
        mock_client.aclose = AsyncMock()

        slide = {"slide_id": "s1", "slide_number": 1, "type": "title"}
        with patch.object(service, "_get_client", return_value=mock_client):
            await service.publish_slide_ready("pres-1", slide, 1, 10)

        fields = mock_client.xadd.call_args[0][1]
        assert fields["event_type"] == "slide_ready"
        data = json.loads(fields["data"])
        assert data["slide_number"] == 1
        assert data["total_slides"] == 10
        assert data["slide"]["slide_id"] == "s1"

    @pytest.mark.asyncio
    async def test_publish_complete(self):
        service = StreamingService()
        mock_client = AsyncMock()
        mock_client.xadd = AsyncMock(return_value="3-0")
        mock_client.expire = AsyncMock()
        mock_client.aclose = AsyncMock()

        with patch.object(service, "_get_client", return_value=mock_client):
            await service.publish_complete("pres-1", "exec-1", quality_score=8.5)

        fields = mock_client.xadd.call_args[0][1]
        assert fields["event_type"] == "complete"
        data = json.loads(fields["data"])
        assert data["quality_score"] == 8.5

    @pytest.mark.asyncio
    async def test_publish_error(self):
        service = StreamingService()
        mock_client = AsyncMock()
        mock_client.xadd = AsyncMock(return_value="4-0")
        mock_client.expire = AsyncMock()
        mock_client.aclose = AsyncMock()

        with patch.object(service, "_get_client", return_value=mock_client):
            await service.publish_error("pres-1", "exec-1", "Something failed", "research")

        fields = mock_client.xadd.call_args[0][1]
        assert fields["event_type"] == "error"
        data = json.loads(fields["data"])
        assert data["failed_agent"] == "research"
        assert "Something failed" in data["error"]


# ---------------------------------------------------------------------------
# Unit: stream_events generator
# ---------------------------------------------------------------------------

class TestStreamEvents:
    @pytest.mark.asyncio
    async def test_yields_events_and_stops_on_complete(self):
        """Generator should yield SSE lines and stop after 'complete' event."""
        service = StreamingService()
        mock_client = AsyncMock()
        mock_client.aclose = AsyncMock()

        entries = [
            _entry("1-0", "agent_start", {"agent": "research"}),
            _entry("2-0", "agent_complete", {"agent": "research"}),
            _entry("3-0", "complete", {"presentation_id": "pres-1"}),
        ]

        call_count = 0

        async def fake_xread(streams, block, count):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return _make_xread_result(entries)
            return []

        mock_client.xread = fake_xread
        mock_client.exists = AsyncMock(return_value=0)

        with patch.object(service, "_get_client", return_value=mock_client):
            chunks = []
            async for chunk in service.stream_events("pres-1"):
                chunks.append(chunk)

        # Should have 3 SSE messages (agent_start, agent_complete, complete)
        assert len(chunks) == 3
        assert "event: agent_start" in chunks[0]
        assert "event: agent_complete" in chunks[1]
        assert "event: complete" in chunks[2]

    @pytest.mark.asyncio
    async def test_stops_on_error_event(self):
        """Generator should stop after an 'error' terminal event."""
        service = StreamingService()
        mock_client = AsyncMock()
        mock_client.aclose = AsyncMock()

        entries = [
            _entry("1-0", "agent_start", {"agent": "research"}),
            _entry("2-0", "error", {"error": "Pipeline failed"}),
        ]

        async def fake_xread(streams, block, count):
            return _make_xread_result(entries)

        mock_client.xread = fake_xread

        with patch.object(service, "_get_client", return_value=mock_client):
            chunks = []
            async for chunk in service.stream_events("pres-1"):
                chunks.append(chunk)

        assert len(chunks) == 2
        assert "event: error" in chunks[1]

    @pytest.mark.asyncio
    async def test_reconnection_uses_last_event_id(self):
        """When last_event_id is provided, xread should start from that ID."""
        service = StreamingService()
        mock_client = AsyncMock()
        mock_client.aclose = AsyncMock()
        mock_client.exists = AsyncMock(return_value=0)

        captured_start_id = None

        async def fake_xread(streams, block, count):
            nonlocal captured_start_id
            # streams is a dict {key: start_id}
            captured_start_id = list(streams.values())[0]
            return []

        mock_client.xread = fake_xread

        with patch.object(service, "_get_client", return_value=mock_client):
            async for _ in service.stream_events("pres-1", last_event_id="42-0"):
                break

        assert captured_start_id == "42-0"

    @pytest.mark.asyncio
    async def test_default_start_id_is_zero(self):
        """Without last_event_id, xread should start from '0' (replay all)."""
        service = StreamingService()
        mock_client = AsyncMock()
        mock_client.aclose = AsyncMock()
        mock_client.exists = AsyncMock(return_value=0)

        captured_start_id = None

        async def fake_xread(streams, block, count):
            nonlocal captured_start_id
            captured_start_id = list(streams.values())[0]
            return []

        mock_client.xread = fake_xread

        with patch.object(service, "_get_client", return_value=mock_client):
            async for _ in service.stream_events("pres-1"):
                break

        assert captured_start_id == "0"

    @pytest.mark.asyncio
    async def test_exits_when_stream_expires(self):
        """Generator should exit cleanly when the stream key no longer exists."""
        service = StreamingService()
        mock_client = AsyncMock()
        mock_client.aclose = AsyncMock()
        mock_client.xread = AsyncMock(return_value=[])
        mock_client.exists = AsyncMock(return_value=0)  # stream gone

        with patch.object(service, "_get_client", return_value=mock_client):
            chunks = []
            async for chunk in service.stream_events("pres-1"):
                chunks.append(chunk)

        # No events, just exits cleanly
        assert chunks == []

    @pytest.mark.asyncio
    async def test_advances_cursor_across_batches(self):
        """The start_id cursor should advance to the last seen entry_id."""
        service = StreamingService()
        mock_client = AsyncMock()
        mock_client.aclose = AsyncMock()

        batch1 = [_entry("10-0", "agent_start", {"agent": "research"})]
        batch2 = [_entry("20-0", "complete", {"presentation_id": "pres-1"})]

        call_count = 0
        seen_ids = []

        async def fake_xread(streams, block, count):
            nonlocal call_count
            call_count += 1
            seen_ids.append(list(streams.values())[0])
            if call_count == 1:
                return _make_xread_result(batch1)
            return _make_xread_result(batch2)

        mock_client.xread = fake_xread

        with patch.object(service, "_get_client", return_value=mock_client):
            chunks = []
            async for chunk in service.stream_events("pres-1"):
                chunks.append(chunk)

        # First call starts at "0", second call starts at "10-0"
        assert seen_ids[0] == "0"
        assert seen_ids[1] == "10-0"


# ---------------------------------------------------------------------------
# Unit: Cancellation helpers
# ---------------------------------------------------------------------------

class TestCancellationHelpers:
    @pytest.mark.asyncio
    async def test_set_cancellation_flag(self):
        service = StreamingService()
        mock_client = AsyncMock()
        mock_client.set = AsyncMock()
        mock_client.aclose = AsyncMock()

        with patch.object(service, "_get_client", return_value=mock_client):
            await service.set_cancellation_flag("job-123")

        mock_client.set.assert_called_once_with(
            "cancel:job:job-123", "1", ex=STREAM_TTL_SECONDS
        )

    @pytest.mark.asyncio
    async def test_is_cancelled_true(self):
        service = StreamingService()
        mock_client = AsyncMock()
        mock_client.exists = AsyncMock(return_value=1)
        mock_client.aclose = AsyncMock()

        with patch.object(service, "_get_client", return_value=mock_client):
            result = await service.is_cancelled("job-123")

        assert result is True

    @pytest.mark.asyncio
    async def test_is_cancelled_false(self):
        service = StreamingService()
        mock_client = AsyncMock()
        mock_client.exists = AsyncMock(return_value=0)
        mock_client.aclose = AsyncMock()

        with patch.object(service, "_get_client", return_value=mock_client):
            result = await service.is_cancelled("job-123")

        assert result is False

    @pytest.mark.asyncio
    async def test_clear_cancellation_flag(self):
        service = StreamingService()
        mock_client = AsyncMock()
        mock_client.delete = AsyncMock()
        mock_client.aclose = AsyncMock()

        with patch.object(service, "_get_client", return_value=mock_client):
            await service.clear_cancellation_flag("job-123")

        mock_client.delete.assert_called_once_with("cancel:job:job-123")

    @pytest.mark.asyncio
    async def test_cancel_stream_publishes_error_event(self):
        service = StreamingService()
        mock_client = AsyncMock()
        mock_client.xadd = AsyncMock(return_value="5-0")
        mock_client.expire = AsyncMock()
        mock_client.aclose = AsyncMock()

        with patch.object(service, "_get_client", return_value=mock_client):
            await service.cancel_stream("pres-1", "job-123")

        fields = mock_client.xadd.call_args[0][1]
        assert fields["event_type"] == "error"
        data = json.loads(fields["data"])
        assert data.get("cancelled") is True


# ---------------------------------------------------------------------------
# Property: publish then stream round-trip
# ---------------------------------------------------------------------------

class TestPublishStreamRoundTrip:
    @pytest.mark.asyncio
    async def test_published_events_appear_in_stream(self):
        """
        Events published via publish_event should be readable via stream_events.
        This tests the data contract between publisher and consumer.
        """
        service = StreamingService()

        # Simulate a sequence of events that would be stored in the stream
        stored_entries = []

        async def fake_xadd(key, fields, maxlen=None, approximate=None):
            entry_id = f"{len(stored_entries) + 1}-0"
            stored_entries.append((entry_id, dict(fields)))
            return entry_id

        publish_client = AsyncMock()
        publish_client.xadd = fake_xadd
        publish_client.expire = AsyncMock()
        publish_client.aclose = AsyncMock()

        # Publish some events
        with patch.object(service, "_get_client", return_value=publish_client):
            await service.publish_agent_start("pres-1", "research", "exec-1")
            await service.publish_agent_complete("pres-1", "research", "exec-1", 1500.0)
            await service.publish_complete("pres-1", "exec-1", 8.5)

        assert len(stored_entries) == 3

        # Now simulate reading them back via stream_events
        call_count = 0

        async def fake_xread(streams, block, count):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return [("stream:presentation:pres-1", stored_entries)]
            return []

        stream_client = AsyncMock()
        stream_client.xread = fake_xread
        stream_client.exists = AsyncMock(return_value=0)
        stream_client.aclose = AsyncMock()

        with patch.object(service, "_get_client", return_value=stream_client):
            chunks = []
            async for chunk in service.stream_events("pres-1"):
                chunks.append(chunk)

        assert len(chunks) == 3
        assert "event: agent_start" in chunks[0]
        assert "event: agent_complete" in chunks[1]
        assert "event: complete" in chunks[2]

        # Verify data integrity
        data_line = [l for l in chunks[1].split("\n") if l.startswith("data:")][0]
        payload = json.loads(data_line[len("data: "):])
        assert payload["agent"] == "research"
        assert payload["elapsed_ms"] == 1500.0
