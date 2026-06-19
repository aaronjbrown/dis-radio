from __future__ import annotations
import logging
import socket
import struct

from PyQt6.QtCore import QThread, pyqtSignal

from dis_radio.config import AppConfig
from dis_radio.dis.parser import ParsedKind, parse_pdu
from dis_radio.models import TransmitterRecord

log = logging.getLogger(__name__)

_SOCKET_TIMEOUT = 1.0  # seconds; controls how quickly stop() takes effect


class DISListener(QThread):
    transmitter_updated = pyqtSignal(TransmitterRecord)
    signal_received = pyqtSignal(object, bytes, int, int)  # key, audio, encoding, sample_rate

    def __init__(self, config: AppConfig) -> None:
        super().__init__()
        self._config = config
        self._running = False

    # ------------------------------------------------------------------ #
    # Public API                                                           #
    # ------------------------------------------------------------------ #

    def stop(self) -> None:
        self._running = False

    def reconfigure(self, config: AppConfig) -> None:
        """Update config. Caller must stop() + start() to rebind socket."""
        self._config = config

    # ------------------------------------------------------------------ #
    # QThread                                                              #
    # ------------------------------------------------------------------ #

    def run(self) -> None:
        self._running = True
        sock = self._bind()
        if sock is None:
            return
        try:
            while self._running:
                try:
                    data, _ = sock.recvfrom(65535)
                    self._handle_packet(data)
                except socket.timeout:
                    continue
        finally:
            sock.close()

    # ------------------------------------------------------------------ #
    # Internal                                                             #
    # ------------------------------------------------------------------ #

    def _bind(self) -> socket.socket | None:
        try:
            sock = socket.socket(
                socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP
            )
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.settimeout(_SOCKET_TIMEOUT)
            sock.bind(("", self._config.network.port))
            iface = self._config.network.interface or "0.0.0.0"
            mreq = struct.pack(
                "4s4s",
                socket.inet_aton(self._config.network.multicast_group),
                socket.inet_aton(iface),
            )
            sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
            return sock
        except OSError as exc:
            log.error("Failed to bind DIS socket: %s", exc)
            return None

    def _handle_packet(self, data: bytes) -> None:
        result = parse_pdu(data)
        if result is None:
            return
        kind = result[0]
        if kind == ParsedKind.TRANSMITTER:
            _, record = result
            if self._passes_filter(record.exercise_id):
                self.transmitter_updated.emit(record)
        elif kind == ParsedKind.SIGNAL:
            _, key, audio, encoding, sample_rate = result
            if encoding != -1:
                self.signal_received.emit(key, audio, encoding, sample_rate)

    def _passes_filter(self, exercise_id: int) -> bool:
        configured = self._config.network.exercise_id
        return configured is None or configured == exercise_id
