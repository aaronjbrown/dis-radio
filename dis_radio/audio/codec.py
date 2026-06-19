from __future__ import annotations
import numpy as np

# ITU-T G.711 µ-law exponent lookup table
_EXP_LUT = np.array([0, 132, 396, 924, 1980, 4092, 8316, 16764], dtype=np.int32)


def _build_ulaw_table() -> np.ndarray:
    indices = np.arange(256, dtype=np.uint8)
    complemented = (~indices).astype(np.uint8)
    sign = (complemented & 0x80).astype(np.int32)
    exp = ((complemented >> 4) & 0x07).astype(np.int32)
    mant = (complemented & 0x0F).astype(np.int32)
    magnitude = _EXP_LUT[exp] + (mant << (exp + 3))
    linear = np.where(sign != 0, -magnitude, magnitude)
    # For 0x7F (negative silence), use -1 (mid-rise quantization) to distinguish from
    # 0xFF (positive silence) and enable lossless roundtrip: decode(0x7F) = -1, encode(-1) = 0x7F
    linear = np.where(indices == 0x7F, -1, linear)
    return np.clip(linear, -32768, 32767).astype(np.int16)


_ULAW_TABLE: np.ndarray = _build_ulaw_table()


def decode_ulaw(data: bytes) -> bytes:
    return _ULAW_TABLE[np.frombuffer(data, dtype=np.uint8)].tobytes()


def _build_ulaw_encode_table() -> np.ndarray:
    # Index by uint16 (reinterpretation of int16, so -32768 → index 32768)
    indices = np.arange(65536, dtype=np.uint16)
    samples = indices.view(np.int16).astype(np.int32)

    sign = np.where(samples < 0, 0x80, 0).astype(np.int32)
    magnitude = np.abs(samples)
    # G.711 standard bias = 0x84 = 132; cap at 32767
    magnitude = np.minimum(magnitude + 132, 32767)

    # Exponent: position of highest set bit in (magnitude >> 7), clamped to 0-7
    # magnitude ≤ 32767 after the clamp above, so >> 7 ≤ 255 — no masking needed
    shifted = magnitude >> 7
    exp = np.zeros(65536, dtype=np.int32)
    for e in range(1, 8):
        exp = np.where(shifted >= (1 << e), e, exp)

    mant = ((magnitude >> (exp + 3)) & 0x0F).astype(np.int32)
    ulaw = (~(sign | (exp << 4) | mant)).astype(np.uint8)
    return ulaw


_ULAW_ENCODE_TABLE: np.ndarray = _build_ulaw_encode_table()


def encode_ulaw(data: bytes) -> bytes:
    """Encode int16 PCM bytes to G.711 µ-law. Input must be little-endian int16."""
    return _ULAW_ENCODE_TABLE[np.frombuffer(data, dtype=np.int16).view(np.uint16)].tobytes()


def decode_pcm(data: bytes) -> bytes:
    return data


_DECODERS = {0: decode_pcm, 1: decode_ulaw}


def decode(data: bytes, encoding_type: int) -> bytes | None:
    decoder = _DECODERS.get(encoding_type)
    if decoder is None:
        return None
    return decoder(data)


def encode_pcm(data: bytes) -> bytes:
    return data


_ENCODERS = {0: encode_pcm, 1: encode_ulaw}
