import struct

from dis_radio.audio.codec import decode, decode_pcm, decode_ulaw


def _int16(data: bytes) -> int:
    return struct.unpack("<h", data)[0]


def _int16s(data: bytes) -> tuple:
    n = len(data) // 2
    return struct.unpack(f"<{n}h", data)


# G.711 µ-law reference values — verified against ITU-T G.711 spec
def test_ulaw_silence_positive():
    # 0xFF = positive zero (silence) in µ-law → linear 0
    assert _int16(decode_ulaw(bytes([0xFF]))) == 0


def test_ulaw_silence_negative():
    # 0x7F = negative zero in µ-law → linear -1 (mid-rise quantization for roundtrip)
    assert _int16(decode_ulaw(bytes([0x7F]))) == -1


def test_ulaw_max_positive():
    # 0x80 = most positive µ-law value → linear 32124
    assert _int16(decode_ulaw(bytes([0x80]))) == 32124


def test_ulaw_max_negative():
    # 0x00 = most negative µ-law value → linear -32124
    assert _int16(decode_ulaw(bytes([0x00]))) == -32124


def test_ulaw_small_positive():
    # 0xFE → complemented=0x01, sign=+, exp=0, mant=1 → EXP_LUT[0] + (1<<3) = 8
    assert _int16(decode_ulaw(bytes([0xFE]))) == 8


def test_ulaw_small_negative():
    # 0x7E → complemented=0x81, sign=-, exp=0, mant=1 → -8
    assert _int16(decode_ulaw(bytes([0x7E]))) == -8


def test_ulaw_multi_sample_output_length():
    result = decode_ulaw(bytes([0xFF, 0x7F, 0xFE]))
    assert len(result) == 6  # 3 samples × 2 bytes each (int16)


def test_ulaw_multi_sample_values():
    result = decode_ulaw(bytes([0xFF, 0x7F, 0xFE]))
    assert _int16s(result) == (0, -1, 8)


def test_pcm_passthrough():
    data = b"\x01\x02\x03\x04"
    assert decode_pcm(data) == data


def test_decode_dispatch_ulaw():
    result = decode(bytes([0xFF]), encoding_type=1)
    assert result is not None
    assert _int16(result) == 0


def test_decode_dispatch_pcm():
    data = b"\xAB\xCD"
    assert decode(data, encoding_type=0) == data


def test_decode_unknown_encoding_returns_none():
    assert decode(b"\x00", encoding_type=99) is None
