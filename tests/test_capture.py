from unittest.mock import MagicMock

import numpy as np
import pytest

from dis_radio.audio.capture import AudioCapture


@pytest.fixture
def mock_sd(monkeypatch):
    mock = MagicMock()
    mock_stream = MagicMock()
    mock.InputStream.return_value = mock_stream
    monkeypatch.setattr("dis_radio.audio.capture.sd", mock)
    return mock, mock_stream


def test_start_opens_input_stream(mock_sd):
    sd_mock, stream_mock = mock_sd
    capture = AudioCapture(input_device=None)
    result = capture.start(lambda chunk: None)
    assert result is True
    sd_mock.InputStream.assert_called_once()
    stream_mock.start.assert_called_once()


def test_start_passes_input_device(mock_sd):
    sd_mock, stream_mock = mock_sd
    capture = AudioCapture(input_device="My Mic")
    capture.start(lambda chunk: None)
    call_kwargs = sd_mock.InputStream.call_args.kwargs
    assert call_kwargs.get("device") == "My Mic"


def test_start_uses_8000hz_mono_int16(mock_sd):
    sd_mock, _ = mock_sd
    capture = AudioCapture(input_device=None)
    capture.start(lambda chunk: None)
    call_kwargs = sd_mock.InputStream.call_args.kwargs
    assert call_kwargs["samplerate"] == 8000
    assert call_kwargs["channels"] == 1
    assert call_kwargs["dtype"] == "int16"


def test_stop_closes_stream(mock_sd):
    sd_mock, stream_mock = mock_sd
    capture = AudioCapture(input_device=None)
    capture.start(lambda chunk: None)
    capture.stop()
    stream_mock.stop.assert_called_once()
    stream_mock.close.assert_called_once()


def test_stop_without_start_does_not_raise(mock_sd):
    capture = AudioCapture(input_device=None)
    capture.stop()  # must not raise


def test_start_twice_does_not_open_two_streams(mock_sd):
    sd_mock, _ = mock_sd
    capture = AudioCapture(input_device=None)
    capture.start(lambda chunk: None)
    capture.start(lambda chunk: None)
    sd_mock.InputStream.assert_called_once()


def test_callback_calls_on_chunk_with_ulaw_encoded_data(mock_sd):
    sd_mock, _ = mock_sd
    chunks = []
    capture = AudioCapture(input_device=None)
    capture.start(chunks.append)

    # Extract the callback that was registered
    callback = sd_mock.InputStream.call_args.kwargs["callback"]

    # Simulate 160 frames of silence (int16 value = 0 → µ-law 0xFF)
    indata = np.zeros((160, 1), dtype=np.int16)
    callback(indata, 160, None, None)

    assert len(chunks) == 1
    assert len(chunks[0]) == 160
    # linear silence (0) must encode to µ-law silence (0xFF)
    assert all(b == 0xFF for b in chunks[0])


def test_callback_encodes_known_value(mock_sd):
    sd_mock, _ = mock_sd
    chunks = []
    capture = AudioCapture(input_device=None)
    capture.start(chunks.append)
    callback = sd_mock.InputStream.call_args.kwargs["callback"]

    # int16 32124 must encode to µ-law 0x80
    indata = np.full((1, 1), 32124, dtype=np.int16)
    callback(indata, 1, None, None)

    assert len(chunks) == 1
    assert chunks[0] == bytes([0x80])


def test_start_returns_false_on_mic_error(mock_sd):
    sd_mock, _ = mock_sd
    sd_mock.InputStream.side_effect = Exception("no mic")
    capture = AudioCapture(input_device=None)
    result = capture.start(lambda chunk: None)
    assert result is False
