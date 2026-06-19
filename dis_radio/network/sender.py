from __future__ import annotations
import logging
import socket
import struct
import time

from dis_radio.config import AppConfig
from dis_radio.dis.modulation import PRESETS
from dis_radio.models import TransmitterKey, TransmitterState

log = logging.getLogger(__name__)

_PROTOCOL_VERSION = 7
_PDU_FAMILY_RADIO = 4
_PDU_TYPE_TRANSMITTER = 25
_PDU_TYPE_SIGNAL = 26
_TRANSMITTER_PDU_LEN = 104
_SIGNAL_PDU_FIXED_LEN = 12 + 6 + 2 + 2 + 2 + 4 + 2 + 2  # = 32
_ENCODING_SCHEME_ULAW = 0x0001

# DIS entity kind for radio (IEEE 1278.1 / SISO-REF-010 Table 6)
_ENTITY_KIND_RADIO = 7


def _dis_timestamp() -> int:
    secs = time.time() % 3600
    units = int(secs * (2**31 - 1) / 3600)
    return (units << 1) | 1   # bit 0 = 1 → absolute time reference


class _SocketWrapper:
    """Thin wrapper around a UDP socket exposing sendto as a regular Python method.

    Having sendto as a Python-level attribute (not a C slot) allows tests to
    monkeypatch it via pytest's monkeypatch.setattr.
    """

    def __init__(self, interface: str = "") -> None:
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        self._sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 1)
        if interface:
            self._sock.setsockopt(
                socket.IPPROTO_IP,
                socket.IP_MULTICAST_IF,
                socket.inet_aton(interface),
            )

    def sendto(self, data: bytes, addr: tuple[str, int]) -> None:
        self._sock.sendto(data, addr)

    def close(self) -> None:
        self._sock.close()


class DISSender:
    def __init__(self, config: AppConfig) -> None:
        self._group = config.network.multicast_group
        self._port = config.network.port
        self._sock = _SocketWrapper(config.network.interface)
        self._entity_type = _extract_entity_type(config)

    def reconfigure(self, config: AppConfig) -> None:
        """Update target multicast group, port, and entity type without recreating the socket."""
        self._group = config.network.multicast_group
        self._port = config.network.port
        self._entity_type = _extract_entity_type(config)

    def send_transmitter(
        self,
        key: TransmitterKey,
        frequency_hz: float,
        state: TransmitterState,
        exercise_id: int,
        modulation_major: str = "No Statement",
        power_dbm: float = 0.0,
        bandwidth_hz: float = 0.0,
    ) -> None:
        self._send(self._build_transmitter_pdu(
            key, frequency_hz, state, exercise_id, modulation_major, power_dbm, bandwidth_hz,
        ))

    def send_signal(
        self,
        key: TransmitterKey,
        audio_ulaw: bytes,
        sample_rate: int,
        exercise_id: int,
    ) -> None:
        self._send(self._build_signal_pdu(key, audio_ulaw, sample_rate, exercise_id))

    def close(self) -> None:
        self._sock.close()

    def _send(self, data: bytes) -> None:
        try:
            self._sock.sendto(data, (self._group, self._port))
        except OSError as exc:
            log.warning("UDP send failed: %s", exc)

    def _build_transmitter_pdu(
        self,
        key: TransmitterKey,
        frequency_hz: float,
        state: TransmitterState,
        exercise_id: int,
        modulation_major: str = "No Statement",
        power_dbm: float = 0.0,
        bandwidth_hz: float = 0.0,
    ) -> bytes:
        site, app, entity, radio_id = key
        ss, major, detail, system, _ = PRESETS.get(modulation_major, PRESETS["No Statement"])
        domain, country, category, subcategory, specific, extra = self._entity_type
        buf = struct.pack(
            '>BBBBIHBB',
            _PROTOCOL_VERSION, exercise_id, _PDU_TYPE_TRANSMITTER, _PDU_FAMILY_RADIO,
            _dis_timestamp(), _TRANSMITTER_PDU_LEN, 0, 0,
        )
        buf += struct.pack('>HHH', site, app, entity)
        buf += struct.pack('>H', radio_id)
        buf += struct.pack('>BBHBBBB',
                           _ENTITY_KIND_RADIO, domain, country, category, subcategory, specific, extra)
        buf += struct.pack('>BB', int(state), 0)
        buf += struct.pack('>H', 0)
        buf += struct.pack('>ddd', 0.0, 0.0, 0.0)
        buf += struct.pack('>fff', 0.0, 0.0, 0.0)
        buf += struct.pack('>HH', 0, 0)
        buf += struct.pack('>q', round(frequency_hz))
        buf += struct.pack('>f', bandwidth_hz)
        buf += struct.pack('>f', power_dbm)
        buf += struct.pack('>HHHH', ss, major, detail, system)
        buf += struct.pack('>HH', 0, 0)
        buf += struct.pack('>BHB', 0, 0, 0)
        return buf

    def _build_signal_pdu(
        self,
        key: TransmitterKey,
        audio_ulaw: bytes,
        sample_rate: int,
        exercise_id: int,
    ) -> bytes:
        site, app, entity, radio_id = key
        audio_len = len(audio_ulaw)
        total_len = _SIGNAL_PDU_FIXED_LEN + audio_len
        buf = struct.pack(
            '>BBBBIHBB',
            _PROTOCOL_VERSION, exercise_id, _PDU_TYPE_SIGNAL, _PDU_FAMILY_RADIO,
            _dis_timestamp(), total_len, 0, 0,
        )
        buf += struct.pack('>HHH', site, app, entity)
        buf += struct.pack('>H', radio_id)
        buf += struct.pack('>H', _ENCODING_SCHEME_ULAW)
        buf += struct.pack('>H', 0)
        buf += struct.pack('>I', sample_rate)
        buf += struct.pack('>H', audio_len * 8)
        buf += struct.pack('>H', 0)
        buf += audio_ulaw
        return buf


def _extract_entity_type(config: AppConfig) -> tuple[int, int, int, int, int, int]:
    tx = config.transmit
    return (
        tx.entity_type_domain,
        tx.entity_type_country,
        tx.entity_type_category,
        tx.entity_type_subcategory,
        tx.entity_type_specific,
        tx.entity_type_extra,
    )
