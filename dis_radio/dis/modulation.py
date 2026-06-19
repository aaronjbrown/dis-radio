from __future__ import annotations

from dis_radio.dis.enums import MAJOR_MOD_NAMES

# (spread_spectrum, major_modulation, detail, system, default_bandwidth_hz)
Preset = tuple[int, int, int, int, float]

PRESETS: dict[str, Preset] = {
    "No Statement":     (0, 0, 0, 0,       0.0),
    "NBFM (12.5 kHz)":  (0, 3, 1, 1,  12_500.0),
    "NBFM (25 kHz)":    (0, 3, 1, 1,  25_000.0),
    "WFM (200 kHz)":    (0, 3, 1, 1, 200_000.0),
    "AM (DSB)":         (0, 1, 1, 1,   8_000.0),
    "AM (SSB)":         (0, 1, 4, 1,   3_000.0),
    "Unmodulated":      (0, 6, 0, 1,       0.0),
    "Pulse":            (0, 5, 0, 1,       0.0),
    "CPSM":             (0, 7, 0, 1,       0.0),
}


def channel_modulation_key(modulation_major: str) -> str:
    """Return the SISO major modulation name used as the channel grouping key.

    Accepts either a UI preset name ("NBFM (25 kHz)") or a name already
    produced by the parser ("Angle"), and returns the SISO UID 155 major
    modulation name in both cases so local and remote records compare equal.
    """
    preset = PRESETS.get(modulation_major)
    if preset is not None:
        return MAJOR_MOD_NAMES.get(preset[1], modulation_major)
    return modulation_major
