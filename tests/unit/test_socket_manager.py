"""Tests for the SocketManager read loop."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from sensio_lib.socket_manager import SocketManager


def _make_reader(chunks: list[bytes]) -> AsyncMock:
    """Create a mock StreamReader that yields the given chunks then EOF."""
    reader = AsyncMock(spec=asyncio.StreamReader)
    read_values = list(chunks) + [b""]  # empty = EOF
    reader.read = AsyncMock(side_effect=read_values)
    reader.at_eof = MagicMock(return_value=False)
    return reader


def _make_writer() -> MagicMock:
    """Create a mock StreamWriter."""
    writer = MagicMock()
    writer.is_closing = MagicMock(return_value=False)
    writer.close = MagicMock()
    writer.wait_closed = AsyncMock()
    writer.write = MagicMock()
    writer.drain = AsyncMock()
    return writer


class TestReadLoop:
    """Tests for the background read loop."""

    @pytest.mark.asyncio
    async def test_read_loop_dispatches_messages(self):
        sm = SocketManager("127.0.0.1")
        received: list[str] = []
        sm.set_message_callback(lambda msg: received.append(msg))

        reader = _make_reader([b"\x01hello\x02\x01world\x02"])
        writer = _make_writer()

        with patch("sensio_lib.socket_manager.asyncio.open_connection",
                    return_value=(reader, writer)):
            await sm.connect()
            # Let the read loop process
            await asyncio.sleep(0.05)
            await sm.close()

        assert received == ["hello", "world"]

    @pytest.mark.asyncio
    async def test_read_loop_handles_split_messages(self):
        sm = SocketManager("127.0.0.1")
        received: list[str] = []
        sm.set_message_callback(lambda msg: received.append(msg))

        reader = _make_reader([b"\x01hel", b"lo\x02"])
        writer = _make_writer()

        with patch("sensio_lib.socket_manager.asyncio.open_connection",
                    return_value=(reader, writer)):
            await sm.connect()
            await asyncio.sleep(0.05)
            await sm.close()

        assert received == ["hello"]

    @pytest.mark.asyncio
    async def test_read_loop_calls_disconnect_callback_on_eof(self):
        sm = SocketManager("127.0.0.1")
        disconnected = []
        sm.set_disconnect_callback(lambda: disconnected.append(True))

        reader = _make_reader([])  # Immediate EOF
        writer = _make_writer()

        with patch("sensio_lib.socket_manager.asyncio.open_connection",
                    return_value=(reader, writer)):
            await sm.connect()
            await asyncio.sleep(0.05)
            await sm.close()

        assert len(disconnected) == 1

    @pytest.mark.asyncio
    async def test_read_loop_survives_callback_exception(self):
        sm = SocketManager("127.0.0.1")
        good_messages: list[str] = []

        call_count = 0

        def callback(msg):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ValueError("boom")
            good_messages.append(msg)

        sm.set_message_callback(callback)

        reader = _make_reader([b"\x01first\x02\x01second\x02"])
        writer = _make_writer()

        with patch("sensio_lib.socket_manager.asyncio.open_connection",
                    return_value=(reader, writer)):
            await sm.connect()
            await asyncio.sleep(0.05)
            await sm.close()

        assert good_messages == ["second"]

    @pytest.mark.asyncio
    async def test_close_cancels_read_task(self):
        sm = SocketManager("127.0.0.1")

        # Reader that blocks forever
        reader = AsyncMock(spec=asyncio.StreamReader)
        reader.at_eof = MagicMock(return_value=False)
        reader.read = AsyncMock(side_effect=asyncio.CancelledError)
        writer = _make_writer()

        with patch("sensio_lib.socket_manager.asyncio.open_connection",
                    return_value=(reader, writer)):
            await sm.connect()
            assert sm._read_task is not None
            await sm.close()
            assert sm._read_task is None

    @pytest.mark.asyncio
    async def test_read_loop_handles_connection_reset(self):
        sm = SocketManager("127.0.0.1")
        disconnected = []
        sm.set_disconnect_callback(lambda: disconnected.append(True))

        reader = AsyncMock(spec=asyncio.StreamReader)
        reader.at_eof = MagicMock(return_value=False)
        reader.read = AsyncMock(side_effect=ConnectionResetError("reset"))
        writer = _make_writer()

        with patch("sensio_lib.socket_manager.asyncio.open_connection",
                    return_value=(reader, writer)):
            await sm.connect()
            await asyncio.sleep(0.05)
            await sm.close()

        assert len(disconnected) == 1

    @pytest.mark.asyncio
    async def test_no_callback_set(self):
        """Messages are silently discarded when no callback is set."""
        sm = SocketManager("127.0.0.1")
        # No callback set

        reader = _make_reader([b"\x01hello\x02"])
        writer = _make_writer()

        with patch("sensio_lib.socket_manager.asyncio.open_connection",
                    return_value=(reader, writer)):
            await sm.connect()
            await asyncio.sleep(0.05)
            await sm.close()
        # No exception = success
