from __future__ import annotations

import logging
from datetime import datetime
from enum import Enum

from opendis.dis7 import SignalPdu, TransmitterPdu
from opendis.PduFactory import createPdu

from dis_radio.dis.enums import MAJOR_MOD_NAMES
from dis_radio.models import TransmitterKey, TransmitterRecord, TransmitterState

log = logging.getLogger(__name__)

# Maps (DIS encoding class, DIS encoding type) → internal codec type
# Internal: 0 = PCM pass-through, 1 = µ-law
_ENCODING_MAP: dict[tuple[int, int], int] = {
    (0, 1): 1,  # Encoded Audio, µ-law
    (0, 4): 0,  # Encoded Audio, 16-bit PCM big-endian
    (0, 6): 0,  # Encoded Audio, 16-bit PCM little-endian
}


class ParsedKind(Enum):
    TRANSMITTER = "transmitter"
    SIGNAL = "signal"


ParsedPDU = (
    tuple[ParsedKind, TransmitterRecord]
    | tuple[ParsedKind, TransmitterKey, bytes, int, int]
)


def parse_pdu(data: bytes) -> ParsedPDU | None:
    if not data:
        return None
    try:
        pdu = createPdu(data)
    except Exception as exc:
        log.debug("Failed to parse PDU: %s", exc)
        return None
    if pdu is None:
        return None
    if isinstance(pdu, TransmitterPdu):
        return _parse_transmitter(pdu)
    if isinstance(pdu, SignalPdu):
        return _parse_signal(pdu)
    return None


def _parse_transmitter(pdu: TransmitterPdu) -> tuple[ParsedKind, TransmitterRecord]:
    # opendis 1.0 field names: radioReferenceID (EntityID), radioNumber
    # EntityID sub-fields: siteID, applicationID, entityID
    eid = pdu.radioReferenceID
    record = TransmitterRecord(
        entity_id=(eid.siteID, eid.applicationID, eid.entityID),
        radio_id=pdu.radioNumber,
        state=TransmitterState(min(pdu.transmitState, 2)),
        frequency_hz=float(pdu.frequency),
        power_dbm=float(pdu.power),
        bandwidth_hz=float(pdu.transmitFrequencyBandwidth),
        modulation_major=MAJOR_MOD_NAMES.get(
            pdu.modulationType.majorModulation, "Unknown"
        ),
        exercise_id=pdu.exerciseID,
        last_seen=datetime.now(),
    )
    return (ParsedKind.TRANSMITTER, record)


def _parse_signal(pdu: SignalPdu) -> tuple[ParsedKind, TransmitterKey, bytes, int, int]:
    # opendis 1.0 field names: entityID (EntityID), radioID
    # EntityID sub-fields: siteID, applicationID, entityID
    eid = pdu.entityID
    key: TransmitterKey = (eid.siteID, eid.applicationID, eid.entityID, pdu.radioID)
    actual_bytes = pdu.dataLength // 8
    audio = bytes(pdu.data[:actual_bytes])
    enc_class = (pdu.encodingScheme >> 14) & 0x03
    enc_type = pdu.encodingScheme & 0x3FFF
    codec_type = _ENCODING_MAP.get((enc_class, enc_type), -1)
    if codec_type == -1:
        log.debug("Unsupported DIS encoding class=%d type=%d", enc_class, enc_type)
    return (ParsedKind.SIGNAL, key, audio, codec_type, pdu.sampleRate)
