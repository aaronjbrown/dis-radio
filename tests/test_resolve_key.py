import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication

from dis_radio.gui.main_window import MainWindow


@pytest.fixture(scope="session")
def qapp():
    return QApplication.instance() or QApplication([])


def test_bare_key_returns_no_modifier_and_key(qapp):
    assert MainWindow._resolve_key("Space") == (
        Qt.KeyboardModifier.NoModifier,
        Qt.Key.Key_Space,
    )


def test_shift_modifier(qapp):
    assert MainWindow._resolve_key("Shift+Space") == (
        Qt.KeyboardModifier.ShiftModifier,
        Qt.Key.Key_Space,
    )


def test_ctrl_modifier(qapp):
    assert MainWindow._resolve_key("Ctrl+Space") == (
        Qt.KeyboardModifier.ControlModifier,
        Qt.Key.Key_Space,
    )


def test_alt_modifier(qapp):
    assert MainWindow._resolve_key("Alt+F1") == (
        Qt.KeyboardModifier.AltModifier,
        Qt.Key.Key_F1,
    )


def test_multiple_modifiers(qapp):
    assert MainWindow._resolve_key("Ctrl+Shift+F1") == (
        Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier,
        Qt.Key.Key_F1,
    )


def test_unknown_key_returns_none(qapp):
    assert MainWindow._resolve_key("Shift+Banana") is None


def test_unknown_modifier_returns_none(qapp):
    assert MainWindow._resolve_key("Super+Space") is None


def test_empty_string_returns_none(qapp):
    assert MainWindow._resolve_key("") is None


def test_meta_modifier(qapp):
    assert MainWindow._resolve_key("Meta+Space") == (
        Qt.KeyboardModifier.MetaModifier,
        Qt.Key.Key_Space,
    )


def test_bare_non_space_key(qapp):
    assert MainWindow._resolve_key("F4") == (
        Qt.KeyboardModifier.NoModifier,
        Qt.Key.Key_F4,
    )


def test_bare_unknown_key(qapp):
    assert MainWindow._resolve_key("Banana") is None


def test_keypad_modifier_not_in_relevant_modifiers(qapp):
    # KeypadModifier is set when keys originate from the numeric keypad.
    # It must be stripped before PTT comparison so bare keys still fire.
    masked = Qt.KeyboardModifier.KeypadModifier & MainWindow._RELEVANT_MODIFIERS
    assert masked == Qt.KeyboardModifier.NoModifier


def test_trailing_plus_returns_none(qapp):
    assert MainWindow._resolve_key("Shift+") is None


def test_plus_alone_returns_none(qapp):
    assert MainWindow._resolve_key("+") is None
