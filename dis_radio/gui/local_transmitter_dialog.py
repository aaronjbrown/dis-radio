from __future__ import annotations
from typing import Optional

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox,
    QFormLayout, QHBoxLayout, QLineEdit, QVBoxLayout, QWidget,
)

from dis_radio.dis.modulation import PRESETS
from dis_radio.models import LocalTransmitter, TransmitterRecord

_UNITS = [("Hz", 1.0), ("kHz", 1_000.0), ("MHz", 1_000_000.0), ("GHz", 1_000_000_000.0)]
_UNIT_FACTORS: dict[str, float] = dict(_UNITS)


def _best_unit(hz: float) -> tuple[str, float]:
    if hz >= 1_000_000_000:
        return "GHz", 1_000_000_000.0
    if hz >= 1_000_000:
        return "MHz", 1_000_000.0
    if hz >= 1_000:
        return "kHz", 1_000.0
    return "Hz", 1.0


class LocalTransmitterDialog(QDialog):
    local_transmitter_saved = pyqtSignal(LocalTransmitter)

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        *,
        prefill: Optional[TransmitterRecord] = None,
        edit_target: Optional[LocalTransmitter] = None,
    ) -> None:
        super().__init__(parent)
        self._edit_target = edit_target
        self.setWindowTitle("Local Transmitter" if edit_target is None else "Edit Local Transmitter")
        self.setMinimumWidth(320)
        self._build_ui()
        if edit_target is not None:
            self._populate_from_local(edit_target)
        elif prefill is not None:
            self._populate_from_record(prefill)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self._name_edit = QLineEdit()
        self._name_edit.setPlaceholderText("e.g. Command Net")
        self._name_edit.textChanged.connect(self._update_ok_button)
        form.addRow("Name", self._name_edit)

        freq_row = QHBoxLayout()
        self._freq_spin = QDoubleSpinBox()
        self._freq_spin.setDecimals(3)
        self._freq_spin.setRange(0.0, 999_999.999)
        self._freq_unit = QComboBox()
        for label, _ in _UNITS:
            self._freq_unit.addItem(label)
        self._freq_unit.setCurrentText("MHz")
        freq_row.addWidget(self._freq_spin, stretch=1)
        freq_row.addWidget(self._freq_unit)
        form.addRow("Frequency", freq_row)

        self._mod_combo = QComboBox()
        for preset in PRESETS:
            self._mod_combo.addItem(preset)
        self._mod_combo.currentTextChanged.connect(self._on_preset_changed)
        form.addRow("Modulation", self._mod_combo)

        self._bw_spin = QDoubleSpinBox()
        self._bw_spin.setDecimals(1)
        self._bw_spin.setRange(0.0, 999_999.9)
        self._bw_spin.setSuffix(" kHz")
        form.addRow("Bandwidth", self._bw_spin)

        self._power_spin = QDoubleSpinBox()
        self._power_spin.setDecimals(1)
        self._power_spin.setRange(-200.0, 200.0)
        self._power_spin.setSuffix(" dBm")
        self._power_spin.setValue(10.0)
        form.addRow("Power", self._power_spin)

        layout.addLayout(form)

        self._buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self._buttons.accepted.connect(self._on_accept)
        self._buttons.rejected.connect(self.reject)
        layout.addWidget(self._buttons)

        self._update_ok_button()
        self._on_preset_changed(self._mod_combo.currentText())

    def _on_preset_changed(self, preset_name: str) -> None:
        _, _, _, _, default_bw_hz = PRESETS.get(preset_name, PRESETS["No Statement"])
        self._bw_spin.setValue(default_bw_hz / 1_000.0)

    def _update_ok_button(self) -> None:
        self._buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(
            bool(self._name_edit.text().strip())
        )

    def _populate_from_record(self, record: TransmitterRecord) -> None:
        unit_label, divisor = _best_unit(record.frequency_hz)
        self._freq_spin.setValue(record.frequency_hz / divisor)
        self._freq_unit.setCurrentText(unit_label)
        idx = self._mod_combo.findText(record.modulation_major)
        if idx >= 0:
            self._mod_combo.setCurrentIndex(idx)
        self._bw_spin.setValue(record.bandwidth_hz / 1_000.0)
        self._power_spin.setValue(record.power_dbm)

    def _populate_from_local(self, lt: LocalTransmitter) -> None:
        self._name_edit.setText(lt.name)
        unit_label, divisor = _best_unit(lt.frequency_hz)
        self._freq_spin.setValue(lt.frequency_hz / divisor)
        self._freq_unit.setCurrentText(unit_label)
        idx = self._mod_combo.findText(lt.modulation_major)
        if idx >= 0:
            self._mod_combo.setCurrentIndex(idx)
        self._bw_spin.setValue(lt.bandwidth_hz / 1_000.0)
        self._power_spin.setValue(lt.power_dbm)

    def _on_accept(self) -> None:
        unit_label = self._freq_unit.currentText()
        divisor = _UNIT_FACTORS[unit_label]
        freq_hz = self._freq_spin.value() * divisor
        radio_id = self._edit_target.radio_id if self._edit_target is not None else 0
        lt = LocalTransmitter(
            name=self._name_edit.text().strip(),
            frequency_hz=freq_hz,
            modulation_major=self._mod_combo.currentText(),
            bandwidth_hz=self._bw_spin.value() * 1_000.0,
            power_dbm=self._power_spin.value(),
            radio_id=radio_id,
        )
        self.local_transmitter_saved.emit(lt)
        self.accept()
