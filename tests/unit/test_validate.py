"""Tests for hub validation probe."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from sensio_lib.exceptions import SensioConnectionError, SensioHubValidationError
from sensio_lib.validate import validate_hub


def _make_reader(data: bytes) -> AsyncMock:
    """Create a mock reader that returns the given data."""
    reader = AsyncMock(spec=asyncio.StreamReader)
    reader.read = AsyncMock(return_value=data)
    return reader


def _make_writer() -> MagicMock:
    writer = MagicMock()
    writer.is_closing = MagicMock(return_value=False)
    writer.close = MagicMock()
    writer.wait_closed = AsyncMock()
    return writer


VALID_CONNECT = (
    b'\x01<connect sn="980284010F50" ip="192.168.8.31" mac="98:02:84:01:0f:50"'
    b' pname="" pid="4BA386BD-000899" pdate="1269008061" psum="4128"'
    b' rg="" fw="etn-spux Feb 18 2022 17:05:01 6.12.1-65"/>\x02'
)


class TestValidateHub:
    """Tests for validate_hub()."""

    @pytest.mark.asyncio
    async def test_valid_hub(self):
        reader = _make_reader(VALID_CONNECT)
        writer = _make_writer()

        with patch("sensio_lib.validate.asyncio.open_connection",
                    return_value=(reader, writer)):
            info = await validate_hub("192.168.8.31")

        assert info.serial == "980284010F50"
        assert info.ip == "192.168.8.31"
        assert info.mac == "98:02:84:01:0f:50"
        assert "6.12.1-65" in info.firmware
        writer.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_connection_refused(self):
        with patch("sensio_lib.validate.asyncio.open_connection",
                    side_effect=OSError("Connection refused")):
            with pytest.raises(SensioConnectionError, match="Cannot connect"):
                await validate_hub("192.168.8.99")

    @pytest.mark.asyncio
    async def test_connection_timeout(self):
        with patch("sensio_lib.validate.asyncio.open_connection",
                    side_effect=asyncio.TimeoutError()):
            with pytest.raises(SensioConnectionError):
                await validate_hub("192.168.8.99")

    @pytest.mark.asyncio
    async def test_no_data(self):
        reader = _make_reader(b"")
        writer = _make_writer()

        with patch("sensio_lib.validate.asyncio.open_connection",
                    return_value=(reader, writer)):
            with pytest.raises(SensioHubValidationError, match="closed immediately"):
                await validate_hub("192.168.8.31")

    @pytest.mark.asyncio
    async def test_no_framed_messages(self):
        reader = _make_reader(b"random garbage without delimiters")
        writer = _make_writer()

        with patch("sensio_lib.validate.asyncio.open_connection",
                    return_value=(reader, writer)):
            with pytest.raises(SensioHubValidationError, match="no framed"):
                await validate_hub("192.168.8.31")

    @pytest.mark.asyncio
    async def test_not_a_sensio_hub(self):
        reader = _make_reader(b"\x01HTTP/1.1 200 OK\x02")
        writer = _make_writer()

        with patch("sensio_lib.validate.asyncio.open_connection",
                    return_value=(reader, writer)):
            with pytest.raises(SensioHubValidationError, match="not a Sensio"):
                await validate_hub("192.168.8.31")

    @pytest.mark.asyncio
    async def test_read_timeout(self):
        reader = AsyncMock(spec=asyncio.StreamReader)
        reader.read = AsyncMock(side_effect=asyncio.TimeoutError())
        writer = _make_writer()

        with patch("sensio_lib.validate.asyncio.open_connection",
                    return_value=(reader, writer)):
            with pytest.raises(SensioHubValidationError, match="no data"):
                await validate_hub("192.168.8.31")

    @pytest.mark.asyncio
    async def test_custom_port(self):
        reader = _make_reader(VALID_CONNECT)
        writer = _make_writer()

        with patch("sensio_lib.validate.asyncio.open_connection",
                    return_value=(reader, writer)) as mock_conn:
            await validate_hub("10.0.0.1", port=9999)
            mock_conn.assert_called_once()
            call_args = mock_conn.call_args[0]
            assert call_args == ("10.0.0.1", 9999)
