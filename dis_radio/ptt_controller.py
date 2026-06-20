from __future__ import annotations

import logging

from PyQt6.QtCore import QObject, QTimer, pyqtSignal

from dis_radio.audio.capture import AudioCapture
from dis_radio.audio.player import AudioPlayer
from dis_radio.config import AppConfig
from dis_radio.models import TransmitterKey, TransmitterRecord, TransmitterState
from dis_radio.network.sender import DISSender

log = logging.getLogger(__name__)

_HEARTBEAT_INTERVAL_MS = 5000
_SAMPLE_RATE = 8000


class PTTController(QObject):
    # Emits the active role ("primary"/"secondary"), or "" when inactive
    ptt_active = pyqtSignal(str)
    ptt_error = pyqtSignal(str)

    def __init__(
        self,
        config: AppConfig,
        sender: DISSender,
        player: AudioPlayer,
        *,
        _capture: AudioCapture | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._config = config
        self._sender = sender
        self._player = player
        self._capture = _capture or AudioCapture(config.transmit.input_device)

        self._primary_key: TransmitterKey | None = None
        self._primary_freq: float = 0.0
        self._primary_mod: str = "No Statement"
        self._secondary_key: TransmitterKey | None = None
        self._secondary_freq: float = 0.0
        self._secondary_mod: str = "No Statement"
        self._primary_power_dbm: float = 0.0
        self._secondary_power_dbm: float = 0.0
        self._primary_bandwidth_hz: float = 0.0
        self._secondary_bandwidth_hz: float = 0.0
        self._active_role: str | None = None

        self._heartbeat = QTimer(self)
        self._heartbeat.setInterval(_HEARTBEAT_INTERVAL_MS)
        self._heartbeat.timeout.connect(self._send_heartbeat)

    # ------------------------------------------------------------------ #
    # Public API                                                           #
    # ------------------------------------------------------------------ #

    def select(self, key: TransmitterKey, record: TransmitterRecord, role: str) -> None:
        if role == "primary":
            self._primary_key = key
            self._primary_freq = record.frequency_hz
            self._primary_mod = record.modulation_major
            self._primary_power_dbm = record.power_dbm
            self._primary_bandwidth_hz = record.bandwidth_hz
        else:
            self._secondary_key = key
            self._secondary_freq = record.frequency_hz
            self._secondary_mod = record.modulation_major
            self._secondary_power_dbm = record.power_dbm
            self._secondary_bandwidth_hz = record.bandwidth_hz

    def deselect(self, role: str) -> None:
        if role == "primary":
            if self._active_role == "primary":
                self._stop_ptt("primary")
            self._primary_key = None
            self._primary_freq = 0.0
            self._primary_mod = "No Statement"
            self._primary_power_dbm = 0.0
            self._primary_bandwidth_hz = 0.0
        else:
            if self._active_role == "secondary":
                self._stop_ptt("secondary")
            self._secondary_key = None
            self._secondary_freq = 0.0
            self._secondary_mod = "No Statement"
            self._secondary_power_dbm = 0.0
            self._secondary_bandwidth_hz = 0.0

    def ptt_press(self, role: str) -> None:
        key = self._primary_key if role == "primary" else self._secondary_key
        if key is None:
            return

        freq = self._primary_freq if role == "primary" else self._secondary_freq
        mod = self._primary_mod if role == "primary" else self._secondary_mod
        power = (
            self._primary_power_dbm if role == "primary" else self._secondary_power_dbm
        )
        bw = (
            self._primary_bandwidth_hz
            if role == "primary"
            else self._secondary_bandwidth_hz
        )
        our_key = self._our_key(role)
        exercise_id = self._config.network.exercise_id or 1

        def _on_chunk(audio_ulaw: bytes) -> None:
            self._sender.send_signal(our_key, audio_ulaw, _SAMPLE_RATE, exercise_id)

        success = self._capture.start(_on_chunk)
        if not success:
            self.ptt_error.emit("Failed to open microphone")
            return

        self._sender.send_transmitter(
            our_key, freq, TransmitterState.TRANSMITTING, exercise_id,
            modulation_major=mod, power_dbm=power, bandwidth_hz=bw,
        )
        self._player.mute_for_tx(key)
        self._active_role = role
        self.ptt_active.emit(role)

    def ptt_release(self, role: str) -> None:
        if self._active_role != role:
            return
        self._stop_ptt(role)

    def start_heartbeat(self) -> None:
        self._heartbeat.start()

    def stop_heartbeat(self) -> None:
        self._heartbeat.stop()

    def reconfigure(self, config: AppConfig, player: AudioPlayer | None = None) -> None:
        """Update config and optionally swap the AudioPlayer reference."""
        if self._active_role is not None:
            self._stop_ptt(self._active_role)
        self._config = config
        self._capture = AudioCapture(config.transmit.input_device)
        if player is not None:
            self._player = player

    def close(self) -> None:
        """Tear down PTT state cleanly — call before destroying the controller."""
        if self._active_role is not None:
            self._stop_ptt(self._active_role)
        self._capture.stop()
        self._heartbeat.stop()

    # ------------------------------------------------------------------ #
    # Internal                                                             #
    # ------------------------------------------------------------------ #

    def _our_key(self, role: str) -> TransmitterKey:
        radio_id = (
            self._config.transmit.primary_radio_id
            if role == "primary"
            else self._config.transmit.secondary_radio_id
        )
        return (
            self._config.transmit.site_id,
            self._config.transmit.app_id,
            self._config.transmit.entity_id,
            radio_id,
        )

    def _stop_ptt(self, role: str) -> None:
        key = self._primary_key if role == "primary" else self._secondary_key
        freq = self._primary_freq if role == "primary" else self._secondary_freq
        mod = self._primary_mod if role == "primary" else self._secondary_mod
        power = (
            self._primary_power_dbm if role == "primary" else self._secondary_power_dbm
        )
        bw = (
            self._primary_bandwidth_hz
            if role == "primary"
            else self._secondary_bandwidth_hz
        )
        our_key = self._our_key(role)
        exercise_id = self._config.network.exercise_id or 1

        self._capture.stop()
        if key is not None:
            self._sender.send_transmitter(
                our_key, freq, TransmitterState.IDLE, exercise_id,
                modulation_major=mod, power_dbm=power, bandwidth_hz=bw,
            )
            self._player.unmute_for_tx(key)
        self._active_role = None
        self.ptt_active.emit("")

    def _send_heartbeat(self) -> None:
        exercise_id = self._config.network.exercise_id or 1
        for role, key, freq, mod, power, bw in [
            (
                "primary", self._primary_key,
                self._primary_freq, self._primary_mod,
                self._primary_power_dbm, self._primary_bandwidth_hz,
            ),
            (
                "secondary", self._secondary_key,
                self._secondary_freq, self._secondary_mod,
                self._secondary_power_dbm, self._secondary_bandwidth_hz,
            ),
        ]:
            if key is None:
                continue
            state = (
                TransmitterState.TRANSMITTING
                if self._active_role == role
                else TransmitterState.IDLE
            )
            self._sender.send_transmitter(
                self._our_key(role), freq, state, exercise_id,
                modulation_major=mod, power_dbm=power, bandwidth_hz=bw,
            )
