import struct
from dis_radio.audio.codec import decode_ulaw, encode_ulaw


def _pack_i16(v: int) -> bytes:
    return struct.pack('<h', v)


def test_encode_silence_gives_0xFF():
    # G.711 positive silence: linear 0 → µ-law 0xFF
    assert encode_ulaw(_pack_i16(0)) == b'\xFF'


def test_encode_negative_silence_gives_0x7F():
    # Instead verify: encode(decode(0x7F)) == 0x7F
    decoded = decode_ulaw(bytes([0x7F]))
    assert encode_ulaw(decoded) == bytes([0x7F])


def test_encode_max_positive_gives_0x80():
    # decode_ulaw(0x80) = 32124; re-encoding should give 0x80
    assert encode_ulaw(_pack_i16(32124)) == b'\x80'


def test_encode_max_negative_gives_0x00():
    # decode_ulaw(0x00) = -32124
    assert encode_ulaw(_pack_i16(-32124)) == b'\x00'


def test_encode_decode_roundtrip_all_codes():
    # For every µ-law code, decode then re-encode must give back the same code.
    all_codes = bytes(range(256))
    decoded = decode_ulaw(all_codes)   # 512 bytes (256 int16 samples)
    reencoded = encode_ulaw(decoded)
    assert reencoded == all_codes


def test_encode_multi_sample_output_length():
    # 3 int16 samples → 3 µ-law bytes
    data = struct.pack('<3h', 0, 32124, -32124)
    result = encode_ulaw(data)
    assert len(result) == 3


def test_encode_multi_sample_known_values():
    data = struct.pack('<3h', 0, 32124, -32124)
    result = encode_ulaw(data)
    assert result == bytes([0xFF, 0x80, 0x00])
