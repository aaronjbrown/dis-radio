# DIS Radio Monitor

A PyQt6 desktop application for monitoring and participating in DIS (IEEE 1278.1) radio exercises. It receives Transmitter and Signal PDUs from a multicast network, renders live radio tiles, plays received audio, and can transmit audio back using push-to-talk (PTT).

## Features

**Receive**
- Displays each transmitter as a tile showing frequency, power, modulation, state, and time since last PDU
- Tiles dim when a transmitter goes stale and are removed after a configurable timeout
- Toggle per-transmitter audio playback — multiple radios play simultaneously
- Supports G.711 µ-law and 16-bit PCM audio encoding
- Optional exercise ID filtering

**Transmit**
- Define local transmitters (virtual radios) that appear on the DIS network; they persist across sessions
- Assign any tile as primary (P) or secondary (S) transmit radio
- Press a configurable key to start PTT — microphone audio is encoded to µ-law and sent as Signal PDUs
- Heartbeat PDUs keep local and PTT radios visible on the network
- Channel consolidation: when a local transmitter matches a received radio's frequency and modulation, both are shown as a single tile

## Requirements

- Python 3.11+
- A working audio output device (for receive)
- A microphone (for PTT transmit)
- Network access to the DIS multicast group

## Setup

```bash
python -m venv .venv
.venv/bin/pip install -r requirements.txt
```

## Running

```bash
.venv/bin/python main.py
```

Settings are stored in `config.toml` in the working directory. The file is created with defaults on first run.

## Usage

### Connecting

Set the multicast group and port in the toolbar, then click **Connect**. The status dot turns green when listening. The Exercise ID field filters PDUs to a specific exercise; leave it blank to receive all exercises.

### Transmitter tiles

Each tile shows:
- **Title** — `site:app:entity • Radio N` for observed radios, or the configured name for local transmitters
- **Freq / Power / Mod** — from the Transmitter PDU
- **State** — OFF (grey), IDLE (amber), or TX (green)
- **Seen** — time since last PDU (observed tiles) or "LOCAL" (local tiles)

A **+N** badge appears on local tiles when N remote radios share the same channel; hovering shows the individual entity IDs.

Tile controls:
| Button | Action |
|--------|--------|
| **P** | Set as primary TX radio (red when active) |
| **S** | Set as secondary TX radio (orange when active) |
| 🔊 | Toggle audio playback (blue when active) |
| 📌 | (Observed only) Pin as a local transmitter with pre-filled values |
| ✏ | (Local only) Edit name, frequency, modulation, power |
| 🗑 | (Local only) Delete — disabled while the tile is selected for TX |

### Local transmitters

Click **+** in the toolbar to add a local transmitter. Enter a name, frequency, modulation type, bandwidth, and power level. Once connected, the app broadcasts Transmitter PDUs for each local radio every 5 seconds and immediately on creation.

When a local transmitter's frequency and modulation match an incoming observed radio, that observed radio is absorbed as a "guest" rather than shown as a separate tile. If the local transmitter is deleted, the first guest is re-promoted to its own tile.

### Push-to-talk (PTT)

1. In **Settings → Transmit**, configure the entity identity (site/app/entity IDs) and PTT keys.
2. Click **P** or **S** on a tile to designate it as the primary or secondary transmit radio.
3. Hold the PTT key while connected — the **PTT** indicator in the toolbar turns red while transmitting.

The PTT key is specified as a Qt key name (e.g. `Space`, `F1`) optionally prefixed with modifiers: `Shift`, `Ctrl`, `Alt`, `Meta`. Combine with `+`: `Shift+Space`, `Ctrl+F1`. Leave the secondary field blank to disable it.

While transmitting, the local manager suppresses the heartbeat PDU for that radio so the transmitted state is not overwritten.

### Settings dialog

**General tab**
- Multicast group, port, network interface, exercise ID filter
- Stale timeout (seconds before a tile dims; tiles are removed at 2× this value)
- Audio output device

**Transmit tab**
- Site ID, App ID, Entity ID — DIS entity identity used for outbound PDUs
- Primary / secondary radio IDs — radio numbers within that entity
- PTT key (primary) and PTT key (secondary)
- Microphone (input) device
- Starting radio ID — the radio ID assigned to the first new local transmitter
- Radio Entity Type — domain, country, category, subcategory, specific, extra (SISO-REF-010)

## Configuration reference

`config.toml` is written to the working directory. See `config.example.toml` for an annotated template.

### `[network]`

| Key | Default | Description |
|-----|---------|-------------|
| `multicast_group` | `"239.255.0.1"` | DIS multicast group to join |
| `port` | `3000` | UDP port |
| `interface` | `""` | Outbound interface IP address; empty = system default |
| `exercise_id` | _(absent)_ | Integer 1–255; omit to receive all exercises |

### `[audio]`

| Key | Default | Description |
|-----|---------|-------------|
| `output_device` | _(absent)_ | Device name as reported by sounddevice; omit for system default |

### `[display]`

| Key | Default | Description |
|-----|---------|-------------|
| `stale_timeout_seconds` | `30` | Seconds before a tile dims; removed at 2× this value |

### `[transmit]`

