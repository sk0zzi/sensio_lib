"""Message parsing for the Sensio hub protocol.

Parses raw hub strings (after \\x01..\\x02 framing is stripped) into typed
Python objects. The hub sends several message types; we currently only
act on RSN messages, but the parser is designed to be extended.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass

from sensio_lib.exceptions import SensioConnectionError


@dataclass
class HubIdentity:
    """Identity information parsed from the <connect .../> XML on TCP connect.

    The hub sends this XML tag as the very first message after a TCP
    connection is established.
    """

    serial: str
    ip: str
    mac: str
    firmware: str
    product_id: str


@dataclass
class RsnMessage:
    """A single RSN status message from the hub.

    RSN messages report state changes for devices, sensors, timers, etc.
    Format: RSN <address> <name> <type_code> <flag> <field_a> <field_b>
    """

    address: int
    name: str
    type_code: int
    flag: int
    field_a: float
    field_b: float


def parse_hub_identity(raw: str) -> HubIdentity:
    """Parse the <connect .../> XML tag sent by the hub on TCP connect.

    Args:
        raw: The raw string content (framing already stripped).

    Returns:
        HubIdentity with serial, IP, MAC, firmware, and product ID.

    Raises:
        SensioConnectionError: If the string is not a valid Sensio
            connect tag (wrong element, missing attributes, garbled).
    """
    try:
        root = ET.fromstring(raw.strip())
    except ET.ParseError as err:
        raise SensioConnectionError(
            f"Hub did not send valid XML on connect: {err}"
        ) from err

    if root.tag != "connect":
        raise SensioConnectionError(
            f"Expected <connect> element, got <{root.tag}>"
        )

    try:
        return HubIdentity(
            serial=root.attrib["sn"],
            ip=root.attrib["ip"],
            mac=root.attrib["mac"],
            firmware=root.attrib["fw"],
            product_id=root.attrib["pid"],
        )
    except KeyError as err:
        raise SensioConnectionError(
            f"Connect tag missing required attribute: {err}"
        ) from err


def parse_rsn_message(raw: str) -> RsnMessage | None:
    """Parse an RSN status message from the hub.

    The RSN format is fixed: ``RSN <address> <name> <type> <flag> <a> <b>``
    (7 space-separated tokens). Any other message type returns None.

    Args:
        raw: The raw string content (framing already stripped).

    Returns:
        An RsnMessage if the string is a valid RSN line, or None for
        any other message type (PANEL_BRIGHTNESS, end, x_bm_st, etc.).
        Returning None allows the caller to silently skip non-RSN messages.
    """
    parts = raw.strip().split()
    if len(parts) != 7 or parts[0] != "RSN":
        return None

    try:
        return RsnMessage(
            address=int(parts[1]),
            name=parts[2],
            type_code=int(parts[3]),
            flag=int(parts[4]),
            field_a=float(parts[5]),
            field_b=float(parts[6]),
        )
    except (ValueError, IndexError):
        return None
