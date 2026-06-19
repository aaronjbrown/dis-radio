from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
import tomlkit

from dis_radio.models import LocalTransmitter

DEFAULT_CONFIG_PATH = Path("config.toml")


@dataclass
class NetworkConfig:
    multicast_group: str = "239.255.0.1"
    port: int = 3000
    interface: str = ""
    exercise_id: Optional[int] = None


@dataclass
class AudioConfig:
    output_device: Optional[str] = None


@dataclass
class DisplayConfig:
    stale_timeout_seconds: int = 30


@dataclass
class TransmitConfig:
    site_id: int = 1
    app_id: int = 1
    entity_id: int = 1
    primary_radio_id: int = 1
    secondary_radio_id: int = 2
    ptt_key_primary: str = "Space"
    ptt_key_secondary: str = ""
    input_device: Optional[str] = None
    entity_type_domain: int = 0
    entity_type_country: int = 0
    entity_type_category: int = 1
    entity_type_subcategory: int = 0
    entity_type_specific: int = 0
    entity_type_extra: int = 0


@dataclass
class LocalTransmitterConfig:
    starting_radio_id: int = 1
    transmitters: list[LocalTransmitter] = field(default_factory=list)


@dataclass
class AppConfig:
    network: NetworkConfig = field(default_factory=NetworkConfig)
    audio: AudioConfig = field(default_factory=AudioConfig)
    display: DisplayConfig = field(default_factory=DisplayConfig)
    transmit: TransmitConfig = field(default_factory=TransmitConfig)
    local_transmitters: LocalTransmitterConfig = field(default_factory=LocalTransmitterConfig)


def load(path: Path = DEFAULT_CONFIG_PATH) -> AppConfig:
    if not path.exists():
        config = AppConfig()
        save(config, path)
        return config
    data = tomlkit.loads(path.read_text(encoding="utf-8"))
    net = data.get("network", {})
    aud = data.get("audio", {})
    dis = data.get("display", {})
    tx = data.get("transmit", {})
    lt_section = data.get("local_transmitters", {})
    radios_data = lt_section.get("radios", [])
    transmitters = [
        LocalTransmitter(
            name=str(r["name"]),
            frequency_hz=float(r["frequency_hz"]),
            modulation_major=str(r["modulation_major"]),
            power_dbm=float(r["power_dbm"]),
            radio_id=int(r["radio_id"]),
            bandwidth_hz=float(r.get("bandwidth_hz", 0.0)),
        )
        for r in radios_data
    ]
    return AppConfig(
        network=NetworkConfig(
            multicast_group=str(net.get("multicast_group", "239.255.0.1")),
            port=int(net.get("port", 3000)),
            interface=str(net.get("interface", "")),
            exercise_id=int(net["exercise_id"]) if "exercise_id" in net else None,
        ),
        audio=AudioConfig(
            output_device=aud.get("output_device", None) or None,
        ),
        display=DisplayConfig(
            stale_timeout_seconds=int(dis.get("stale_timeout_seconds", 30)),
        ),
        transmit=TransmitConfig(
            site_id=int(tx.get("site_id", 1)),
            app_id=int(tx.get("app_id", 1)),
            entity_id=int(tx.get("entity_id", 1)),
            primary_radio_id=int(tx.get("primary_radio_id", 1)),
            secondary_radio_id=int(tx.get("secondary_radio_id", 2)),
            ptt_key_primary=str(tx.get("ptt_key_primary", "Space")),
            ptt_key_secondary=str(tx.get("ptt_key_secondary", "")),
            input_device=tx.get("input_device", None) or None,
            entity_type_domain=int(tx.get("entity_type_domain", 0)),
            entity_type_country=int(tx.get("entity_type_country", 0)),
            entity_type_category=int(tx.get("entity_type_category", 1)),
            entity_type_subcategory=int(tx.get("entity_type_subcategory", 0)),
            entity_type_specific=int(tx.get("entity_type_specific", 0)),
            entity_type_extra=int(tx.get("entity_type_extra", 0)),
        ),
        local_transmitters=LocalTransmitterConfig(
            starting_radio_id=int(lt_section.get("starting_radio_id", 1)),
            transmitters=transmitters,
        ),
    )


def save(config: AppConfig, path: Path = DEFAULT_CONFIG_PATH) -> None:
    doc = tomlkit.document()

    net = tomlkit.table()
    net["multicast_group"] = config.network.multicast_group
    net["port"] = config.network.port
    net["interface"] = config.network.interface
    if config.network.exercise_id is not None:
        net["exercise_id"] = config.network.exercise_id
    doc["network"] = net

    aud = tomlkit.table()
    if config.audio.output_device is not None:
        aud["output_device"] = config.audio.output_device
    doc["audio"] = aud

    dis = tomlkit.table()
    dis["stale_timeout_seconds"] = config.display.stale_timeout_seconds
    doc["display"] = dis

    tx = tomlkit.table()
    tx["site_id"] = config.transmit.site_id
    tx["app_id"] = config.transmit.app_id
    tx["entity_id"] = config.transmit.entity_id
    tx["primary_radio_id"] = config.transmit.primary_radio_id
    tx["secondary_radio_id"] = config.transmit.secondary_radio_id
    tx["ptt_key_primary"] = config.transmit.ptt_key_primary
    tx["ptt_key_secondary"] = config.transmit.ptt_key_secondary
    if config.transmit.input_device is not None:
        tx["input_device"] = config.transmit.input_device
    tx["entity_type_domain"] = config.transmit.entity_type_domain
    tx["entity_type_country"] = config.transmit.entity_type_country
    tx["entity_type_category"] = config.transmit.entity_type_category
    tx["entity_type_subcategory"] = config.transmit.entity_type_subcategory
    tx["entity_type_specific"] = config.transmit.entity_type_specific
    tx["entity_type_extra"] = config.transmit.entity_type_extra
    doc["transmit"] = tx

    lt_table = tomlkit.table()
    lt_table["starting_radio_id"] = config.local_transmitters.starting_radio_id
    if config.local_transmitters.transmitters:
        radios = tomlkit.aot()
        for lt in config.local_transmitters.transmitters:
            t = tomlkit.table()
            t["name"] = lt.name
            t["frequency_hz"] = lt.frequency_hz
            t["modulation_major"] = lt.modulation_major
            t["power_dbm"] = lt.power_dbm
            t["bandwidth_hz"] = lt.bandwidth_hz
            t["radio_id"] = lt.radio_id
            radios.append(t)
        lt_table["radios"] = radios
    doc["local_transmitters"] = lt_table

    path.write_text(tomlkit.dumps(doc), encoding="utf-8")
