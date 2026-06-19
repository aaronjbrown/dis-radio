from __future__ import annotations
import logging
from datetime import datetime
from typing import Optional

from PyQt6.QtCore import QRect, QSize, Qt, QTimer
from PyQt6.QtGui import QKeyEvent
from PyQt6.QtWidgets import (
    QLabel, QLayout,
    QLayoutItem, QLineEdit, QMainWindow, QPushButton,
    QScrollArea, QStatusBar, QToolBar,
    QWidget,
)

from dis_radio.audio.player import AudioPlayer
from dis_radio.config import AppConfig, save as save_config
from dis_radio.gui.local_transmitter_dialog import LocalTransmitterDialog
from dis_radio.gui.settings_dialog import SettingsDialog
from dis_radio.gui.transmitter_tile import TransmitterTile
from dis_radio.local_transmitter_manager import LocalTransmitterManager
from dis_radio.models import LocalTransmitter, TransmitterKey, TransmitterRecord
from dis_radio.dis.modulation import channel_modulation_key
from dis_radio.network.listener import DISListener
from dis_radio.network.sender import DISSender
from dis_radio.ptt_controller import PTTController


log = logging.getLogger(__name__)


# ------------------------------------------------------------------ #
# QFlowLayout — wrapping tile grid                                    #
# ------------------------------------------------------------------ #

class QFlowLayout(QLayout):
    """Arranges child widgets in left-to-right rows, wrapping as needed."""

    def __init__(self, parent: Optional[QWidget] = None, h_spacing: int = 8, v_spacing: int = 8) -> None:
        super().__init__(parent)
        self._items: list[QLayoutItem] = []
        self._h_spacing = h_spacing
        self._v_spacing = v_spacing

    def addItem(self, item: QLayoutItem) -> None:  # noqa: N802
        self._items.append(item)

    def count(self) -> int:
        return len(self._items)

    def itemAt(self, index: int) -> Optional[QLayoutItem]:  # noqa: N802
        return self._items[index] if 0 <= index < len(self._items) else None

    def takeAt(self, index: int) -> Optional[QLayoutItem]:  # noqa: N802
        return self._items.pop(index) if 0 <= index < len(self._items) else None

    def hasHeightForWidth(self) -> bool:  # noqa: N802
        return True

    def heightForWidth(self, width: int) -> int:  # noqa: N802
        return self._do_layout(QRect(0, 0, width, 0), dry_run=True)

    def setGeometry(self, rect: QRect) -> None:  # noqa: N802
        super().setGeometry(rect)
        self._do_layout(rect, dry_run=False)

    def sizeHint(self) -> QSize:  # noqa: N802
        return self.minimumSize()

    def minimumSize(self) -> QSize:  # noqa: N802
        size = QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        margins = self.contentsMargins()
        size = QSize(
            size.width() + margins.left() + margins.right(),
            size.height() + margins.top() + margins.bottom(),
        )
        return size

    def removeWidget(self, widget: QWidget) -> None:  # noqa: N802
        for i, item in enumerate(self._items):
            if item.widget() is widget:
                self.takeAt(i)
                break

    def _do_layout(self, rect: QRect, *, dry_run: bool) -> int:
        margins = self.contentsMargins()
        x = rect.x() + margins.left()
        y = rect.y() + margins.top()
        row_height = 0
        right_limit = rect.right() - margins.right()

        for item in self._items:
            hint = item.sizeHint()
            if x + hint.width() > right_limit and x > rect.x() + margins.left():
                x = rect.x() + margins.left()
                y += row_height + self._v_spacing
                row_height = 0
            if not dry_run:
                item.setGeometry(QRect(x, y, hint.width(), hint.height()))
            x += hint.width() + self._h_spacing
            row_height = max(row_height, hint.height())

        return y + row_height - rect.y() + margins.bottom()


# ------------------------------------------------------------------ #
# MainWindow                                                          #
# ------------------------------------------------------------------ #

