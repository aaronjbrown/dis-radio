from __future__ import annotations
from datetime import datetime
from typing import Optional

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QFrame, QGraphicsOpacityEffect, QHBoxLayout,
    QLabel, QPushButton, QVBoxLayout, QWidget,
)

from dis_radio.models import TransmitterRecord, TransmitterState

_STATE_COLORS = {
    TransmitterState.OFF: "#888888",
    TransmitterState.IDLE: "#E6A817",
    TransmitterState.TRANSMITTING: "#2ECC71",
}

_STATE_LABELS = {
    TransmitterState.OFF: "OFF",
    TransmitterState.IDLE: "IDLE",
    TransmitterState.TRANSMITTING: "RX",
}


def _format_frequency(hz: float) -> str:
    if hz < 1_000_000:
        return f"{hz / 1_000:.3f} kHz"
    if hz < 1_000_000_000:
        return f"{hz / 1_000_000:.3f} MHz"
    return f"{hz / 1_000_000_000:.3f} GHz"


def _format_age(last_seen: datetime) -> str:
    secs = (datetime.now() - last_seen).total_seconds()
    if secs < 60:
        return f"{secs:.1f}s ago"
    return f"{int(secs // 60)}m {int(secs % 60)}s ago"


class TransmitterTile(QFrame):
    play_toggled = pyqtSignal(bool)
    tx_primary_toggled = pyqtSignal(bool)
    tx_secondary_toggled = pyqtSignal(bool)
    clone_clicked = pyqtSignal()    # observed tiles only
    edit_clicked = pyqtSignal()     # local tiles only
    delete_clicked = pyqtSignal()   # local tiles only

    def __init__(
        self,
        record: TransmitterRecord,
        is_local: bool = False,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._last_seen: datetime = record.last_seen
        self._audio_enabled: bool = False
        self._is_local: bool = is_local
        self._transmitting_guest: Optional[TransmitterRecord] = None
        self._local_tx_active: bool = False
        self._last_record: Optional[TransmitterRecord] = None
        self._delete_btn: Optional[QPushButton] = None
        self._edit_btn: Optional[QPushButton] = None
        self._clone_btn: Optional[QPushButton] = None
        self._opacity = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self._opacity)
        self._build_ui()
        self.update_record(record)

    # ------------------------------------------------------------------ #
    # Public API                                                           #
    # ------------------------------------------------------------------ #

    @property
    def last_seen(self) -> datetime:
        return self._last_seen

    @property
    def audio_enabled(self) -> bool:
        return self._audio_enabled

    def update_record(self, record: TransmitterRecord) -> None:
        self._last_seen = record.last_seen
        self._last_record = record
        site, app, entity = record.entity_id
        if self._is_local and record.name:
            title = record.name
        else:
            title = f"{site}:{app}:{entity}  •  Radio {record.radio_id}"
        self._title_label.setText(title)
        self._freq_label.setText(_format_frequency(record.frequency_hz))
        self._power_label.setText(f"{record.power_dbm:.1f} dBm")
        self._mod_label.setText(record.modulation_major)
        color = _STATE_COLORS.get(record.state, "#888888")
        label = _STATE_LABELS.get(record.state, "?")
        self._state_label.setText(label)
        self._state_label.setStyleSheet(
            f"color: white; background: {color}; border-radius: 4px; padding: 2px 6px;"
        )
        if self._is_local:
            self._seen_label.setText("LOCAL")
        else:
            self._seen_label.setText(_format_age(record.last_seen))
        self._apply_guest_override()
        if self._local_tx_active:
            self._apply_local_tx_label()

    def set_stale(self, stale: bool) -> None:
        self._opacity.setOpacity(0.5 if stale else 1.0)

    def refresh_age(self) -> None:
        if not self._is_local:
            self._seen_label.setText(_format_age(self._last_seen))

    def set_tx_primary(self, selected: bool) -> None:
        self._tx_primary_btn.blockSignals(True)
        self._tx_primary_btn.setChecked(selected)
        color = "#E74C3C" if selected else ""
        self._tx_primary_btn.setStyleSheet(
            f"background: {color}; color: {'white' if selected else ''};"
        )
        self._tx_primary_btn.blockSignals(False)

    def set_tx_secondary(self, selected: bool) -> None:
        self._tx_secondary_btn.blockSignals(True)
        self._tx_secondary_btn.setChecked(selected)
        color = "#E67E22" if selected else ""
        self._tx_secondary_btn.setStyleSheet(
            f"background: {color}; color: {'white' if selected else ''};"
        )
        self._tx_secondary_btn.blockSignals(False)

    def set_guests(self, guests: list[TransmitterRecord]) -> None:
        if not guests:
            self._transmitting_guest = None
            self._guest_label.hide()
            self._guest_label.setToolTip("")
            return
        self._guest_label.setText(f"+{len(guests)}")
        lines = []
        for g in guests:
            s, a, e = g.entity_id
            state_str = _STATE_LABELS.get(g.state, "?")
            lines.append(f"{s}:{a}:{e}  •  Radio {g.radio_id}  •  {state_str}")
        self._guest_label.setToolTip("\n".join(lines))
        self._guest_label.show()
        # If any guest is transmitting, store it so update_record can re-apply the override
        transmitting = [g for g in guests if g.state == TransmitterState.TRANSMITTING]
        self._transmitting_guest = transmitting[0] if transmitting else None
        self._apply_guest_override()

    def set_delete_enabled(self, enabled: bool) -> None:
        if self._delete_btn is not None:
            self._delete_btn.setEnabled(enabled)

    # ------------------------------------------------------------------ #
    # Internal                                                             #
    # ------------------------------------------------------------------ #

    def set_local_tx(self, active: bool) -> None:
        self._local_tx_active = active
        if active:
            self._apply_local_tx_label()
        elif self._last_record is not None:
            color = _STATE_COLORS.get(self._last_record.state, "#888888")
            label = _STATE_LABELS.get(self._last_record.state, "?")
            self._state_label.setText(label)
            self._state_label.setStyleSheet(
                f"color: white; background: {color}; border-radius: 4px; padding: 2px 6px;"
            )
            self._apply_guest_override()

    def _apply_local_tx_label(self) -> None:
        self._state_label.setText("TX")
        self._state_label.setStyleSheet(
            "color: white; background: #E74C3C; border-radius: 4px; padding: 2px 6px;"
        )

    def _apply_guest_override(self) -> None:
        """If a guest is currently transmitting, override title and state labels."""
        if self._transmitting_guest is None or self._local_tx_active:
            return
        g = self._transmitting_guest
        s, a, e = g.entity_id
        self._title_label.setText(f"{s}:{a}:{e}  •  Radio {g.radio_id} [remote]")
        self._state_label.setText("RX")
        self._state_label.setStyleSheet(
            f"color: white; background: {_STATE_COLORS[TransmitterState.TRANSMITTING]}; "
            "border-radius: 4px; padding: 2px 6px;"
        )

    def _build_ui(self) -> None:
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setMinimumWidth(220)
        self.setMaximumWidth(300)

        if self._is_local:
            self.setStyleSheet("TransmitterTile { border-left: 3px solid #1A73E8; }")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 8)
        outer.setSpacing(4)

        # Header row
        header = QHBoxLayout()
        self._title_label = QLabel()
        self._title_label.setStyleSheet("font-weight: bold;")

        if self._is_local:
            self._local_badge = QLabel("LOCAL")
            self._local_badge.setStyleSheet(
                "color: #1A73E8; font-size: 9px; font-weight: bold; padding: 0 3px;"
            )
            header.addWidget(self._local_badge)

        self._tx_primary_btn = QPushButton("P")
        self._tx_primary_btn.setCheckable(True)
        self._tx_primary_btn.setFixedSize(28, 28)
        self._tx_primary_btn.setToolTip("Set as primary TX radio")
        self._tx_primary_btn.toggled.connect(self._on_tx_primary_toggled)

        self._tx_secondary_btn = QPushButton("S")
        self._tx_secondary_btn.setCheckable(True)
        self._tx_secondary_btn.setFixedSize(28, 28)
        self._tx_secondary_btn.setToolTip("Set as secondary TX radio")
        self._tx_secondary_btn.toggled.connect(self._on_tx_secondary_toggled)

        self._play_btn = QPushButton("🔊")
        self._play_btn.setCheckable(True)
        self._play_btn.setFixedSize(28, 28)
        self._play_btn.setToolTip("Toggle audio playback")
        self._play_btn.toggled.connect(self._on_play_toggled)

        header.addWidget(self._title_label, stretch=1)
        header.addWidget(self._tx_primary_btn)
        header.addWidget(self._tx_secondary_btn)
        header.addWidget(self._play_btn)

        if self._is_local:
            self._edit_btn = QPushButton("✏")
            self._edit_btn.setFixedSize(28, 28)
            self._edit_btn.setToolTip("Edit local transmitter")
            self._edit_btn.clicked.connect(self.edit_clicked)
            header.addWidget(self._edit_btn)

            self._delete_btn = QPushButton("🗑")
            self._delete_btn.setFixedSize(28, 28)
            self._delete_btn.setToolTip("Delete local transmitter")
            self._delete_btn.clicked.connect(self.delete_clicked)
            header.addWidget(self._delete_btn)
        else:
            self._clone_btn = QPushButton("📌")
            self._clone_btn.setFixedSize(28, 28)
            self._clone_btn.setToolTip("Pin as local transmitter")
            self._clone_btn.clicked.connect(self.clone_clicked)
            header.addWidget(self._clone_btn)

        outer.addLayout(header)

        # Divider
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        outer.addWidget(line)

        # Fields grid
        self._freq_label = self._add_row(outer, "Freq")
        self._power_label = self._add_row(outer, "Power")
        self._mod_label = self._add_row(outer, "Mod")

        state_row = QHBoxLayout()
        state_row.addWidget(QLabel("State"))
        self._state_label = QLabel()
        state_row.addWidget(self._state_label, alignment=Qt.AlignmentFlag.AlignRight)
        outer.addLayout(state_row)

        self._seen_label = self._add_row(outer, "Seen")

        # Guest count badge (bottom right, hidden by default)
        guest_row = QHBoxLayout()
        guest_row.addStretch()
        self._guest_label = QLabel()
        self._guest_label.setStyleSheet(
            "color: white; background: #555; border-radius: 8px; "
            "padding: 1px 6px; font-size: 10px;"
        )
        self._guest_label.hide()
        guest_row.addWidget(self._guest_label)
        outer.addLayout(guest_row)

    def _add_row(self, layout: QVBoxLayout, label: str) -> QLabel:
        row = QHBoxLayout()
        row.addWidget(QLabel(label))
        value = QLabel()
        row.addWidget(value, alignment=Qt.AlignmentFlag.AlignRight)
        layout.addLayout(row)
        return value

    def _on_play_toggled(self, checked: bool) -> None:
        self._audio_enabled = checked
        color = "#1A73E8" if checked else ""
        self._play_btn.setStyleSheet(
            f"background: {color}; color: {'white' if checked else ''};"
        )
        self.play_toggled.emit(checked)

    def _on_tx_primary_toggled(self, checked: bool) -> None:
        color = "#E74C3C" if checked else ""
        self._tx_primary_btn.setStyleSheet(
            f"background: {color}; color: {'white' if checked else ''};"
        )
        self.tx_primary_toggled.emit(checked)

    def _on_tx_secondary_toggled(self, checked: bool) -> None:
        color = "#E67E22" if checked else ""
        self._tx_secondary_btn.setStyleSheet(
            f"background: {color}; color: {'white' if checked else ''};"
        )
        self.tx_secondary_toggled.emit(checked)
