"""Tests for protocol message parsing."""

import pytest

from sensio_lib.message import (
    TYPE_BUTTON,
    TYPE_DIMMER,
    TYPE_MEMORY,
    TYPE_RELAY,
    TYPE_SENSOR,
    HubInfo,
    RsnMessage,
    extract_messages,
    parse_connect_message,
    parse_rsn,
)


class TestParseRsn:
    """Tests for parse_rsn()."""

    def test_button_message(self):
        msg = parse_rsn("RSN 79057 B_LightBod_ON 6 1 0 0")
        assert msg == RsnMessage(
            address=79057, name="B_LightBod_ON",
            type_code=TYPE_BUTTON, flag=1, field_a=0.0, field_b=0.0,
        )

    def test_relay_message(self):
        msg = parse_rsn("RSN 41302 R_VindusrStue 8 1 1 1")
        assert msg == RsnMessage(
            address=41302, name="R_VindusrStue",
            type_code=TYPE_RELAY, flag=1, field_a=1.0, field_b=1.0,
        )

    def test_dimmer_message(self):
        msg = parse_rsn("RSN 42264 D_TaklampeBod 21 1 100 100")
        assert msg == RsnMessage(
            address=42264, name="D_TaklampeBod",
            type_code=TYPE_DIMMER, flag=1, field_a=100.0, field_b=100.0,
        )

    def test_dimmer_ramping(self):
        msg = parse_rsn("RSN 39938 D_DownlightsKinorom 21 1 23 50")
        assert msg is not None
        assert msg.field_a == 23.0
        assert msg.field_b == 50.0

    def test_memory_message_float(self):
        msg = parse_rsn("RSN 42382 M_D_TaklampeBod_Val 23 1 0 100.000")
        assert msg == RsnMessage(
            address=42382, name="M_D_TaklampeBod_Val",
            type_code=TYPE_MEMORY, flag=1, field_a=0.0, field_b=100.0,
        )

    def test_sensor_message(self):
        msg = parse_rsn("RSN 31790 A_EnergiSoverom1 10 1 0 4895.941")
        assert msg == RsnMessage(
            address=31790, name="A_EnergiSoverom1",
            type_code=TYPE_SENSOR, flag=1, field_a=0.0, field_b=4895.941,
        )

    def test_negative_value(self):
        msg = parse_rsn("RSN 63543 M_HusCurSc 23 1 0 -1.000")
        assert msg is not None
        assert msg.field_b == -1.0

    def test_off_state(self):
        msg = parse_rsn("RSN 42264 D_TaklampeBod 21 1 0 0")
        assert msg is not None
        assert msg.field_a == 0.0
        assert msg.field_b == 0.0

    def test_whitespace_variations(self):
        # Extra spaces between fields
        msg = parse_rsn("RSN 79057  B_LightBod_ON  6  1 0 0")
        assert msg is not None
        assert msg.address == 79057

    def test_returns_none_for_non_rsn(self):
        assert parse_rsn("PANEL_BRIGHTNESS 70") is None
        assert parse_rsn("x_bm_st ACK_DIRECT seq=11") is None
        assert parse_rsn("end 79057") is None
        assert parse_rsn("") is None

    def test_returns_none_for_malformed(self):
        assert parse_rsn("RSN not enough fields") is None
        assert parse_rsn("RSN abc name 6 1 0 0") is None


class TestParseConnectMessage:
    """Tests for parse_connect_message()."""

    def test_valid_connect(self):
        raw = (
            '<connect sn="980284010F50" ip="192.168.8.31" mac="98:02:84:01:0f:50"'
            ' pname="" pid="4BA386BD-000899" pdate="1269008061" psum="4128"'
            ' rg="" fw="etn-spux Feb 18 2022 17:05:01 6.12.1-65"/>'
        )
        info = parse_connect_message(raw)
        assert info is not None
        assert info.serial == "980284010F50"
        assert info.ip == "192.168.8.31"
        assert info.mac == "98:02:84:01:0f:50"
        assert info.product_id == "4BA386BD-000899"
        assert "6.12.1-65" in info.firmware

    def test_minimal_connect(self):
        raw = '<connect sn="ABC123" ip="10.0.0.1" mac="aa:bb:cc" pid="X" fw="v1"/>'
        info = parse_connect_message(raw)
        assert info is not None
        assert info.serial == "ABC123"

    def test_returns_none_for_non_connect(self):
        assert parse_connect_message("RSN 42264 D_TaklampeBod 21 1 100 100") is None
        assert parse_connect_message("PANEL_BRIGHTNESS 70") is None
        assert parse_connect_message("") is None

    def test_returns_none_for_malformed_xml(self):
        assert parse_connect_message("<connect broken") is None

    def test_returns_none_without_serial(self):
        assert parse_connect_message('<connect ip="1.2.3.4"/>') is None


class TestExtractMessages:
    """Tests for extract_messages()."""

    def test_single_complete_message(self):
        data = b"\x01hello\x02"
        msgs, buf = extract_messages(data, b"")
        assert msgs == ["hello"]
        assert buf == b""

    def test_multiple_messages(self):
        data = b"\x01msg1\x02\x01msg2\x02"
        msgs, buf = extract_messages(data, b"")
        assert msgs == ["msg1", "msg2"]
        assert buf == b""

    def test_partial_message_buffered(self):
        data = b"\x01partial"
        msgs, buf = extract_messages(data, b"")
        assert msgs == []
        assert buf == b"\x01partial"

    def test_continuation_from_buffer(self):
        msgs, buf = extract_messages(b" data\x02", b"\x01more")
        assert msgs == ["more data"]
        assert buf == b""

    def test_garbage_before_start(self):
        data = b"garbage\x01valid\x02"
        msgs, buf = extract_messages(data, b"")
        assert msgs == ["valid"]
        assert buf == b""

    def test_empty_data(self):
        msgs, buf = extract_messages(b"", b"")
        assert msgs == []
        assert buf == b""

    def test_rsn_message_round_trip(self):
        raw = b"\x01RSN 42264 D_TaklampeBod 21 1 100 100\x02"
        msgs, _ = extract_messages(raw, b"")
        assert len(msgs) == 1
        rsn = parse_rsn(msgs[0])
        assert rsn is not None
        assert rsn.address == 42264
        assert rsn.type_code == TYPE_DIMMER

    def test_mixed_messages(self):
        data = (
            b"\x01RSN 79057 B_LightBod_ON 6 1 0 0\x02"
            b"\x01PANEL_BRIGHTNESS 70\x02"
            b"\x01end 79057\x02"
        )
        msgs, buf = extract_messages(data, b"")
        assert len(msgs) == 3
        assert msgs[1] == "PANEL_BRIGHTNESS 70"
        assert buf == b""

    def test_trailing_partial(self):
        data = b"\x01complete\x02\x01incom"
        msgs, buf = extract_messages(data, b"")
        assert msgs == ["complete"]
        assert buf == b"\x01incom"
