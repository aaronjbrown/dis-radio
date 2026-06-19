from datetime import datetime
from unittest.mock import MagicMock, patch
import pytest
from PyQt6.QtWidgets import QApplication

from dis_radio.config import AppConfig, LocalTransmitterConfig
from dis_radio.models import LocalTransmitter, TransmitterState
from dis_radio.local_transmitter_manager import LocalTransmitterManager


@pytest.fixture(scope="session")
def qapp():
    return QApplication.instance() or QApplication([])


def _make_lt(name="Test", freq=30_000_000.0, mod="AM (DSB)", power=10.0, radio_id=0, bw=0.0) -> LocalTransmitter:
    return LocalTransmitter(name=name, frequency_hz=freq, modulation_major=mod,
                            power_dbm=power, radio_id=radio_id, bandwidth_hz=bw)


def _make_manager(qapp, transmitters=None):
    config = AppConfig()
    config.local_transmitters = LocalTransmitterConfig(
        starting_radio_id=1,
        transmitters=transmitters or [],
    )
    mock_sender = MagicMock()
    with patch("dis_radio.local_transmitter_manager.save_config"):
        manager = LocalTransmitterManager(config, mock_sender)
    return manager, config, mock_sender


def test_add_assigns_starting_radio_id_when_list_empty(qapp):
    manager, config, _ = _make_manager(qapp)
    with patch("dis_radio.local_transmitter_manager.save_config"):
        manager.add(_make_lt(name="Net A"))
    assert config.local_transmitters.transmitters[0].radio_id == 1


def test_add_assigns_next_id_after_existing(qapp):
    existing = [_make_lt(name="Net A", radio_id=3)]
    manager, config, _ = _make_manager(qapp, transmitters=existing)
    with patch("dis_radio.local_transmitter_manager.save_config"):
        manager.add(_make_lt(name="Net B"))
    assert config.local_transmitters.transmitters[1].radio_id == 4


def test_add_emits_transmitter_updated(qapp):
    manager, _, _ = _make_manager(qapp)
    emitted = []
    manager.transmitter_updated.connect(emitted.append)
    with patch("dis_radio.local_transmitter_manager.save_config"):
        manager.add(_make_lt(name="Net A"))
    assert len(emitted) == 1
    assert emitted[0].is_local is True
    assert emitted[0].modulation_major == "AM (DSB)"


def test_add_record_uses_transmit_config_entity(qapp):
    manager, config, _ = _make_manager(qapp)
    config.transmit.site_id = 10
    config.transmit.app_id = 20
    config.transmit.entity_id = 30
    emitted = []
    manager.transmitter_updated.connect(emitted.append)
    with patch("dis_radio.local_transmitter_manager.save_config"):
        manager.add(_make_lt())
    assert emitted[0].entity_id == (10, 20, 30)


def test_remove_deletes_from_config(qapp):
    existing = [_make_lt(name="Net A", radio_id=1), _make_lt(name="Net B", radio_id=2)]
    manager, config, _ = _make_manager(qapp, transmitters=existing)
    with patch("dis_radio.local_transmitter_manager.save_config"):
        manager.remove(1)
    assert len(config.local_transmitters.transmitters) == 1
    assert config.local_transmitters.transmitters[0].radio_id == 2


def test_remove_emits_transmitter_removed(qapp):
    existing = [_make_lt(name="Net A", radio_id=5)]
    manager, config, _ = _make_manager(qapp, transmitters=existing)
    config.transmit.site_id = 1
    config.transmit.app_id = 1
    config.transmit.entity_id = 1
    removed_keys = []
    manager.transmitter_removed.connect(removed_keys.append)
    with patch("dis_radio.local_transmitter_manager.save_config"):
        manager.remove(5)
    assert removed_keys == [(1, 1, 1, 5)]


def test_update_replaces_transmitter_in_config(qapp):
    existing = [_make_lt(name="Old Name", radio_id=1)]
    manager, config, _ = _make_manager(qapp, transmitters=existing)
    updated = _make_lt(name="New Name", freq=50_000_000.0, radio_id=1)
    with patch("dis_radio.local_transmitter_manager.save_config"):
        manager.update(updated)
    assert config.local_transmitters.transmitters[0].name == "New Name"
    assert config.local_transmitters.transmitters[0].frequency_hz == 50_000_000.0


def test_update_emits_transmitter_updated(qapp):
    existing = [_make_lt(name="Old", radio_id=1)]
    manager, _, _ = _make_manager(qapp, transmitters=existing)
    emitted = []
    manager.transmitter_updated.connect(emitted.append)
    with patch("dis_radio.local_transmitter_manager.save_config"):
        manager.update(_make_lt(name="New", radio_id=1))
    assert len(emitted) == 1
    assert emitted[0].is_local is True


