from unittest.mock import MagicMock

import pytest

from dis_radio.audio.player import AudioPlayer


@pytest.fixture
def mock_sd(monkeypatch):
    """Patch sounddevice so no real audio device is needed."""
    mock = MagicMock()
    mock_stream = MagicMock()
    mock.RawOutputStream.return_value = mock_stream
    monkeypatch.setattr("dis_radio.audio.player.sd", mock)
    return mock, mock_stream


def test_enable_creates_stream_on_first_feed(mock_sd):
    sd_mock, stream_mock = mock_sd
    player = AudioPlayer(output_device=None)
    key = (1, 2, 3, 4)

    player.enable(key)
    # No stream yet — created lazily on first feed
    sd_mock.RawOutputStream.assert_not_called()

    player.feed(key, bytes([0xFF, 0xFF]), encoding_type=1, sample_rate=8000)
    sd_mock.RawOutputStream.assert_called_once()
    stream_mock.start.assert_called_once()


def test_disable_stops_and_closes_stream(mock_sd):
    sd_mock, stream_mock = mock_sd
    player = AudioPlayer(output_device=None)
    key = (1, 2, 3, 4)

    player.enable(key)
    player.feed(key, bytes([0xFF]), encoding_type=1, sample_rate=8000)
    player.disable(key)

    stream_mock.stop.assert_called_once()
    stream_mock.close.assert_called_once()


def test_feed_when_not_enabled_does_nothing(mock_sd):
    sd_mock, _ = mock_sd
    player = AudioPlayer(output_device=None)
    key = (1, 2, 3, 4)

    player.feed(key, bytes([0xFF]), encoding_type=1, sample_rate=8000)
    sd_mock.RawOutputStream.assert_not_called()


def test_feed_unknown_encoding_does_nothing(mock_sd):
    sd_mock, _ = mock_sd
    player = AudioPlayer(output_device=None)
    key = (1, 2, 3, 4)

    player.enable(key)
    player.feed(key, bytes([0x00]), encoding_type=99, sample_rate=8000)
    sd_mock.RawOutputStream.assert_not_called()


def test_sample_rate_change_recreates_stream(mock_sd):
    sd_mock, _ = mock_sd
    player = AudioPlayer(output_device=None)
    key = (1, 2, 3, 4)

    player.enable(key)
    player.feed(key, bytes([0xFF]), encoding_type=1, sample_rate=8000)
    player.feed(key, bytes([0xFF]), encoding_type=1, sample_rate=16000)

    assert sd_mock.RawOutputStream.call_count == 2


def test_disable_without_enable_does_not_raise(mock_sd):
    player = AudioPlayer(output_device=None)
    player.disable((9, 9, 9, 9))  # should not raise


def test_enable_twice_does_not_create_two_streams(mock_sd):
    sd_mock, stream_mock = mock_sd
    player = AudioPlayer(output_device=None)
    key = (1, 2, 3, 4)

    player.enable(key)
    player.enable(key)
    player.feed(key, bytes([0xFF]), encoding_type=1, sample_rate=8000)

    sd_mock.RawOutputStream.assert_called_once()
