from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from enum import IntEnum
from typing import Optional

TransmitterKey = tuple[int, int, int, int]  # site, application, entity, radio_id


class TransmitterState(IntEnum):
    OFF = 0
    IDLE = 1
    TRANSMITTING = 2


@dataclass
class LocalTransmitter:
    name: str
    frequency_hz: float
    modulation_major: str
    power_dbm: float
    radio_id: int  # auto-assigned; stored in config
    bandwidth_hz: float = 0.0


@dataclass
class TransmitterRecord:
    entity_id: tuple[int, int, int]
    radio_id: int
    state: TransmitterState
    frequency_hz: float
    power_dbm: float
    modulation_major: str
    exercise_id: int
    last_seen: datetime
    audio_enabled: bool = False
    is_local: bool = False
    name: Optional[str] = None  # set for local transmitters; None for observed
    bandwidth_hz: float = 0.0

    @property
    def key(self) -> TransmitterKey:
        return (*self.entity_id, self.radio_id)