class MainWindow(QMainWindow):
    _RELEVANT_MODIFIERS: Qt.KeyboardModifier = (
        # Excludes KeypadModifier (numpad origin) and GroupSwitchModifier (X11 AltGr)
        Qt.KeyboardModifier.ShiftModifier
        | Qt.KeyboardModifier.ControlModifier
        | Qt.KeyboardModifier.AltModifier
        | Qt.KeyboardModifier.MetaModifier
    )
    _MODIFIER_NAME_MAP: dict[str, str] = {
        "Shift": "Shift",
        "Ctrl": "Control",
        "Alt": "Alt",
        "Meta": "Meta",
    }

    def __init__(self, config: AppConfig) -> None:
        super().__init__()
        self._config = config
        self._tiles: dict[TransmitterKey, TransmitterTile] = {}
        self._records: dict[TransmitterKey, TransmitterRecord] = {}
        self._primary_tx_tile: Optional[TransmitterTile] = None
        self._secondary_tx_tile: Optional[TransmitterTile] = None
        self._active_ptt_tile: Optional[TransmitterTile] = None

        # Channel consolidation index
        self._channel_index: dict[tuple[float, str], TransmitterKey] = {}
        self._channel_guests: dict[TransmitterKey, set[TransmitterKey]] = {}

        self._player = AudioPlayer(config.audio.output_device)
        self._sender = DISSender(config)
        self._listener = DISListener(config)
        self._local_manager = LocalTransmitterManager(config, self._sender)
        self._ptt = PTTController(config, self._sender, self._player)
        self._stale_timer = QTimer(self)

        self._ptt_key_primary = self._resolve_key(config.transmit.ptt_key_primary)
        self._ptt_key_secondary = self._resolve_key(config.transmit.ptt_key_secondary)

        self.setWindowTitle("DIS Radio Monitor")
        self.resize(900, 600)
        self._build_ui()
        self._connect_signals()
        self._stale_timer.start(1000)
        self._local_manager.load()  # create tiles for persisted local transmitters

    # ------------------------------------------------------------------ #
    # UI construction                                                      #
    # ------------------------------------------------------------------ #

    def _build_ui(self) -> None:
        toolbar = QToolBar("Main", self)
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        self._status_dot = QLabel("●")
        self._status_dot.setStyleSheet("color: #888888; font-size: 18px;")
        self._status_dot.setToolTip("Disconnected")
        toolbar.addWidget(self._status_dot)

        toolbar.addWidget(QLabel("  Multicast "))
        self._multicast_edit = QLineEdit(self._config.network.multicast_group)
        self._multicast_edit.setFixedWidth(130)
        toolbar.addWidget(self._multicast_edit)

        toolbar.addWidget(QLabel(" Port "))
        self._port_edit = QLineEdit(str(self._config.network.port))
        self._port_edit.setFixedWidth(60)
        toolbar.addWidget(self._port_edit)

        toolbar.addWidget(QLabel(" Exercise ID "))
        self._exercise_edit = QLineEdit()
        self._exercise_edit.setPlaceholderText("all")
        self._exercise_edit.setFixedWidth(50)
        if self._config.network.exercise_id is not None:
            self._exercise_edit.setText(str(self._config.network.exercise_id))
        toolbar.addWidget(self._exercise_edit)

        self._connect_btn = QPushButton("Connect")
        self._connect_btn.setCheckable(True)
        self._connect_btn.toggled.connect(self._on_connect_toggled)
        toolbar.addWidget(self._connect_btn)

        settings_btn = QPushButton("Settings")
        settings_btn.clicked.connect(self._open_settings)
        toolbar.addWidget(settings_btn)

        add_local_btn = QPushButton("+")
        add_local_btn.setToolTip("Add local transmitter")
        add_local_btn.setFixedWidth(28)
        add_local_btn.clicked.connect(self._on_add_local)
        toolbar.addWidget(add_local_btn)

        self._ptt_label = QLabel(" PTT ")
        self._ptt_label.setStyleSheet(
            "color: #888888; font-size: 12px; padding: 2px 6px; border-radius: 4px;"
        )
        toolbar.addWidget(self._ptt_label)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        self._flow_layout = QFlowLayout(container, h_spacing=8, v_spacing=8)
        container.setLayout(self._flow_layout)
        scroll.setWidget(container)
        self.setCentralWidget(scroll)

        self.setStatusBar(QStatusBar())

    # ------------------------------------------------------------------ #
    # Signal wiring                                                        #
    # ------------------------------------------------------------------ #

    def _connect_signals(self) -> None:
        self._listener.transmitter_updated.connect(self._on_transmitter_updated)
        self._listener.signal_received.connect(self._on_signal_received)
        self._local_manager.transmitter_updated.connect(self._on_transmitter_updated)
        self._local_manager.transmitter_removed.connect(self._on_local_removed)
        self._stale_timer.timeout.connect(self._check_stale)
        self._ptt.ptt_active.connect(self._on_ptt_active)
        self._ptt.ptt_error.connect(self._on_ptt_error)

    # ------------------------------------------------------------------ #
    # Slots                                                                #
    # ------------------------------------------------------------------ #

    def _on_connect_toggled(self, checked: bool) -> None:
        self._sync_config_from_toolbar()
        exercise_id = self._config.network.exercise_id or 1
        if checked:
            self._connect_btn.setText("Disconnect")
            self._listener.reconfigure(self._config)
            self._listener.start()
            self._local_manager.start(exercise_id)
            self._ptt.start_heartbeat()
            self._status_dot.setStyleSheet("color: #2ECC71; font-size: 18px;")
            self._status_dot.setToolTip("Connected")
        else:
            self._connect_btn.setText("Connect")
            self._listener.stop()
            self._listener.wait(2000)
            self._local_manager.stop()
            self._ptt.stop_heartbeat()
            self._status_dot.setStyleSheet("color: #888888; font-size: 18px;")
            self._status_dot.setToolTip("Disconnected")

    def _on_transmitter_updated(self, record: TransmitterRecord) -> None:
        if not record.is_local:
            # Ignore PDUs echoed back from our own entity — managed via LocalTransmitterManager
            site, app, entity = record.entity_id
            if (site == self._config.transmit.site_id
                    and app == self._config.transmit.app_id
                    and entity == self._config.transmit.entity_id):
                return

        key = record.key
        self._records[key] = record

        if record.is_local:
            # Clean up stale channel index entry if freq/mod changed
            old_channel = next(
                (ch for ch, k in self._channel_index.items() if k == key), None
            )
            new_channel = (record.frequency_hz, channel_modulation_key(record.modulation_major))
            if old_channel and old_channel != new_channel:
                del self._channel_index[old_channel]
            self._channel_index[new_channel] = key

            if key not in self._tiles:
                tile = TransmitterTile(record, is_local=True)
                self._wire_tile(tile, key, is_local=True)
                self._tiles[key] = tile
                self._flow_layout.addWidget(tile)
                self._channel_guests.setdefault(key, set())
                # Absorb any existing observed tiles on this channel as guests
                obs_keys = [
                    k for k, r in self._records.items()
                    if not r.is_local
                    and (r.frequency_hz, r.modulation_major.upper()) == new_channel
                    and k in self._tiles
                ]
                for obs_key in obs_keys:
                    self._channel_guests[key].add(obs_key)
                    obs_tile = self._tiles.pop(obs_key)
                    self._flow_layout.removeWidget(obs_tile)
                    obs_tile.hide()
                    obs_tile.deleteLater()
                if self._channel_guests[key]:
                    guest_records = [
                        self._records[gk] for gk in self._channel_guests[key]
                        if gk in self._records
                    ]
                    tile.set_guests(guest_records)
            else:
                self._tiles[key].update_record(record)
        else:
            channel_key_tuple = (record.frequency_hz, channel_modulation_key(record.modulation_major))
            canonical_key = self._channel_index.get(channel_key_tuple)
            if canonical_key is not None:
                # Route to canonical local tile as guest
                guests = self._channel_guests.setdefault(canonical_key, set())
                guests.add(key)
                guest_records = [
                    self._records[gk] for gk in guests if gk in self._records
                ]
                tile = self._tiles.get(canonical_key)
                if tile:
                    tile.set_guests(guest_records)
            else:
                # Observed radio with no local match — existing behaviour
                if key not in self._tiles:
                    tile = TransmitterTile(record, is_local=False)
                    self._wire_tile(tile, key, is_local=False)
                    self._tiles[key] = tile
                    self._flow_layout.addWidget(tile)
                else:
                    self._tiles[key].update_record(record)

    def _on_local_removed(self, key: object) -> None:
        key = key  # type: TransmitterKey
        # Remove channel index entry
        old_channel = next(
            (ch for ch, k in self._channel_index.items() if k == key), None
        )
        if old_channel:
            del self._channel_index[old_channel]

        # Re-promote first guest to its own observed tile; drop the rest
        guests = self._channel_guests.pop(key, set())
        promoted = False
        for gk in guests:
            if gk not in self._records:
                continue
            if not promoted:
                guest_record = self._records[gk]
                tile = TransmitterTile(guest_record, is_local=False)
                self._wire_tile(tile, gk, is_local=False)
                self._tiles[gk] = tile
                self._flow_layout.addWidget(tile)
                promoted = True
            else:
                self._records.pop(gk, None)  # drop; will re-appear on next PDU

        # Remove the local tile
        tile = self._tiles.pop(key, None)
        self._records.pop(key, None)
        if tile:
            if tile is self._primary_tx_tile:
                self._primary_tx_tile = None
                self._ptt.deselect("primary")
            if tile is self._secondary_tx_tile:
                self._secondary_tx_tile = None
                self._ptt.deselect("secondary")
            self._flow_layout.removeWidget(tile)
            tile.hide()
            tile.deleteLater()

    def _on_signal_received(
        self, key: object, audio: bytes, encoding: int, sample_rate: int
    ) -> None:
        tile = self._tiles.get(key)  # type: ignore[arg-type]
        play_key = key
        if tile is None:
            # Key may be a guest of a local tile — find its canonical key so
            # audio is routed through the local tile's stream (which is
            # indexed by the canonical key in AudioPlayer).
            for canonical_key, guests in self._channel_guests.items():
                if key in guests:  # type: ignore[operator]
                    tile = self._tiles.get(canonical_key)
                    play_key = canonical_key
                    break
        if tile is not None and tile.audio_enabled:
            self._player.feed(play_key, audio, encoding, sample_rate)  # type: ignore[arg-type]

    def _toggle_audio(self, key: TransmitterKey, enabled: bool) -> None:
        if enabled:
            self._player.enable(key)
        else:
            self._player.disable(key)

    def _check_stale(self) -> None:
        timeout = self._config.display.stale_timeout_seconds
        now = datetime.now()
        to_remove: list[TransmitterKey] = []
        local_keys = set(self._channel_index.values())

        for key, tile in self._tiles.items():
            if key in local_keys:
                # Local tiles never expire; always show as fresh
                tile.set_stale(False)
                # Prune stale guests
                guests = self._channel_guests.get(key, set())
                stale_guests = {
                    gk for gk in guests
                    if gk not in self._records
                    or (now - self._records[gk].last_seen).total_seconds() > 2 * timeout
                }
                for gk in stale_guests:
                    guests.discard(gk)
                    self._records.pop(gk, None)
                guest_records = [self._records[gk] for gk in guests if gk in self._records]
                tile.set_guests(guest_records)
            else:
                age = (now - tile.last_seen).total_seconds()
                if age > 2 * timeout:
                    to_remove.append(key)
                else:
                    tile.set_stale(age > timeout)
                    tile.refresh_age()

        for key in to_remove:
            self._player.disable(key)
            tile = self._tiles.pop(key)
            self._records.pop(key, None)
            if tile is self._primary_tx_tile:
                self._primary_tx_tile = None
                self._ptt.deselect("primary")
            if tile is self._secondary_tx_tile:
                self._secondary_tx_tile = None
                self._ptt.deselect("secondary")
            self._flow_layout.removeWidget(tile)
            tile.hide()
            tile.deleteLater()

    def _open_settings(self) -> None:
        dialog = SettingsDialog(self._config, parent=self)
        dialog.config_changed.connect(self._on_settings_changed)
        dialog.exec()

    def _on_settings_changed(self, config: AppConfig) -> None:
        self._config = config
        save_config(config)
        self._sender.reconfigure(config)
        self._local_manager.reconfigure(config)
        self._ptt_key_primary = self._resolve_key(config.transmit.ptt_key_primary)
        self._ptt_key_secondary = self._resolve_key(config.transmit.ptt_key_secondary)
        if self._connect_btn.isChecked():
            self._listener.stop()
            self._listener.wait(2000)
            self._listener.reconfigure(config)
            self._listener.start()
        self._player.close_all()
        self._player = AudioPlayer(config.audio.output_device)
        self._ptt.reconfigure(config, player=self._player)
        for key, tile in self._tiles.items():
            if tile.audio_enabled:
                self._player.enable(key)

    def _on_add_local(self) -> None:
        dialog = LocalTransmitterDialog(parent=self)
        dialog.local_transmitter_saved.connect(self._local_manager.add)
        dialog.exec()

    def _on_clone_tile(self, key: TransmitterKey) -> None:
        record = self._records.get(key)
        if record is None:
            return
        dialog = LocalTransmitterDialog(parent=self, prefill=record)
        dialog.local_transmitter_saved.connect(self._local_manager.add)
        dialog.exec()

    def _on_edit_local(self, key: TransmitterKey) -> None:
        lt_list = self._config.local_transmitters.transmitters
        radio_id = key[3]
        lt = next((t for t in lt_list if t.radio_id == radio_id), None)
        if lt is None:
            return
        dialog = LocalTransmitterDialog(parent=self, edit_target=lt)
        dialog.local_transmitter_saved.connect(self._local_manager.update)
        dialog.exec()

    def _on_delete_local(self, key: TransmitterKey) -> None:
        self._local_manager.remove(key[3])

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        if event.isAutoRepeat():
            return
        role = None
        if self._ptt_key_primary:
            modifiers, key = self._ptt_key_primary
            if event.key() == key and (event.modifiers() & MainWindow._RELEVANT_MODIFIERS) == modifiers:
                role = "primary"
        if role is None and self._ptt_key_secondary:
            modifiers, key = self._ptt_key_secondary
            if event.key() == key and (event.modifiers() & MainWindow._RELEVANT_MODIFIERS) == modifiers:
                role = "secondary"

        if role is not None:
            self._ptt.ptt_press(role)
            # Suppress local manager PDU while we are transmitting on a local tile
            active_tile = self._primary_tx_tile if role == "primary" else self._secondary_tx_tile
            if active_tile is not None:
                active_key = next(
                    (k for k, t in self._tiles.items() if t is active_tile), None
                )
                if active_key and active_key in self._channel_index.values():
                    self._local_manager.suppress(active_key)
        else:
            super().keyPressEvent(event)

    def keyReleaseEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        if event.isAutoRepeat():
            return
        role = None
        if self._ptt_key_primary:
            modifiers, key = self._ptt_key_primary
            if event.key() == key and (event.modifiers() & MainWindow._RELEVANT_MODIFIERS) == modifiers:
                role = "primary"
        if role is None and self._ptt_key_secondary:
            modifiers, key = self._ptt_key_secondary
            if event.key() == key and (event.modifiers() & MainWindow._RELEVANT_MODIFIERS) == modifiers:
                role = "secondary"

        if role is not None:
            self._ptt.ptt_release(role)
            # Resume local manager PDU after PTT release
            active_tile = self._primary_tx_tile if role == "primary" else self._secondary_tx_tile
            if active_tile is not None:
                active_key = next(
                    (k for k, t in self._tiles.items() if t is active_tile), None
                )
                if active_key and active_key in self._channel_index.values():
                    self._local_manager.unsuppress(active_key)
        else:
            super().keyReleaseEvent(event)

    def _on_ptt_active(self, role: str) -> None:
        if role:
            self._ptt_label.setStyleSheet(
                "color: white; background: #E74C3C; font-size: 12px; "
                "padding: 2px 6px; border-radius: 4px;"
            )
            tile = self._primary_tx_tile if role == "primary" else self._secondary_tx_tile
            if tile is not None:
                tile.set_local_tx(True)
            self._active_ptt_tile = tile
        else:
            self._ptt_label.setStyleSheet(
                "color: #888888; font-size: 12px; padding: 2px 6px; border-radius: 4px;"
            )
            if self._active_ptt_tile is not None:
                self._active_ptt_tile.set_local_tx(False)
                self._active_ptt_tile = None

    def _on_ptt_error(self, message: str) -> None:
        self.statusBar().showMessage(message, 5000)

    def _on_tx_primary_toggled(
        self, key: TransmitterKey, tile: TransmitterTile, enabled: bool
    ) -> None:
        if enabled:
            if self._primary_tx_tile is not None and self._primary_tx_tile is not tile:
                self._primary_tx_tile.set_tx_primary(False)
                self._ptt.deselect("primary")
            self._primary_tx_tile = tile
            record = self._records.get(key)
            if record:
                self._ptt.select(key, record, "primary")
        else:
            self._primary_tx_tile = None
            self._ptt.deselect("primary")
        self._refresh_delete_enabled()

    def _on_tx_secondary_toggled(
        self, key: TransmitterKey, tile: TransmitterTile, enabled: bool
    ) -> None:
        if enabled:
            if self._secondary_tx_tile is not None and self._secondary_tx_tile is not tile:
                self._secondary_tx_tile.set_tx_secondary(False)
                self._ptt.deselect("secondary")
            self._secondary_tx_tile = tile
            record = self._records.get(key)
            if record:
                self._ptt.select(key, record, "secondary")
        else:
            self._secondary_tx_tile = None
            self._ptt.deselect("secondary")
        self._refresh_delete_enabled()

    # ------------------------------------------------------------------ #
    # Helpers                                                              #
    # ------------------------------------------------------------------ #

    def _wire_tile(self, tile: TransmitterTile, key: TransmitterKey, *, is_local: bool) -> None:
        tile.play_toggled.connect(
            lambda enabled, k=key: self._toggle_audio(k, enabled)
        )
        tile.tx_primary_toggled.connect(
            lambda enabled, k=key, t=tile: self._on_tx_primary_toggled(k, t, enabled)
        )
        tile.tx_secondary_toggled.connect(
            lambda enabled, k=key, t=tile: self._on_tx_secondary_toggled(k, t, enabled)
        )
        if is_local:
            tile.edit_clicked.connect(lambda k=key: self._on_edit_local(k))
            tile.delete_clicked.connect(lambda k=key: self._on_delete_local(k))
        else:
            tile.clone_clicked.connect(lambda k=key: self._on_clone_tile(k))

    def _refresh_delete_enabled(self) -> None:
        selected_as_tx = {
            t for t in (self._primary_tx_tile, self._secondary_tx_tile) if t is not None
        }
        local_keys = set(self._channel_index.values())
        for key in local_keys:
            tile = self._tiles.get(key)
            if tile:
                tile.set_delete_enabled(tile not in selected_as_tx)

    def _sync_config_from_toolbar(self) -> None:
        self._config.network.multicast_group = self._multicast_edit.text().strip()
        try:
            self._config.network.port = int(self._port_edit.text())
        except ValueError:
            pass
        exercise_text = self._exercise_edit.text().strip()
        self._config.network.exercise_id = (
            int(exercise_text) if exercise_text.isdigit() and int(exercise_text) > 0 else None
        )
        save_config(self._config)

    @staticmethod
    def _resolve_key(key_name: str) -> Optional[tuple[Qt.KeyboardModifier, Qt.Key]]:
        if not key_name:
            return None
        parts = key_name.split("+")
        key_part = parts[-1]
        if not key_part:
            log.warning("PTT key name has empty key part in %r — ignoring", key_name)
            return None
        modifier_parts = parts[:-1]
        combined = Qt.KeyboardModifier.NoModifier
        for mod in modifier_parts:
            normalized = MainWindow._MODIFIER_NAME_MAP.get(mod)
            if normalized is None:
                log.warning("Unknown PTT modifier name: %r — ignoring", mod)
                return None
            combined |= Qt.KeyboardModifier[f"{normalized}Modifier"]
        try:
            key = Qt.Key[f"Key_{key_part}"]
        except KeyError:
            log.warning("Unknown PTT key name: %r — ignoring", key_part)
            return None
        return combined, key

    def closeEvent(self, event) -> None:  # noqa: ANN001, N802
        self._listener.stop()
        self._listener.wait(2000)
        self._local_manager.stop()
        self._ptt.close()
        self._player.close_all()
        self._sender.close()
        super().closeEvent(event)
