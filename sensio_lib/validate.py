"""Hub validation probe for verifying a Sensio hub at a given address."""

from __future__ import annotations

import asyncio
import logging

from sensio_lib.exceptions import SensioConnectionError, SensioHubValidationError
from sensio_lib.message import HubInfo, extract_messages, parse_connect_message

logger = logging.getLogger(__name__)

_PROBE_TIMEOUT = 5


async def validate_hub(
    address: str, port: int = 10023, timeout: float = _PROBE_TIMEOUT
) -> HubInfo:
    """Probe a TCP address and verify it is a Sensio hub.

    Opens a short-lived connection, reads the first framed message,
    and parses it as the XML connect tag. Closes the connection after.

    Args:
        address: Hub IP address or hostname.
        port: TCP port (default 10023).
        timeout: Connection and read timeout in seconds.

    Returns:
        HubInfo with the hub's identity.

    Raises:
        SensioConnectionError: Cannot reach the address.
        SensioHubValidationError: Connected but not a valid Sensio hub.
    """
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(address, port),
            timeout=timeout,
        )
    except (OSError, asyncio.TimeoutError) as err:
        raise SensioConnectionError(
            f"Cannot connect to {address}:{port}: {err}"
        ) from err

    try:
        data = await asyncio.wait_for(reader.read(4096), timeout=timeout)
    except (OSError, asyncio.TimeoutError) as err:
        writer.close()
        raise SensioHubValidationError(
            f"Connected to {address}:{port} but received no data: {err}"
        ) from err
    finally:
        if not writer.is_closing():
            writer.close()
            try:
                await writer.wait_closed()
            except OSError:
                pass

    if not data:
        raise SensioHubValidationError(
            f"Connected to {address}:{port} but connection closed immediately"
        )

    messages, _ = extract_messages(data, b"")
    if not messages:
        raise SensioHubValidationError(
            f"Connected to {address}:{port} but received no framed messages"
        )

    # The first message should be the XML connect tag
    hub_info = parse_connect_message(messages[0])
    if hub_info is None:
        raise SensioHubValidationError(
            f"Connected to {address}:{port} but first message is not a Sensio "
            f"connect tag: {messages[0][:100]}"
        )

    logger.info(
        "Validated Sensio hub at %s:%d — serial=%s fw=%s",
        address, port, hub_info.serial, hub_info.firmware,
    )
    return hub_info
