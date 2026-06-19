from __future__ import annotations
from typing import Optional

import sounddevice as sd
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox, QCompleter, QDialog, QDialogButtonBox, QFormLayout,
    QGroupBox, QLineEdit, QSpinBox, QTabWidget, QVBoxLayout, QWidget,
)

from dis_radio.config import AppConfig
from dis_radio.dis.enums import COUNTRY_CODES, COUNTRY_NAMES, DOMAIN_NAMES

_SORTED_COUNTRY_NAMES = sorted(COUNTRY_NAMES.values())


class SettingsDialog(QDialog):
    config_changed = pyqtSignal(AppConfig)

    def __init__(self, config: AppConfig, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._config = config
        self.setWindowTitle("Settings")
        self.setMinimumWidth(380)
        self._build_ui()
        self._populate(config)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        tabs = QTabWidget()

        # ── General tab ────────────────────────────────────────────────
        general = QWidget()
        general_form = QFormLayout(general)

        self._multicast_edit = QLineEdit()
        general_form.addRow("Multicast group", self._multicast_edit)

        self._port_spin = QSpinBox()
        self._port_spin.setRange(1, 65535)
        general_form.addRow("Port", self._port_spin)

        self._iface_edit = QLineEdit()
        self._iface_edit.setPlaceholderText("(system default)")
        general_form.addRow("Network interface", self._iface_edit)

        self._exercise_spin = QSpinBox()
        self._exercise_spin.setRange(0, 255)
        self._exercise_spin.setSpecialValueText("All exercises")
        general_form.addRow("Exercise ID filter", self._exercise_spin)

        self._stale_spin = QSpinBox()
        self._stale_spin.setRange(5, 3600)
        self._stale_spin.setSuffix(" s")
        general_form.addRow("Stale timeout", self._stale_spin)

        self._device_combo = QComboBox()
        self._device_combo.addItem("System default", userData=None)
        try:
            for dev in sd.query_devices():
                if dev["max_output_channels"] > 0:
                    self._device_combo.addItem(dev["name"], userData=dev["name"])
        except Exception:
            pass
        general_form.addRow("Audio output device", self._device_combo)

        tabs.addTab(general, "General")

        # ── Transmit tab ───────────────────────────────────────────────
        transmit = QWidget()
        transmit_form = QFormLayout(transmit)

        self._site_spin = QSpinBox()
        self._site_spin.setRange(0, 65535)
        transmit_form.addRow("Site ID", self._site_spin)

        self._app_spin = QSpinBox()
        self._app_spin.setRange(0, 65535)
        transmit_form.addRow("App ID", self._app_spin)

        self._entity_spin = QSpinBox()
        self._entity_spin.setRange(0, 65535)
        transmit_form.addRow("Entity ID", self._entity_spin)

        self._primary_radio_spin = QSpinBox()
        self._primary_radio_spin.setRange(1, 65535)
        transmit_form.addRow("Primary radio ID", self._primary_radio_spin)

        self._secondary_radio_spin = QSpinBox()
        self._secondary_radio_spin.setRange(1, 65535)
        transmit_form.addRow("Secondary radio ID", self._secondary_radio_spin)

        self._ptt_primary_edit = QLineEdit()
        self._ptt_primary_edit.setPlaceholderText("e.g. Space, Shift+Space, Ctrl+F1")
        self._ptt_primary_edit.setToolTip(
            "Key name for primary PTT, optionally prefixed with modifiers.\n"
            "Modifiers: Shift, Ctrl, Alt, Meta.\n"
            "Examples: Space, Shift+Space, Ctrl+F1, Ctrl+Shift+F1"
        )
        transmit_form.addRow("PTT key (primary)", self._ptt_primary_edit)

        self._ptt_secondary_edit = QLineEdit()
        self._ptt_secondary_edit.setPlaceholderText("e.g. Shift+Space, Ctrl+Space")
        self._ptt_secondary_edit.setToolTip(
            "Key name for secondary PTT, optionally prefixed with modifiers.\n"
            "Modifiers: Shift, Ctrl, Alt, Meta.\n"
            "Examples: Shift+Space, Ctrl+Shift+F1 — leave empty to disable."
        )
        transmit_form.addRow("PTT key (secondary)", self._ptt_secondary_edit)

        self._input_combo = QComboBox()
        self._input_combo.addItem("System default", userData=None)
        try:
            for dev in sd.query_devices():
                if dev["max_input_channels"] > 0:
                    self._input_combo.addItem(dev["name"], userData=dev["name"])
        except Exception:
            pass
        transmit_form.addRow("Microphone (input)", self._input_combo)

        self._starting_radio_id_spin = QSpinBox()
        self._starting_radio_id_spin.setRange(1, 65535)
        self._starting_radio_id_spin.setToolTip(
            "Radio ID assigned to the first local transmitter created. "
            "Existing transmitters are unaffected by changes here."
        )
        transmit_form.addRow("Starting radio ID", self._starting_radio_id_spin)

        # ── Radio Entity Type group box ───────────────────────────────
        entity_group = QGroupBox("Radio Entity Type")
        entity_form = QFormLayout(entity_group)

        self._domain_combo = QComboBox()
        for i in sorted(DOMAIN_NAMES):
            self._domain_combo.addItem(DOMAIN_NAMES[i])
        entity_form.addRow("Domain", self._domain_combo)

        self._country_combo = QComboBox()
        self._country_combo.setEditable(True)
        for name in _SORTED_COUNTRY_NAMES:
            self._country_combo.addItem(name, userData=COUNTRY_CODES[name])
        completer = QCompleter(_SORTED_COUNTRY_NAMES, self._country_combo)
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        completer.setFilterMode(Qt.MatchFlag.MatchContains)
        self._country_combo.setCompleter(completer)
        entity_form.addRow("Country", self._country_combo)

        self._et_category_spin = QSpinBox()
        self._et_category_spin.setRange(0, 255)
        entity_form.addRow("Category", self._et_category_spin)

        self._et_subcategory_spin = QSpinBox()
        self._et_subcategory_spin.setRange(0, 255)
        entity_form.addRow("Subcategory", self._et_subcategory_spin)

        self._et_specific_spin = QSpinBox()
        self._et_specific_spin.setRange(0, 255)
        entity_form.addRow("Specific", self._et_specific_spin)

        self._et_extra_spin = QSpinBox()
        self._et_extra_spin.setRange(0, 255)
        entity_form.addRow("Extra", self._et_extra_spin)

        transmit_form.addRow(entity_group)

        tabs.addTab(transmit, "Transmit")

        layout.addWidget(tabs)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _populate(self, config: AppConfig) -> None:
        # General
        self._multicast_edit.setText(config.network.multicast_group)
        self._port_spin.setValue(config.network.port)
        self._iface_edit.setText(config.network.interface or "")
        self._exercise_spin.setValue(config.network.exercise_id or 0)
        self._stale_spin.setValue(config.display.stale_timeout_seconds)
        if config.audio.output_device:
            idx = self._device_combo.findData(config.audio.output_device)
            if idx >= 0:
                self._device_combo.setCurrentIndex(idx)

        # Transmit
        self._site_spin.setValue(config.transmit.site_id)
        self._app_spin.setValue(config.transmit.app_id)
        self._entity_spin.setValue(config.transmit.entity_id)
        self._primary_radio_spin.setValue(config.transmit.primary_radio_id)
        self._secondary_radio_spin.setValue(config.transmit.secondary_radio_id)
        self._ptt_primary_edit.setText(config.transmit.ptt_key_primary)
        self._ptt_secondary_edit.setText(config.transmit.ptt_key_secondary)
        if config.transmit.input_device:
            idx = self._input_combo.findData(config.transmit.input_device)
            if idx >= 0:
                self._input_combo.setCurrentIndex(idx)
        self._starting_radio_id_spin.setValue(config.local_transmitters.starting_radio_id)

        self._domain_combo.setCurrentIndex(config.transmit.entity_type_domain)

        country_display = COUNTRY_NAMES.get(config.transmit.entity_type_country, "Other")
        idx = self._country_combo.findText(country_display)
        if idx >= 0:
            self._country_combo.setCurrentIndex(idx)

        self._et_category_spin.setValue(config.transmit.entity_type_category)
        self._et_subcategory_spin.setValue(config.transmit.entity_type_subcategory)
        self._et_specific_spin.setValue(config.transmit.entity_type_specific)
        self._et_extra_spin.setValue(config.transmit.entity_type_extra)

    def _on_accept(self) -> None:
        exercise_id = self._exercise_spin.value()
        self._config.network.multicast_group = self._multicast_edit.text().strip()
        self._config.network.port = self._port_spin.value()
        self._config.network.interface = self._iface_edit.text().strip()
        self._config.network.exercise_id = exercise_id if exercise_id > 0 else None
        self._config.display.stale_timeout_seconds = self._stale_spin.value()
        self._config.audio.output_device = self._device_combo.currentData()

        self._config.transmit.site_id = self._site_spin.value()
        self._config.transmit.app_id = self._app_spin.value()
        self._config.transmit.entity_id = self._entity_spin.value()
        self._config.transmit.primary_radio_id = self._primary_radio_spin.value()
        self._config.transmit.secondary_radio_id = self._secondary_radio_spin.value()
        self._config.transmit.ptt_key_primary = self._ptt_primary_edit.text().strip()
        self._config.transmit.ptt_key_secondary = self._ptt_secondary_edit.text().strip()
        self._config.transmit.input_device = self._input_combo.currentData()
        self._config.local_transmitters.starting_radio_id = self._starting_radio_id_spin.value()

        self._config.transmit.entity_type_domain = self._domain_combo.currentIndex()
        self._config.transmit.entity_type_country = COUNTRY_CODES.get(
            self._country_combo.currentText(), 0
        )
        self._config.transmit.entity_type_category = self._et_category_spin.value()
        self._config.transmit.entity_type_subcategory = self._et_subcategory_spin.value()
        self._config.transmit.entity_type_specific = self._et_specific_spin.value()
        self._config.transmit.entity_type_extra = self._et_extra_spin.value()

        self.config_changed.emit(self._config)
        self.accept()
