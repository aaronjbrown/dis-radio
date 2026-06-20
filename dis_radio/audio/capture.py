from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

import sounddevice as sd

from dis_radio.audio.codec import encode_ulaw

log = logging.getLogger(__name__)

_SAMPLE_RATE = 8000
_CHANNELS = 1
_DTYPE = "int16"


class AudioCapture:
    def __init__(self, input_device: str | None) -> None:
        self._input_device = input_device
        self._stream: sd.InputStream | None = None

    def start(self, on_chunk: Callable[[bytes], None]) -> bool:
        """Open the microphone and start calling on_chunk with µ-law encoded frames.

        Returns True on success, False if the mic could not be opened.
        """
        if self._stream is not None:
            return True

        def _callback(indata: Any, frames: int, time: Any, status: Any) -> None:
            if status:
                log.warning("audio input status: %s", status)
            on_chunk(encode_ulaw(indata.tobytes()))

        try:
            self._stream = sd.InputStream(
                samplerate=_SAMPLE_RATE,
                channels=_CHANNELS,
                dtype=_DTYPE,
                device=self._input_device,
                callback=_callback,
            )
            self._stream.start()
            return True
        except Exception as exc:
            log.warning("Failed to open microphone: %s", exc)
            self._stream = None
            return False

    def stop(self) -> None:
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception as exc:
                log.warning("Error closing microphone stream: %s", exc)
            self._stream = None
