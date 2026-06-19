from datetime import datetime
from unittest.mock import MagicMock
import pytest
from PyQt6.QtWidgets import QApplication
from dis_radio.config import AppConfig
from dis_radio.models import TransmitterRecord, TransmitterState
from dis_radio.ptt_controller import PTTController


@pytest.fixture(scope="session")
def qapp():
    return QApplication.instance() or QApplication([])


def _make_record(
    freq: float = 148_500_000.0,
    power_dbm: float = 0.0,
    bandwidth_hz: float = 0.0,
) -> TransmitterRecord:
    return TransmitterRecord(
        entity_id=(10, 1, 5),
        radio_id=1,
        state=TransmitterState.IDLE,
        frequency_hz=freq,
        power_dbm=power_dbm,
        bandwidth_hz=bandwidth_hz,
        modulation_major="NBFM (25 kHz)",
        exercise_id=1,
        last_seen=datetime.now(),
    )


def _make_controller(qapp, config=None):
    config = config or AppConfig()
    mock_sender = MagicMock()
    mock_player = MagicMock()
    mock_capture = MagicMock()
    mock_capture.start.return_value = True
    controller = PTTController(config, mock_sender, mock_player, _capture=mock_capture)
    return controller, mock_sender, mock_player, mock_capture


def test_select_primary_stores_key_and_frequency(qapp):
    controller, _, _, _ = _make_controller(qapp)
    key = (1, 2, 3, 4)
    controller.select(key, _make_record(freq=456_000_000.0), "primary")
    assert controller._primary_key == key
    assert controller._primary_freq == 456_000_000.0


def test_select_secondary_stores_key_and_frequency(qapp):
    controller, _, _, _ = _make_controller(qapp)
    key = (5, 6, 7, 8)
    controller.select(key, _make_record(freq=123_000_000.0), "secondary")
    assert controller._secondary_key == key
    assert controller._secondary_freq == 123_000_000.0


def test_deselect_primary_clears_key(qapp):
    controller, _, _, _ = _make_controller(qapp)
    controller.select((1, 2, 3, 4), _make_record(), "primary")
    controller.deselect("primary")
    assert controller._primary_key is None


def test_deselect_secondary_clears_key(qapp):
    controller, _, _, _ = _make_controller(qapp)
    controller.select((1, 2, 3, 4), _make_record(), "secondary")
    controller.deselect("secondary")
    assert controller._secondary_key is None


def test_ptt_press_starts_capture(qapp):
    controller, _, _, mock_capture = _make_controller(qapp)
    controller.select((1, 2, 3, 4), _make_record(), "primary")
    controller.ptt_press("primary")
    mock_capture.start.assert_called_once()


def test_ptt_press_mutes_tx_radio_in_player(qapp):
    controller, _, mock_player, _ = _make_controller(qapp)
    key = (1, 2, 3, 4)
    controller.select(key, _make_record(), "primary")
    controller.ptt_press("primary")
    mock_player.mute_for_tx.assert_called_with(key)


def test_ptt_press_emits_ptt_active_true(qapp):
    controller, _, _, _ = _make_controller(qapp)
    controller.select((1, 2, 3, 4), _make_record(), "primary")
    active_states = []
    controller.ptt_active.connect(active_states.append)
    controller.ptt_press("primary")
    assert active_states == ["primary"]


def test_ptt_press_sends_transmitting_heartbeat(qapp):
    controller, mock_sender, _, _ = _make_controller(qapp)
    key = (1, 2, 3, 4)
    controller.select(key, _make_record(freq=148_500_000.0), "primary")
    controller.ptt_press("primary")
    # Should send a TransmitterPDU with TRANSMITTING state immediately
    mock_sender.send_transmitter.assert_called()
    args = mock_sender.send_transmitter.call_args[0]
    assert args[2] == TransmitterState.TRANSMITTING


def test_ptt_release_stops_capture(qapp):
    controller, _, _, mock_capture = _make_controller(qapp)
    controller.select((1, 2, 3, 4), _make_record(), "primary")
    controller.ptt_press("primary")
    mock_capture.reset_mock()
    controller.ptt_release("primary")
    mock_capture.stop.assert_called_once()


