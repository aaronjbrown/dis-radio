from __future__ import annotations

import collections
import logging
from typing import Any

import sounddevice as sd

from dis_radio.audio.codec import decode
from dis_radio.models import TransmitterKey

log = logging.getLogger(__name__)

_STREAM_CHANNELS = 1
_STREAM_DTYPE = "int16"
_BYTES_PER_SAMPLE = 2

# Number of PDU-sized chunks to accumulate before starting (and to re-accumulate
# after the queue runs dry).  Each chunk is one decoded Signal PDU = 160 samples
# = 320 bytes at 8 kHz.  5 chunks ≈ 100 ms — enough to absorb typical UDP jitter
# without adding perceptible latency.
_PRE_ROLL_CHUNKS = 5


class TransmitterStream:
    def __init__(self, sample_rate: int, output_device: str | None) -> None:
        self.sample_rate = sample_rate
        # deque gives O(1) popleft and allows in-place head replacement for
        # partial chunks, avoiding the queue.put() tail-append ordering bug.
        self._buf: collections.deque[bytes] = collections.deque()
        self._buffering = True  # True while waiting for the pre-roll to fill
        self._muted = False  # silences during PTT TX without closing the stream
        self._stream = sd.RawOutputStream(
            samplerate=sample_rate,
            channels=_STREAM_CHANNELS,
            dtype=_STREAM_DTYPE,
            device=output_device,
            latency="high",
            callback=self._callback,
        )
        self._stream.start()

    def feed(self, pcm: bytes) -> None:
        self._buf.append(pcm)

    def mute(self) -> None:
        self._muted = True

    def unmute(self) -> None:
        self._muted = False

    def close(self) -> None:
        self._stream.stop()
        self._stream.close()

    def _callback(self, outdata: Any, frames: int, time: Any, status: Any) -> None:
        if status:
            log.warning("audio output status: %s", status)
        needed = frames * _BYTES_PER_SAMPLE
        buf = bytearray(needed)

        # While muted (PTT active on this channel), output silence without
        # draining _buf so the buffer is intact when transmission ends.
        if self._muted:
            outdata[:] = buf
            return

        # Hold back output until the jitter buffer has pre-rolled, and restart
        # buffering whenever the queue runs dry during playback.
        if self._buffering:
            if len(self._buf) < _PRE_ROLL_CHUNKS:
                outdata[:] = buf  # silence while buffering
                return
            self._buffering = False

        offset = 0
        while offset < needed and self._buf:
            chunk = self._buf[0]
            n = min(len(chunk), needed - offset)
            buf[offset : offset + n] = chunk[:n]
            offset += n
            if n == len(chunk):
                self._buf.popleft()
            else:
                # Partial consume: replace head with the unconsumed remainder so
                # it is read first on the next callback (not reordered to the tail).
                self._buf[0] = chunk[n:]

        if offset < needed:
            # Queue ran dry mid-callback — rebuffer to avoid future starvation.
            self._buffering = True

        outdata[:] = buf


class AudioPlayer:
    def __init__(self, output_device: str | None) -> None:
        self._output_device = output_device
        self._enabled: set[TransmitterKey] = set()
        self._streams: dict[TransmitterKey, TransmitterStream] = {}

    def close_all(self) -> None:
        for key in list(self._streams):
            self.disable(key)

    def enable(self, key: TransmitterKey) -> None:
        self._enabled.add(key)

    def disable(self, key: TransmitterKey) -> None:
        self._enabled.discard(key)
        stream = self._streams.pop(key, None)
        if stream is not None:
            try:
                stream.close()
            except Exception as exc:
                log.warning("Error closing stream for %s: %s", key, exc)

    def mute_for_tx(self, key: TransmitterKey) -> None:
        """Silence output for key during PTT without closing the stream.

        Stops feeding new data (removes from _enabled) and freezes the output
        callback so the jitter buffer is preserved for instant resume on unmute.
        """
        self._enabled.discard(key)
        stream = self._streams.get(key)
        if stream is not None:
            stream.mute()

    def unmute_for_tx(self, key: TransmitterKey) -> None:
        """Restore output for key after PTT ends.

        Re-enables data feed and unmutes the callback. Because _buf was frozen
        during mute, playback resumes immediately without a pre-roll delay.
        """
        self._enabled.add(key)
        stream = self._streams.get(key)
        if stream is not None:
            stream.unmute()

    def feed(
        self,
        key: TransmitterKey,
        data: bytes,
        encoding_type: int,
        sample_rate: int,
    ) -> None:
        if key not in self._enabled:
            return
        pcm = decode(data, encoding_type)
        if pcm is None:
            log.debug("Unsupported encoding type %d for key %s", encoding_type, key)
            return
        if key in self._streams and self._streams[key].sample_rate != sample_rate:
            try:
                self._streams[key].close()
            except Exception as exc:
                log.warning("Error closing stream on rate change for %s: %s", key, exc)
            del self._streams[key]
        if key not in self._streams:
            self._streams[key] = TransmitterStream(sample_rate, self._output_device)
        self._streams[key].feed(pcm)
