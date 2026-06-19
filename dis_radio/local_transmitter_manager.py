from __future__ import annotations
import logging
from datetime import datetime
from typing import Optional

from PyQt6.QtCore import QObject, QTimer, pyqtSignal

from dis_radio.config import AppConfig
from dis_radio.config import save as save_config
from dis_radio.models import LocalTransmitter, TransmitterKey, TransmitterRecord, TransmitterState
from dis_radio.network.sender import DISSender

log = logging.getLogger(__name__)

_HEARTBEAT_INTERVAL_MS = 5000


class LocalTransmitterManager(QObject):
    transmitter_updated = pyqtSignal(TransmitterRecord)
    transmitter_removed = pyqtSignal(object)  # TransmitterKey

    def __init__(
        self,
        config: AppConfig,
        sender: DISSender,
        *,
        parent: Optional[QObject] = None,
    ) -> None:
        super().__init__(parent)
        self._config = config
        self._sender = sender
        self._exercise_id: int = 1
        self._active: bool = False
        self._suppressed: set[TransmitterKey] = set()

        self._heartbeat = QTimer(self)
        self._heartbeat.setInterval(_HEARTBEAT_INTERVAL_MS)
        self._heartbeat.timeout.connect(self._on_heartbeat)

    # ------------------------------------------------------------------ #
    # Public API                                                           #
    # ------------------------------------------------------------------ #

    def start(self, exercise_id: int) -> None:
        self._exercise_id = exercise_id
        self._active = True
        self._heartbeat.start()
        for lt in self._config.local_transmitters.transmitters:
            self.transmitter_updated.emit(self._make_record(lt))
            self._sender.send_transmitter(
                self._key(lt.radio_id), lt.frequency_hz, TransmitterState.IDLE, exercise_id,
                power_dbm=lt.power_dbm, bandwidth_hz=lt.bandwidth_hz,
                modulation_major=lt.modulation_major,
            )

    def stop(self) -> None:
        self._active = False
        self._heartbeat.stop()

    def load(self) -> None:
        """Emit records for all local transmitters without starting the timer or sending DIS PDUs.

        Call once at startup so tiles appear immediately before the user connects.
        """
        for lt in self._config.local_transmitters.transmitters:
            self.transmitter_updated.emit(self._make_record(lt))

    def add(self, lt: LocalTransmitter) -> None:
        existing = self._config.local_transmitters.transmitters
        lt.radio_id = (
            max(t.radio_id for t in existing) + 1
            if existing
            else self._config.local_transmitters.starting_radio_id
        )
        existing.append(lt)
        save_config(self._config)
        self.transmitter_updated.emit(self._make_record(lt))
        if self._active:
            self._sender.send_transmitter(
                self._key(lt.radio_id), lt.frequency_hz, TransmitterState.IDLE, self._exercise_id,
                power_dbm=lt.power_dbm, bandwidth_hz=lt.bandwidth_hz,
                modulation_major=lt.modulation_major,
            )

    def remove(self, radio_id: int) -> None:
        key = self._key(radio_id)
        self._config.local_transmitters.transmitters = [
            t for t in self._config.local_transmitters.transmitters if t.radio_id != radio_id
        ]
        save_config(self._config)
        if self._active:
            self._sender.send_transmitter(key, 0.0, TransmitterState.OFF, self._exercise_id)
        self.transmitter_removed.emit(key)

    def update(self, lt: LocalTransmitter) -> None:
        transmitters = self._config.local_transmitters.transmitters
        for i, t in enumerate(transmitters):
            if t.radio_id == lt.radio_id:
                transmitters[i] = lt
                break
        save_config(self._config)
        self.transmitter_updated.emit(self._make_record(lt))
        if self._active:
            self._sender.send_transmitter(
                self._key(lt.radio_id), lt.frequency_hz, TransmitterState.IDLE, self._exercise_id,
                power_dbm=lt.power_dbm, bandwidth_hz=lt.bandwidth_hz,
                modulation_major=lt.modulation_major,
            )

    def reconfigure(self, config: AppConfig) -> None:
        self._config = config

    def suppress(self, key: TransmitterKey) -> None:
        self._suppressed.add(key)

    def unsuppress(self, key: TransmitterKey) -> None:
        self._suppressed.discard(key)

    # ------------------------------------------------------------------ #
    # Internal                                                             #
    # ------------------------------------------------------------------ #

    def _on_heartbeat(self) -> None:
        for lt in self._config.local_transmitters.transmitters:
            key = self._key(lt.radio_id)
            self.transmitter_updated.emit(self._make_record(lt))
            if self._active and key not in self._suppressed:
                self._sender.send_transmitter(
                    key, lt.frequency_hz, TransmitterState.IDLE, self._exercise_id,
                    power_dbm=lt.power_dbm, bandwidth_hz=lt.bandwidth_hz,
                    modulation_major=lt.modulation_major,
                )

    def _key(self, radio_id: int) -> TransmitterKey:
        return (
            self._config.transmit.site_id,
            self._config.transmit.app_id,
            self._config.transmit.entity_id,
            radio_id,
        )

    def _make_record(self, lt: LocalTransmitter) -> TransmitterRecord:
        return TransmitterRecord(
            entity_id=(
                self._config.transmit.site_id,
                self._config.transmit.app_id,
                self._config.transmit.entity_id,
            ),
            radio_id=lt.radio_id,
            state=TransmitterState.IDLE,
            frequency_hz=lt.frequency_hz,
            power_dbm=lt.power_dbm,
            bandwidth_hz=lt.bandwidth_hz,
            modulation_major=lt.modulation_major,
            exercise_id=self._exercise_id,
            last_seen=datetime.now(),
            is_local=True,
            name=lt.name,
        )