def test_ptt_release_unmutes_tx_radio(qapp):
    controller, _, mock_player, _ = _make_controller(qapp)
    key = (1, 2, 3, 4)
    controller.select(key, _make_record(), "primary")
    controller.ptt_press("primary")
    mock_player.reset_mock()
    controller.ptt_release("primary")
    mock_player.unmute_for_tx.assert_called_with(key)


def test_ptt_release_emits_ptt_active_false(qapp):
    controller, _, _, _ = _make_controller(qapp)
    controller.select((1, 2, 3, 4), _make_record(), "primary")
    controller.ptt_press("primary")
    active_states = []
    controller.ptt_active.connect(active_states.append)
    controller.ptt_release("primary")
    assert active_states == [""]


def test_ptt_press_no_selection_does_nothing(qapp):
    controller, mock_sender, mock_player, mock_capture = _make_controller(qapp)
    # No radio selected — press should be silently ignored
    controller.ptt_press("primary")
    mock_capture.start.assert_not_called()
    mock_player.disable.assert_not_called()
    mock_sender.send_transmitter.assert_not_called()


def test_ptt_press_mic_failure_emits_error(qapp):
    controller, _, _, mock_capture = _make_controller(qapp)
    mock_capture.start.return_value = False
    controller.select((1, 2, 3, 4), _make_record(), "primary")
    errors = []
    controller.ptt_error.connect(errors.append)
    controller.ptt_press("primary")
    assert len(errors) == 1


def test_audio_chunk_sent_as_signal_pdu(qapp):
    """Verify that audio chunks from AudioCapture are forwarded to DISSender."""
    controller, mock_sender, _, mock_capture = _make_controller(qapp)
    key = (1, 2, 3, 4)
    controller.select(key, _make_record(), "primary")
    controller.ptt_press("primary")

    # Simulate AudioCapture calling on_chunk by extracting and calling the callback
    on_chunk = mock_capture.start.call_args[0][0]
    audio_data = bytes([0xFF] * 160)
    on_chunk(audio_data)

    mock_sender.send_signal.assert_called_once()
    args = mock_sender.send_signal.call_args[0]
    assert args[0] == controller._our_key("primary")  # transmit on our own key, not remote
    assert args[1] == audio_data  # audio bytes passed through


def test_deselect_while_ptt_active_stops_capture(qapp):
    controller, _, _, mock_capture = _make_controller(qapp)
    controller.select((1, 2, 3, 4), _make_record(), "primary")
    controller.ptt_press("primary")
    mock_capture.reset_mock()
    controller.deselect("primary")
    mock_capture.stop.assert_called_once()


def test_ptt_press_sends_modulation_from_selected_record(qapp):
    controller, mock_sender, _, _ = _make_controller(qapp)
    controller.select((1, 2, 3, 4), _make_record(), "primary")
    controller.ptt_press("primary")
    kwargs = mock_sender.send_transmitter.call_args[1]
    assert kwargs.get("modulation_major") == "NBFM (25 kHz)"


def test_select_stores_modulation(qapp):
    controller, _, _, _ = _make_controller(qapp)
    controller.select((1, 2, 3, 4), _make_record(), "primary")
    assert controller._primary_mod == "NBFM (25 kHz)"


def test_select_stores_power_and_bandwidth(qapp):
    controller, _, _, _ = _make_controller(qapp)
    controller.select((1, 2, 3, 4), _make_record(power_dbm=37.0, bandwidth_hz=25_000.0), "primary")
    assert controller._primary_power_dbm == 37.0
    assert controller._primary_bandwidth_hz == 25_000.0


def test_deselect_clears_power_and_bandwidth(qapp):
    controller, _, _, _ = _make_controller(qapp)
    controller.select((1, 2, 3, 4), _make_record(power_dbm=37.0, bandwidth_hz=25_000.0), "primary")
    controller.deselect("primary")
    assert controller._primary_power_dbm == 0.0
    assert controller._primary_bandwidth_hz == 0.0


def test_ptt_press_sends_power_and_bandwidth(qapp):
    controller, mock_sender, _, _ = _make_controller(qapp)
    controller.select((1, 2, 3, 4), _make_record(power_dbm=37.0, bandwidth_hz=25_000.0), "primary")
    controller.ptt_press("primary")
    kwargs = mock_sender.send_transmitter.call_args[1]
    assert kwargs.get("power_dbm") == 37.0
    assert kwargs.get("bandwidth_hz") == 25_000.0
