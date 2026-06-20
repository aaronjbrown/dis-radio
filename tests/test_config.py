import tempfile
from pathlib import Path

from dis_radio.config import (
    AppConfig,
    load,
    save,
)
from dis_radio.models import LocalTransmitter


def test_load_writes_defaults_when_missing():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "config.toml"
        config = load(path)
        assert config.network.multicast_group == "239.255.0.1"
        assert config.network.port == 3000
        assert config.network.exercise_id is None
        assert path.exists()


def test_round_trip_network_settings():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "config.toml"
        config = AppConfig()
        config.network.port = 4000
        config.network.exercise_id = 7
        save(config, path)
        loaded = load(path)
        assert loaded.network.port == 4000
        assert loaded.network.exercise_id == 7


def test_round_trip_stale_timeout():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "config.toml"
        config = AppConfig()
        config.display.stale_timeout_seconds = 60
        save(config, path)
        loaded = load(path)
        assert loaded.display.stale_timeout_seconds == 60


def test_round_trip_exercise_id_none():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "config.toml"
        config = AppConfig()
        config.network.exercise_id = None
        save(config, path)
        loaded = load(path)
        assert loaded.network.exercise_id is None


def test_transmit_config_defaults():
    config = AppConfig()
    assert config.transmit.site_id == 1
    assert config.transmit.app_id == 1
    assert config.transmit.entity_id == 1
    assert config.transmit.primary_radio_id == 1
    assert config.transmit.secondary_radio_id == 2
    assert config.transmit.ptt_key_primary == "Space"
    assert config.transmit.ptt_key_secondary == ""
    assert config.transmit.input_device is None


def test_round_trip_transmit_config():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "config.toml"
        config = AppConfig()
        config.transmit.site_id = 10
        config.transmit.app_id = 20
        config.transmit.entity_id = 30
        config.transmit.primary_radio_id = 5
        config.transmit.secondary_radio_id = 6
        config.transmit.ptt_key_primary = "F1"
        config.transmit.ptt_key_secondary = "F2"
        config.transmit.input_device = "My Mic"
        save(config, path)
        loaded = load(path)
        assert loaded.transmit.site_id == 10
        assert loaded.transmit.app_id == 20
        assert loaded.transmit.entity_id == 30
        assert loaded.transmit.primary_radio_id == 5
        assert loaded.transmit.secondary_radio_id == 6
        assert loaded.transmit.ptt_key_primary == "F1"
        assert loaded.transmit.ptt_key_secondary == "F2"
        assert loaded.transmit.input_device == "My Mic"


def test_round_trip_transmit_input_device_none():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "config.toml"
        config = AppConfig()
        config.transmit.input_device = None
        save(config, path)
        loaded = load(path)
        assert loaded.transmit.input_device is None


def test_round_trip_transmit_ptt_key_secondary_empty():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "config.toml"
        config = AppConfig()
        config.transmit.ptt_key_secondary = ""
        save(config, path)
        loaded = load(path)
        assert loaded.transmit.ptt_key_secondary == ""


def test_local_transmitters_defaults():
    config = AppConfig()
    assert config.local_transmitters.starting_radio_id == 1
    assert config.local_transmitters.transmitters == []


def test_round_trip_local_transmitters_empty():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "config.toml"
        config = AppConfig()
        save(config, path)
        loaded = load(path)
        assert loaded.local_transmitters.starting_radio_id == 1
        assert loaded.local_transmitters.transmitters == []


def test_round_trip_local_transmitters_with_entries():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "config.toml"
        config = AppConfig()
        config.local_transmitters.starting_radio_id = 5
        config.local_transmitters.transmitters = [
            LocalTransmitter(
                name="Command Net",
                frequency_hz=30_000_000.0,
                modulation_major="AM (DSB)",
                power_dbm=10.0,
                radio_id=5,
            ),
            LocalTransmitter(
                name="Admin Net",
                frequency_hz=40_000_000.0,
                modulation_major="NBFM (25 kHz)",
                power_dbm=5.0,
                radio_id=6,
            ),
        ]
        save(config, path)
        loaded = load(path)
        assert loaded.local_transmitters.starting_radio_id == 5
        assert len(loaded.local_transmitters.transmitters) == 2
        lt = loaded.local_transmitters.transmitters[0]
        assert lt.name == "Command Net"
        assert lt.frequency_hz == 30_000_000.0
        assert lt.modulation_major == "AM (DSB)"
        assert lt.power_dbm == 10.0
        assert lt.radio_id == 5


def test_entity_type_defaults():
    config = AppConfig()
    assert config.transmit.entity_type_domain == 0
    assert config.transmit.entity_type_country == 0
    assert config.transmit.entity_type_category == 1
    assert config.transmit.entity_type_subcategory == 0
    assert config.transmit.entity_type_specific == 0
    assert config.transmit.entity_type_extra == 0


def test_round_trip_entity_type():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "config.toml"
        config = AppConfig()
        config.transmit.entity_type_domain = 2       # Air
        config.transmit.entity_type_country = 255    # United States
        config.transmit.entity_type_category = 1
        config.transmit.entity_type_subcategory = 3
        config.transmit.entity_type_specific = 7
        config.transmit.entity_type_extra = 0
        save(config, path)
        loaded = load(path)
        assert loaded.transmit.entity_type_domain == 2
        assert loaded.transmit.entity_type_country == 255
        assert loaded.transmit.entity_type_category == 1
        assert loaded.transmit.entity_type_subcategory == 3
        assert loaded.transmit.entity_type_specific == 7
        assert loaded.transmit.entity_type_extra == 0


def test_round_trip_local_transmitter_bandwidth_hz():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "config.toml"
        config = AppConfig()
        config.local_transmitters.transmitters = [
            LocalTransmitter(
                name="Net A", frequency_hz=148_500_000.0,
                modulation_major="NBFM (25 kHz)", power_dbm=10.0,
                radio_id=1, bandwidth_hz=25_000.0,
            ),
        ]
        save(config, path)
        loaded = load(path)
        assert loaded.local_transmitters.transmitters[0].bandwidth_hz == 25_000.0


def test_local_transmitter_bandwidth_hz_missing_from_file_loads_as_zero():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "config.toml"
        # Write a config without bandwidth_hz — simulates old config files
        path.write_text(
            "[network]\nmulticast_group = \"239.255.0.1\"\nport = 3000\ninterface = \"\"\n"  # noqa: E501
            "[audio]\n[display]\nstale_timeout_seconds = 30\n[transmit]\n"
            "site_id = 1\napp_id = 1\nentity_id = 1\nprimary_radio_id = 1\n"
            "secondary_radio_id = 2\nptt_key_primary = \"Space\"\nptt_key_secondary = \"\"\n"  # noqa: E501
            "[local_transmitters]\nstarting_radio_id = 1\n"
            "[[local_transmitters.radios]]\nname = \"R1\"\nfrequency_hz = 148500000.0\n"
            "modulation_major = \"NBFM (25 kHz)\"\npower_dbm = 10.0\nradio_id = 1\n"
        )
        loaded = load(path)
        assert loaded.local_transmitters.transmitters[0].bandwidth_hz == 0.0


def test_load_missing_local_transmitters_section_uses_defaults():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "config.toml"
        # Write a config without [local_transmitters]
        path.write_text("[network]\nmulticast_group = \"239.255.0.1\"\nport = 3000\ninterface = \"\"\n")  # noqa: E501
        loaded = load(path)
        assert loaded.local_transmitters.starting_radio_id == 1
        assert loaded.local_transmitters.transmitters == []