def test_heartbeat_emits_record_for_each_transmitter(qapp):
    existing = [_make_lt(name="A", radio_id=1), _make_lt(name="B", radio_id=2)]
    manager, _, _ = _make_manager(qapp, transmitters=existing)
    emitted = []
    manager.transmitter_updated.connect(emitted.append)
    manager._on_heartbeat()
    assert len(emitted) == 2
    assert all(r.is_local for r in emitted)


def test_heartbeat_sends_pdu_for_each_transmitter_when_active(qapp):
    existing = [_make_lt(name="A", radio_id=1), _make_lt(name="B", radio_id=2)]
    manager, config, mock_sender = _make_manager(qapp, transmitters=existing)
    config.transmit.site_id = 1
    config.transmit.app_id = 1
    config.transmit.entity_id = 1
    with patch("dis_radio.local_transmitter_manager.save_config"):
        manager.start(exercise_id=1)
    mock_sender.reset_mock()
    manager._on_heartbeat()
    assert mock_sender.send_transmitter.call_count == 2


def test_heartbeat_does_not_send_pdu_when_inactive(qapp):
    existing = [_make_lt(name="A", radio_id=1)]
    manager, _, mock_sender = _make_manager(qapp, transmitters=existing)
    mock_sender.reset_mock()
    manager._on_heartbeat()
    mock_sender.send_transmitter.assert_not_called()


def test_suppress_prevents_pdu_on_heartbeat(qapp):
    existing = [_make_lt(name="A", radio_id=1)]
    manager, config, mock_sender = _make_manager(qapp, transmitters=existing)
    config.transmit.site_id = 1
    config.transmit.app_id = 1
    config.transmit.entity_id = 1
    with patch("dis_radio.local_transmitter_manager.save_config"):
        manager.start(exercise_id=1)
    mock_sender.reset_mock()
    key = (1, 1, 1, 1)
    manager.suppress(key)
    manager._on_heartbeat()
    mock_sender.send_transmitter.assert_not_called()


def test_unsuppress_resumes_pdu_on_heartbeat(qapp):
    existing = [_make_lt(name="A", radio_id=1)]
    manager, config, mock_sender = _make_manager(qapp, transmitters=existing)
    config.transmit.site_id = 1
    config.transmit.app_id = 1
    config.transmit.entity_id = 1
    with patch("dis_radio.local_transmitter_manager.save_config"):
        manager.start(exercise_id=1)
    mock_sender.reset_mock()
    key = (1, 1, 1, 1)
    manager.suppress(key)
    manager.unsuppress(key)
    manager._on_heartbeat()
    mock_sender.send_transmitter.assert_called_once()


def test_suppress_does_not_prevent_record_emission(qapp):
    existing = [_make_lt(name="A", radio_id=1)]
    manager, config, _ = _make_manager(qapp, transmitters=existing)
    config.transmit.site_id = 1
    config.transmit.app_id = 1
    config.transmit.entity_id = 1
    key = (1, 1, 1, 1)
    manager.suppress(key)
    emitted = []
    manager.transmitter_updated.connect(emitted.append)
    manager._on_heartbeat()
    assert len(emitted) == 1


def test_load_emits_records_without_sending_pdus(qapp):
    existing = [_make_lt(name="A", radio_id=1), _make_lt(name="B", radio_id=2)]
    manager, _, mock_sender = _make_manager(qapp, transmitters=existing)
    emitted = []
    manager.transmitter_updated.connect(emitted.append)
    manager.load()
    assert len(emitted) == 2
    assert all(r.is_local for r in emitted)
    mock_sender.send_transmitter.assert_not_called()


def test_load_sets_name_on_emitted_records(qapp):
    existing = [_make_lt(name="Command Net", radio_id=1)]
    manager, _, _ = _make_manager(qapp, transmitters=existing)
    emitted = []
    manager.transmitter_updated.connect(emitted.append)
    manager.load()
    assert emitted[0].name == "Command Net"


def test_add_passes_power_and_bandwidth_to_sender_when_active(qapp):
    manager, config, mock_sender = _make_manager(qapp)
    config.transmit.site_id = 1
    config.transmit.app_id = 1
    config.transmit.entity_id = 1
    with patch("dis_radio.local_transmitter_manager.save_config"):
        manager.start(exercise_id=1)
    mock_sender.reset_mock()
    with patch("dis_radio.local_transmitter_manager.save_config"):
        manager.add(_make_lt(name="Net A", power=37.0, bw=25_000.0))
    call_kwargs = mock_sender.send_transmitter.call_args[1]
    assert call_kwargs["power_dbm"] == 37.0
    assert call_kwargs["bandwidth_hz"] == 25_000.0
    assert call_kwargs["modulation_major"] == "AM (DSB)"
