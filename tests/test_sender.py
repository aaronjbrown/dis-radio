import struct as _struct
import pytest
from dis_radio.config import AppConfig
from dis_radio.dis.parser import parse_pdu, ParsedKind
from dis_radio.models import TransmitterState
from dis_radio.network.sender import DISSender


@pytest.fixture
def sender_and_captured(monkeypatch):
    """Create a DISSender whose socket.sendto is captured into a list."""
    config = AppConfig()
    config.network.multicast_group = "239.255.0.1"
    config.network.port = 3000
    sender = DISSender(config)
    captured = []
    monkeypatch.setattr(sender._sock, "sendto", lambda data, addr: captured.append((data, addr)))
    return sender, captured


def test_send_transmitter_sends_to_correct_address(sender_and_captured):
    sender, captured = sender_and_captured
    sender.send_transmitter((1, 2, 3, 4), 148_500_000.0, TransmitterState.IDLE, 1)
    assert len(captured) == 1
    _, addr = captured[0]
    assert addr == ("239.255.0.1", 3000)


def test_send_transmitter_pdu_is_parseable(sender_and_captured):
    sender, captured = sender_and_captured
    sender.send_transmitter((1, 2, 3, 4), 148_500_000.0, TransmitterState.IDLE, 1)
    data, _ = captured[0]
    result = parse_pdu(data)
    assert result is not None
    kind, record = result
    assert kind == ParsedKind.TRANSMITTER


def test_send_transmitter_entity_id(sender_and_captured):
    sender, captured = sender_and_captured
    sender.send_transmitter((14, 1, 42, 7), 148_500_000.0, TransmitterState.IDLE, 1)
    data, _ = captured[0]
    _, record = parse_pdu(data)
    assert record.entity_id == (14, 1, 42)
    assert record.radio_id == 7


def test_send_transmitter_frequency(sender_and_captured):
    sender, captured = sender_and_captured
    sender.send_transmitter((1, 1, 1, 1), 456_000_000.0, TransmitterState.IDLE, 1)
    data, _ = captured[0]
    _, record = parse_pdu(data)
    assert record.frequency_hz == 456_000_000.0


def test_send_transmitter_state_idle(sender_and_captured):
    sender, captured = sender_and_captured
    sender.send_transmitter((1, 1, 1, 1), 100_000_000.0, TransmitterState.IDLE, 1)
    data, _ = captured[0]
    _, record = parse_pdu(data)
    assert record.state == TransmitterState.IDLE


def test_send_transmitter_state_transmitting(sender_and_captured):
    sender, captured = sender_and_captured
    sender.send_transmitter((1, 1, 1, 1), 100_000_000.0, TransmitterState.TRANSMITTING, 1)
    data, _ = captured[0]
    _, record = parse_pdu(data)
    assert record.state == TransmitterState.TRANSMITTING


def test_send_transmitter_exercise_id(sender_and_captured):
    sender, captured = sender_and_captured
    sender.send_transmitter((1, 1, 1, 1), 100_000_000.0, TransmitterState.IDLE, 7)
    data, _ = captured[0]
    _, record = parse_pdu(data)
    assert record.exercise_id == 7


def test_send_signal_pdu_is_parseable(sender_and_captured):
    sender, captured = sender_and_captured
    audio = bytes([0xFF] * 160)  # 160 samples of µ-law silence
    sender.send_signal((1, 2, 3, 4), audio, 8000, 1)
    data, _ = captured[0]
    result = parse_pdu(data)
    assert result is not None
    kind, key, received_audio, encoding, sample_rate = result
    assert kind == ParsedKind.SIGNAL


def test_send_signal_key(sender_and_captured):
    sender, captured = sender_and_captured
    audio = bytes([0xFF] * 16)
    sender.send_signal((14, 1, 42, 3), audio, 8000, 1)
    data, _ = captured[0]
    _, key, _, _, _ = parse_pdu(data)
    assert key == (14, 1, 42, 3)


def test_send_signal_audio_bytes(sender_and_captured):
    sender, captured = sender_and_captured
    audio = bytes([0xAB, 0xCD, 0xEF])
    sender.send_signal((1, 1, 1, 1), audio, 8000, 1)
    data, _ = captured[0]
    _, _, received_audio, _, _ = parse_pdu(data)
    assert received_audio == audio


