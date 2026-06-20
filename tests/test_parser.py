import struct

import pytest

from dis_radio.dis.parser import ParsedKind, parse_pdu
from dis_radio.models import TransmitterState


def _make_transmitter_pdu(
    site=1, app=2, entity=3, radio_id=4,
    exercise_id=1, state=2,
    frequency=148_500_000, power=10.0,
    major_mod=3,
) -> bytes:
    """Build raw TransmitterPdu bytes (DIS 7, pduType=25)
    without using opendis serialize."""
    # Fixed payload size (no variable-length lists)
    # Header(12) + EntityID(6) + radioNumber(2) + radioEntityType(8)
    # + transmitState(1) + inputSource(1) + varTxParamCount(2)
    # + antennaLocation(24) + relAntennaLocation(12)
    # + antennaPatternType(2) + antennaPatternCount(2)
    # + frequency(8) + txFreqBW(4) + power(4)
    # + modulationType(8) + cryptoSystem(2) + cryptoKeyId(2)
    # + modParamCount(1) + padding2(2) + padding3(1) = 104 bytes total
    total_len = 104
    buf = struct.pack('>BBBBIHBB',
        7, exercise_id, 25, 4, 0, total_len, 0, 0)  # header
    buf += struct.pack('>HHH', site, app, entity)    # radioReferenceID (EntityID)
    buf += struct.pack('>H', radio_id)               # radioNumber
    buf += struct.pack('>BBHBBBB', 0, 0, 0, 0, 0, 0, 0)  # radioEntityType
    buf += struct.pack('>BB', state, 0)              # transmitState, inputSource
    buf += struct.pack('>H', 0)                      # variableTransmitterParameterCount
    buf += struct.pack('>ddd', 0.0, 0.0, 0.0)        # antennaLocation (Vector3Double)
    buf += struct.pack('>fff', 0.0, 0.0, 0.0)        # relativeAntennaLocation
    buf += struct.pack('>HH', 0, 0)    # antennaPatternType, antennaPatternCount
    buf += struct.pack('>q', frequency)              # frequency (int64)
    buf += struct.pack('>f', 0.0)                    # transmitFrequencyBandwidth
    buf += struct.pack('>f', power)                  # power
    buf += struct.pack('>HHHH', 0, major_mod, 0, 0)  # modulationType
    buf += struct.pack('>HH', 0, 0)                  # cryptoSystem, cryptoKeyId
    buf += struct.pack('>BHB', 0, 0, 0)              # modParamCount, padding2, padding3
    return buf


def _make_signal_pdu(
    site=1, app=2, entity=3, radio_id=4,
    exercise_id=1, encoding_scheme=0x0001,
    sample_rate=8000, audio=b"\xff\xff",
) -> bytes:
    """Build raw SignalPdu bytes (DIS 7, pduType=26) without using opendis serialize."""
    audio_len = len(audio)
    total_len = 12 + 6 + 2 + 2 + 2 + 4 + 2 + 2 + audio_len
    buf = struct.pack('>BBBBIHBB',
        7, exercise_id, 26, 4, 0, total_len, 0, 0)  # header
    buf += struct.pack('>HHH', site, app, entity)    # entityID
    buf += struct.pack('>H', radio_id)               # radioID
    buf += struct.pack('>H', encoding_scheme)        # encodingScheme
    buf += struct.pack('>H', 0)                      # tdlType
    buf += struct.pack('>I', sample_rate)            # sampleRate
    buf += struct.pack('>H', audio_len * 8)          # dataLength (bits)
    buf += struct.pack('>H', 0)                      # samples
    buf += audio                                     # data
    return buf


def test_parse_transmitter_pdu_returns_record():
    data = _make_transmitter_pdu()
    result = parse_pdu(data)
    assert result is not None
    kind, record = result
    assert kind == ParsedKind.TRANSMITTER