| Key | Default | Description |
|-----|---------|-------------|
| `site_id` | `1` | DIS site ID for outbound PDUs |
| `app_id` | `1` | DIS application ID |
| `entity_id` | `1` | DIS entity ID |
| `primary_radio_id` | `1` | Radio ID used for primary PTT |
| `secondary_radio_id` | `2` | Radio ID used for secondary PTT |
| `ptt_key_primary` | `"Space"` | Key name for primary PTT |
| `ptt_key_secondary` | `""` | Key name for secondary PTT; empty = disabled |
| `input_device` | _(absent)_ | Microphone device name; omit for system default |
| `entity_type_domain` | `0` | SISO-REF-010 domain (0=Other, 1=Land, 2=Air, …) |
| `entity_type_country` | `0` | SISO-REF-010 country code |
| `entity_type_category` | `1` | Entity type category |
| `entity_type_subcategory` | `0` | Entity type subcategory |
| `entity_type_specific` | `0` | Entity type specific |
| `entity_type_extra` | `0` | Entity type extra |

### `[local_transmitters]`

| Key | Default | Description |
|-----|---------|-------------|
| `starting_radio_id` | `1` | Radio ID assigned to the first new local transmitter |

Each local transmitter is an entry in `[[local_transmitters.radios]]`:

```toml
[[local_transmitters.radios]]
name          = "Command Net"
frequency_hz  = 30000000.0
modulation_major = "NBFM (25 kHz)"
bandwidth_hz  = 25000.0
power_dbm     = 10.0
radio_id      = 1        # managed by the app; do not edit manually
```

Modulation presets: `No Statement`, `NBFM (12.5 kHz)`, `NBFM (25 kHz)`, `WFM (200 kHz)`, `AM (DSB)`, `AM (SSB)`, `Unmodulated`, `Pulse`, `CPSM`.

## Development

### Running tests

```bash
.venv/bin/python -m pytest tests/ -q
```

Tests construct raw DIS PDU byte buffers with `struct.pack` to exercise the parser against actual wire-format bytes — not via opendis serialisation.

### Architecture

```
UDP multicast → DISListener (QThread) → Qt signals → MainWindow (GUI thread)
                                                      ├── TransmitterTile (display)
                                                      ├── AudioPlayer → TransmitterStream (sounddevice)
                                                      ├── LocalTransmitterManager → DISSender
                                                      └── PTTController → AudioCapture + DISSender
```

| Module | Responsibility |
|--------|---------------|
| `dis_radio/dis/parser.py` | Parses raw bytes into typed records using `opendis` |
| `dis_radio/dis/modulation.py` | Modulation preset table and channel-key normalisation |
| `dis_radio/dis/enums.py` | SISO-REF-010 lookup tables (major modulation, domain, country) |
| `dis_radio/network/listener.py` | `DISListener(QThread)` — binds multicast socket, emits Qt signals |
| `dis_radio/network/sender.py` | `DISSender` — builds and sends Transmitter and Signal PDUs |
| `dis_radio/audio/codec.py` | G.711 µ-law encode/decode via NumPy lookup table |
| `dis_radio/audio/player.py` | `AudioPlayer` / `TransmitterStream` — jitter-buffered playback |
| `dis_radio/audio/capture.py` | `AudioCapture` — microphone capture, encodes to µ-law |
| `dis_radio/ptt_controller.py` | `PTTController` — PTT state machine, heartbeat |
| `dis_radio/local_transmitter_manager.py` | `LocalTransmitterManager` — local radio lifecycle and heartbeat |
| `dis_radio/config.py` | `AppConfig` (nested dataclasses), TOML load/save |
| `dis_radio/models.py` | `TransmitterRecord`, `LocalTransmitter`, `TransmitterKey` |
| `dis_radio/gui/main_window.py` | `MainWindow` — tile grid, channel consolidation, PTT key routing |
| `dis_radio/gui/transmitter_tile.py` | `TransmitterTile(QFrame)` — single radio card widget |
| `dis_radio/gui/settings_dialog.py` | Settings dialog (two tabs: General, Transmit) |
| `dis_radio/gui/local_transmitter_dialog.py` | Add/edit local transmitter dialog |

### Key data types

`TransmitterKey = tuple[int, int, int, int]` — `(site, app, entity, radio_id)`. This tuple is the shared identity linking Transmitter PDUs, Signal PDUs, local transmitters, and audio streams.

`TransmitterRecord` — all display state for one radio. The `is_local` flag distinguishes locally-defined radios from observed ones; `name` is set only for local radios.

### Audio pipeline

Received Signal PDUs carry either µ-law or 16-bit PCM. `codec.py` decodes both to raw `int16` PCM. `TransmitterStream` maintains a pre-roll jitter buffer (≈100 ms at 8 kHz) before feeding `sounddevice.RawOutputStream`.

For PTT, `AudioCapture` opens the microphone at 8 kHz mono, encodes each frame to µ-law with `encode_ulaw`, and passes the bytes to `DISSender.send_signal`.

### Channel consolidation

When a local transmitter is created or updated, `MainWindow` indexes it by `(frequency_hz, modulation_major_name)`. Any incoming observed radio whose channel matches is treated as a "guest" — its tile is hidden and its state is shown via the local tile's badge. Audio for guest Signal PDUs is routed through the local tile's audio stream. When the local transmitter is deleted, the first guest is promoted back to a standalone tile.

## License

GNU Affero General Public License v3.0 — see [LICENSE](LICENSE).