def test_send_signal_encoding_is_ulaw(sender_and_captured):
    sender, captured = sender_and_captured
    sender.send_signal((1, 1, 1, 1), bytes([0xFF]), 8000, 1)
    data, _ = captured[0]
    _, _, _, encoding, _ = parse_pdu(data)
    assert encoding == 1  # codec type 1 = µ-law


def test_send_signal_sample_rate(sender_and_captured):
    sender, captured = sender_and_captured
    sender.send_signal((1, 1, 1, 1), bytes([0xFF] * 4), 8000, 1)
    data, _ = captured[0]
    _, _, _, _, sample_rate = parse_pdu(data)
    assert sample_rate == 8000


def test_send_failure_does_not_raise(monkeypatch):
    config = AppConfig()
    sender = DISSender(config)

    def _raise(data, addr):
        raise OSError("network error")

    monkeypatch.setattr(sender._sock, "sendto", _raise)
    # should log warning and not raise
    sender.send_transmitter((1, 1, 1, 1), 100_000_000.0, TransmitterState.IDLE, 1)


def test_reconfigure_updates_target(monkeypatch):
    config = AppConfig()
    sender = DISSender(config)
    captured = []
    monkeypatch.setattr(sender._sock, "sendto", lambda data, addr: captured.append(addr))
    new_config = AppConfig()
    new_config.network.multicast_group = "239.255.0.2"
    new_config.network.port = 4000
    sender.reconfigure(new_config)
    sender.send_transmitter((1, 1, 1, 1), 100_000_000.0, TransmitterState.IDLE, 1)
    assert captured[0] == ("239.255.0.2", 4000)


def test_send_transmitter_modulation_nbfm(sender_and_captured):
    sender, captured = sender_and_captured
    sender.send_transmitter((1, 1, 1, 1), 148_500_000.0, TransmitterState.IDLE, 1,
                            modulation_major="NBFM (25 kHz)")
    data, _ = captured[0]
    _, record = parse_pdu(data)
    assert record.modulation_major == "Angle"   # SISO UID 155: major=3 → "Angle"


def test_send_transmitter_modulation_am_dsb(sender_and_captured):
    sender, captured = sender_and_captured
    sender.send_transmitter((1, 1, 1, 1), 148_500_000.0, TransmitterState.IDLE, 1,
                            modulation_major="AM (DSB)")
    data, _ = captured[0]
    _, record = parse_pdu(data)
    assert record.modulation_major == "Amplitude"   # SISO UID 155: major=1 → "Amplitude"


def test_send_transmitter_power_dbm(sender_and_captured):
    sender, captured = sender_and_captured
    sender.send_transmitter((1, 1, 1, 1), 148_500_000.0, TransmitterState.IDLE, 1,
                            power_dbm=37.0)
    data, _ = captured[0]
    _, record = parse_pdu(data)
    assert record.power_dbm == pytest.approx(37.0, abs=0.01)


def test_send_transmitter_bandwidth_hz(sender_and_captured):
    sender, captured = sender_and_captured
    sender.send_transmitter((1, 1, 1, 1), 148_500_000.0, TransmitterState.IDLE, 1,
                            bandwidth_hz=25_000.0)
    data, _ = captured[0]
    _, record = parse_pdu(data)
    assert record.bandwidth_hz == pytest.approx(25_000.0, abs=1.0)


def test_send_transmitter_header_timestamp_is_absolute(sender_and_captured):
    sender, captured = sender_and_captured
    sender.send_transmitter((1, 1, 1, 1), 148_500_000.0, TransmitterState.IDLE, 1)
    data, _ = captured[0]
    timestamp = _struct.unpack('>I', data[4:8])[0]
    assert timestamp != 0
    assert timestamp & 1 == 1   # bit 0 = 1 → absolute time reference


def test_send_signal_header_timestamp_is_absolute(sender_and_captured):
    sender, captured = sender_and_captured
    sender.send_signal((1, 1, 1, 1), bytes([0xFF] * 160), 8000, 1)
    data, _ = captured[0]
    timestamp = _struct.unpack('>I', data[4:8])[0]
    assert timestamp != 0
    assert timestamp & 1 == 1
