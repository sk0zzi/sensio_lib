"""Protocol message parsing for the Sensio hub.

Handles framing (\x01...\x02 delimiters), RSN state messages,
and the XML connect tag sent on initial connection.
"""

from __future__ import annotations

import logging
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# RSN type codes
TYPE_TIMER = 2
TYPE_BUTTON = 6
TYPE_RELAY = 8
TYPE_SENSOR = 10
TYPE_DIMMER = 21
TYPE_MEMORY = 23

START_BYTE = b"\x01"
END_BYTE = b"\x02"


@dataclass(frozen=True, slots=True)
class RsnMessage:
    """A parsed RSN state message from the hub.

    Fields:
        address: Numeric address matching functions.json entries.
        name: Human-readable function name (e.g. "D_TaklampeBod").
        type_code: Object type (6=button, 8=relay, 10=sensor, 21=dimmer, 23=memory).
        flag: Status flag (always observed as 1).
        field_a: Meaning depends on type_code.
        field_b: Meaning depends on type_code.
    """

    address: int
    name: str
    type_code: int
    flag: int
    field_a: float
    field_b: float


@dataclass(frozen=True, slots=True)
class HubInfo:
    """Information from the hub's XML connect tag."""

    serial: str
    ip: str
    mac: str
    product_id: str
    firmware: str


_RSN_PATTERN = re.compile(
    r"^RSN\s+"
    r"(\d+)\s+"        # address
    r"(\S+)\s+"        # name
    r"(\d+)\s+"        # type_code
    r"(\d+)\s+"        # flag
    r"([0-9.\-]+)\s+"  # field_a
    r"([0-9.\-]+)$"    # field_b
)


def parse_rsn(line: str) -> RsnMessage | None:
    """Parse a single RSN message line.

    Returns None if the line is not a valid RSN message.
    """
    match = _RSN_PATTERN.match(line.strip())
    if not match:
        return None

    return RsnMessage(
        address=int(match.group(1)),
        name=match.group(2),
        type_code=int(match.group(3)),
        flag=int(match.group(4)),
        field_a=float(match.group(5)),
        field_b=float(match.group(6)),
    )


def parse_connect_message(raw: str) -> HubInfo | None:
    """Parse the XML connect tag sent by the hub on connection.

    Expected format:
        <connect sn="..." ip="..." mac="..." pid="..." fw="..."/>

    Returns None if the message is not a valid connect tag.
    """
    stripped = raw.strip()
    if not stripped.startswith("<connect"):
        return None

    try:
        element = ET.fromstring(stripped)
    except ET.ParseError:
        logger.debug("Failed to parse connect XML: %s", stripped)
        return None

    if element.tag != "connect":
        return None

    serial = element.get("sn", "")
    if not serial:
        return None

    return HubInfo(
        serial=serial,
        ip=element.get("ip", ""),
        mac=element.get("mac", ""),
        product_id=element.get("pid", ""),
        firmware=element.get("fw", ""),
    )


def extract_messages(data: bytes, buffer: bytes) -> tuple[list[str], bytes]:
    """Extract complete messages from a byte stream with \x01..\x02 framing.

    Args:
        data: Newly received bytes.
        buffer: Leftover bytes from previous calls.

    Returns:
        A tuple of (list of decoded message strings, remaining buffer).
    """
    buffer += data
    messages: list[str] = []

    while True:
        start = buffer.find(START_BYTE)
        if start == -1:
            # No start delimiter — discard everything
            buffer = b""
            break

        end = buffer.find(END_BYTE, start + 1)
        if end == -1:
            # Incomplete message — keep from start onwards
            buffer = buffer[start:]
            break

        segment = buffer[start + 1 : end]
        try:
            messages.append(segment.decode("utf-8"))
        except UnicodeDecodeError:
            messages.append(segment.decode("utf-8", errors="replace"))

        buffer = buffer[end + 1 :]

    return messages, buffer