def test_parse_transmitter_entity_id():
    data = _make_transmitter_pdu(site=14, app=1, entity=42)
    _, record = parse_pdu(data)
    assert record.entity_id == (14, 1, 42)


def test_parse_transmitter_radio_id():
    data = _make_transmitter_pdu(radio_id=7)
    _, record = parse_pdu(data)
    assert record.radio_id == 7


def test_parse_transmitter_state_transmitting():
    data = _make_transmitter_pdu(state=2)
    _, record = parse_pdu(data)
    assert record.state == TransmitterState.TRANSMITTING


def test_parse_transmitter_state_off():
    data = _make_transmitter_pdu(state=0)
    _, record = parse_pdu(data)
    assert record.state == TransmitterState.OFF


def test_parse_transmitter_frequency():
    data = _make_transmitter_pdu(frequency=148_500_000)
    _, record = parse_pdu(data)
    assert record.frequency_hz == 148_500_000.0


def test_parse_transmitter_power():
    data = _make_transmitter_pdu(power=10.0)
    _, record = parse_pdu(data)
    assert record.power_dbm == pytest.approx(10.0, abs=0.1)


def test_parse_transmitter_modulation_angle():
    data = _make_transmitter_pdu(major_mod=3)
    _, record = parse_pdu(data)
    assert record.modulation_major == "Angle"


def test_parse_transmitter_modulation_amplitude():
    data = _make_transmitter_pdu(major_mod=1)
    _, record = parse_pdu(data)
    assert record.modulation_major == "Amplitude"


def test_parse_transmitter_exercise_id():
    data = _make_transmitter_pdu(exercise_id=5)
    _, record = parse_pdu(data)
    assert record.exercise_id == 5


def test_parse_signal_pdu_returns_signal():
    data = _make_signal_pdu()
    result = parse_pdu(data)
    assert result is not None
    kind, key, audio, encoding, sample_rate = result
    assert kind == ParsedKind.SIGNAL


def test_parse_signal_pdu_key():
    data = _make_signal_pdu(site=14, app=1, entity=42, radio_id=3)
    _, key, _, _, _ = parse_pdu(data)
    assert key == (14, 1, 42, 3)


def test_parse_signal_pdu_audio_bytes():
    audio = b"\xff\x7f\xfe"
    data = _make_signal_pdu(audio=audio)
    _, _, received_audio, _, _ = parse_pdu(data)
    assert received_audio == audio


def test_parse_signal_pdu_ulaw_encoding():
    # encodingScheme bits 15-14=0 (encoded audio), bits 13-0=1 (µ-law) → 0x0001
    data = _make_signal_pdu(encoding_scheme=0x0001)
    _, _, _, encoding, _ = parse_pdu(data)
    assert encoding == 1  # codec type 1 = µ-law


def test_parse_signal_pdu_sample_rate():
    data = _make_signal_pdu(sample_rate=8000)
    _, _, _, _, sample_rate = parse_pdu(data)
    assert sample_rate == 8000


def test_parse_signal_pdu_pcm_encoding():
    # encoding_scheme=0x0004 → class=0, type=4 → internal codec type 0 (PCM)
    data = _make_signal_pdu(encoding_scheme=0x0004)
    _, _, _, encoding, _ = parse_pdu(data)
    assert encoding == 0


def test_parse_signal_pdu_unknown_encoding():
    # encoding_scheme=0xFFFF → unsupported → internal codec type -1
    data = _make_signal_pdu(encoding_scheme=0xFFFF)
    _, _, _, encoding, _ = parse_pdu(data)
    assert encoding == -1


def test_parse_transmitter_state_idle():
    data = _make_transmitter_pdu(state=1)
    _, record = parse_pdu(data)
    assert record.state == TransmitterState.IDLE


def test_parse_unknown_pdu_returns_none():
    assert parse_pdu(b"\x00" * 12) is None


def test_parse_empty_returns_none():
    assert parse_pdu(b"") is None
