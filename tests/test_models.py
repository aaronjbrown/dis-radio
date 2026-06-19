from datetime import datetime
from dis_radio.models import LocalTransmitter, TransmitterRecord, TransmitterState, TransmitterKey


def _make_record(**kwargs) -> TransmitterRecord:
    defaults = dict(
        entity_id=(1, 2, 3),
        radio_id=4,
        state=TransmitterState.TRANSMITTING,
        frequency_hz=148_500_000.0,
        power_dbm=10.0,
        modulation_major="FM",
        exercise_id=1,
        last_seen=datetime(2026, 1, 1),
    )
    defaults.update(kwargs)
    return TransmitterRecord(**defaults)


def test_transmitter_key():
    rec = _make_record(entity_id=(14, 1, 42), radio_id=3)
    assert rec.key == (14, 1, 42, 3)


def test_key_type_is_tuple():
    rec = _make_record()
    assert isinstance(rec.key, tuple)
    assert len(rec.key) == 4


def test_audio_enabled_defaults_false():
    rec = _make_record()
    assert rec.audio_enabled is False


def test_transmitter_state_values():
    assert TransmitterState.OFF == 0
    assert TransmitterState.IDLE == 1
    assert TransmitterState.TRANSMITTING == 2


def test_local_transmitter_fields():
    lt = LocalTransmitter(
        name="Command Net",
        frequency_hz=30_000_000.0,
        modulation_major="AM",
        power_dbm=10.0,
        radio_id=1,
    )
    assert lt.name == "Command Net"
    assert lt.frequency_hz == 30_000_000.0
    assert lt.modulation_major == "AM"
    assert lt.power_dbm == 10.0
    assert lt.radio_id == 1


def test_transmitter_record_is_local_defaults_false():
    rec = TransmitterRecord(
        entity_id=(1, 2, 3),
        radio_id=4,
        state=TransmitterState.IDLE,
        frequency_hz=30_000_000.0,
        power_dbm=10.0,
        modulation_major="AM",
        exercise_id=1,
        last_seen=datetime.now(),
    )
    assert rec.is_local is False


def test_transmitter_record_is_local_can_be_set():
    rec = TransmitterRecord(
        entity_id=(1, 2, 3),
        radio_id=4,
        state=TransmitterState.IDLE,
        frequency_hz=30_000_000.0,
        power_dbm=10.0,
        modulation_major="AM",
        exercise_id=1,
        last_seen=datetime.now(),
        is_local=True,
    )
    assert rec.is_local is True


def test_transmitter_record_name_defaults_none():
    rec = TransmitterRecord(
        entity_id=(1, 2, 3),
        radio_id=4,
        state=TransmitterState.IDLE,
        frequency_hz=30_000_000.0,
        power_dbm=10.0,
        modulation_major="AM",
        exercise_id=1,
        last_seen=datetime.now(),
    )
    assert rec.name is None


def test_transmitter_record_name_can_be_set():
    rec = TransmitterRecord(
        entity_id=(1, 2, 3),
        radio_id=4,
        state=TransmitterState.IDLE,
        frequency_hz=30_000_000.0,
        power_dbm=10.0,
        modulation_major="AM",
        exercise_id=1,
        last_seen=datetime.now(),
        name="Command Net",
    )
    assert rec.name == "Command Net"


def test_local_transmitter_bandwidth_hz_defaults_to_zero():
    lt = LocalTransmitter(
        name="R1", frequency_hz=148_500_000.0,
        modulation_major="NBFM (25 kHz)", power_dbm=10.0, radio_id=1,
    )
    assert lt.bandwidth_hz == 0.0


def test_transmitter_record_bandwidth_hz_defaults_to_zero():
    record = TransmitterRecord(
        entity_id=(1, 1, 1), radio_id=1, state=TransmitterState.IDLE,
        frequency_hz=148_500_000.0, power_dbm=0.0, modulation_major="No Statement",
        exercise_id=1, last_seen=datetime.now(),
    )
    assert record.bandwidth_hz == 0.0
