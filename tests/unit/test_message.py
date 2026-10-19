"""Tests for the message parsing module."""

import pytest

from sensio_lib.exceptions import SensioConnectionError
from sensio_lib.message import HubIdentity, RsnMessage, parse_hub_identity, parse_rsn_message


class TestParseHubIdentity:
    """Tests for parse_hub_identity()."""

    VALID_XML = (
        '<connect sn="AABBCCDDEEFF" ip="10.0.0.1" mac="aa:bb:cc:dd:ee:ff"'
        ' pname="" pid="TEST-PRODUCT-001" pdate="1000000000" psum="1234"'
        ' rg="" fw="etn-spux Jan 01 2024 12:00:00 1.0.0-1"/>'
    )

    def test_valid_connect_xml(self):
        """Valid connect XML should produce a correct HubIdentity."""
        identity = parse_hub_identity(self.VALID_XML)

        assert isinstance(identity, HubIdentity)
        assert identity.serial == "AABBCCDDEEFF"
        assert identity.ip == "10.0.0.1"
        assert identity.mac == "aa:bb:cc:dd:ee:ff"
        assert identity.firmware == "etn-spux Jan 01 2024 12:00:00 1.0.0-1"
        assert identity.product_id == "TEST-PRODUCT-001"

    def test_valid_xml_with_whitespace(self):
        """Leading/trailing whitespace should be handled."""
        identity = parse_hub_identity(f"  {self.VALID_XML}  \n")
        assert identity.serial == "AABBCCDDEEFF"

    def test_non_connect_element(self):
        """A valid XML element that is not <connect> should raise."""
        with pytest.raises(SensioConnectionError, match="Expected <connect>"):
            parse_hub_identity('<status ok="true"/>')

    def test_missing_required_attribute(self):
        """A <connect> tag missing a required attribute should raise."""
        # Missing 'sn' attribute
        with pytest.raises(SensioConnectionError, match="missing required attribute"):
            parse_hub_identity('<connect ip="1.2.3.4" mac="aa" fw="v1" pid="x"/>')

    def test_garbage_input(self):
        """Non-XML input should raise SensioConnectionError."""
        with pytest.raises(SensioConnectionError, match="valid XML"):
            parse_hub_identity("this is not xml at all")

    def test_empty_string(self):
        """Empty string should raise SensioConnectionError."""
        with pytest.raises(SensioConnectionError):
            parse_hub_identity("")

    def test_partial_xml(self):
        """Incomplete XML should raise SensioConnectionError."""
        with pytest.raises(SensioConnectionError):
            parse_hub_identity("<connect sn=")


class TestParseRsnMessage:
    """Tests for parse_rsn_message()."""

    def test_valid_relay_message(self):
        """A valid RSN type 8 (relay) message should parse correctly."""
        msg = parse_rsn_message("RSN 41302 R_VindusrStue 8 1 1 1")

        assert isinstance(msg, RsnMessage)
        assert msg.address == 41302
        assert msg.name == "R_VindusrStue"
        assert msg.type_code == 8
        assert msg.flag == 1
        assert msg.field_a == 1.0
        assert msg.field_b == 1.0

    def test_valid_dimmer_message(self):
        """A valid RSN type 21 (dimmer) message should parse correctly."""
        msg = parse_rsn_message("RSN 42264 D_TaklampeBod 21 1 100 100")

        assert msg is not None
        assert msg.address == 42264
        assert msg.type_code == 21
        assert msg.field_a == 100.0
        assert msg.field_b == 100.0

    def test_valid_memory_message(self):
        """A valid RSN type 23 (memory) message with float values."""
        msg = parse_rsn_message("RSN 78717 M_BodCurSc 23 1 0 1.000")

        assert msg is not None
        assert msg.address == 78717
        assert msg.type_code == 23
        assert msg.field_a == 0.0
        assert msg.field_b == 1.0

    def test_valid_button_message(self):
        """A valid RSN type 6 (button) message."""
        msg = parse_rsn_message("RSN 79057 B_LightBod_ON 6 1 0 0")

        assert msg is not None
        assert msg.type_code == 6
        assert msg.field_a == 0.0
        assert msg.field_b == 0.0

    def test_panel_brightness_returns_none(self):
        """PANEL_BRIGHTNESS messages should return None."""
        assert parse_rsn_message("PANEL_BRIGHTNESS 70") is None

    def test_end_message_returns_none(self):
        """End-of-cascade messages should return None."""
        assert parse_rsn_message("end 79057") is None

    def test_ack_message_returns_none(self):
        """ACK messages should return None."""
        assert parse_rsn_message("x_bm_st ACK_DIRECT seq=5") is None

    def test_empty_string_returns_none(self):
        """Empty string should return None."""
        assert parse_rsn_message("") is None

    def test_garbage_returns_none(self):
        """Garbage input should return None, not raise."""
        assert parse_rsn_message("hello world this is junk") is None

    def test_rsn_with_negative_float(self):
        """RSN message with negative float values."""
        msg = parse_rsn_message("RSN 63543 M_HusCurSc 23 1 0 -1.000")

        assert msg is not None
        assert msg.field_b == -1.0

    def test_rsn_with_whitespace(self):
        """RSN message with leading/trailing whitespace."""
        msg = parse_rsn_message("  RSN 41302 R_VindusrStue 8 1 0 0  ")

        assert msg is not None
        assert msg.address == 41302
