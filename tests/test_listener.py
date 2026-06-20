import struct

import pytest
from PyQt6.QtWidgets import QApplication

from dis_radio.config import AppConfig
from dis_radio.models import TransmitterRecord
from dis_radio.network.listener import DISListener


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance() or QApplication([])
    return app


def _make_transmitter_pdu_bytes(site=1, app=2, entity=3, radio_id=4,
                                exercise_id=1) -> bytes:
    """Build raw TransmitterPdu bytes (DIS 7, pduType=25)."""
    total_len = 104
    buf = struct.pack('>BBBBIHBB', 7, exercise_id, 25, 4, 0, total_len, 0, 0)
    buf += struct.pack('>HHH', site, app, entity)
    buf += struct.pack('>H', radio_id)
    buf += struct.pack('>BBHBBBB', 0, 0, 0, 0, 0, 0, 0)
    buf += struct.pack('>BB', 2, 0)  # state=TRANSMITTING, inputSource
    buf += struct.pack('>H', 0)
    buf += struct.pack('>ddd', 0.0, 0.0, 0.0)
    buf += struct.pack('>fff', 0.0, 0.0, 0.0)
    buf += struct.pack('>HH', 0, 0)
    buf += struct.pack('>q', 148_500_000)
    buf += struct.pack('>f', 0.0)
    buf += struct.pack('>f', 10.0)
    buf += struct.pack('>HHHH', 0, 3, 0, 0)  # FM
    buf += struct.pack('>HH', 0, 0)
    buf += struct.pack('>BHB', 0, 0, 0)
    return buf


def test_listener_emits_transmitter_updated(qapp):
    config = AppConfig()
    listener = DISListener(config)

    received = []
    listener.transmitter_updated.connect(received.append)

    data = _make_transmitter_pdu_bytes(exercise_id=1)
    listener._handle_packet(data)

    assert len(received) == 1
    assert isinstance(received[0], TransmitterRecord)
    assert received[0].exercise_id == 1


def test_listener_filters_by_exercise_id(qapp):
    config = AppConfig()
    config.network.exercise_id = 2
    listener = DISListener(config)

    received = []
    listener.transmitter_updated.connect(received.append)

    listener._handle_packet(_make_transmitter_pdu_bytes(exercise_id=1))
    listener._handle_packet(_make_transmitter_pdu_bytes(exercise_id=2))

    assert len(received) == 1
    assert received[0].exercise_id == 2


def test_listener_no_filter_passes_all(qapp):
    config = AppConfig()
    config.network.exercise_id = None
    listener = DISListener(config)

    received = []
    listener.transmitter_updated.connect(received.append)

    listener._handle_packet(_make_transmitter_pdu_bytes(exercise_id=1))
    listener._handle_packet(_make_transmitter_pdu_bytes(exercise_id=3))

    assert len(received) == 2


def test_listener_ignores_bad_data(qapp):
    config = AppConfig()
    listener = DISListener(config)

    received = []
    listener.transmitter_updated.connect(received.append)
    listener._handle_packet(b"\x00\x01\x02")  # garbage bytes

    assert len(received) == 0
