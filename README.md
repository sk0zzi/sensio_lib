# Sensio Library

![AI: Assisted](https://img.shields.io/badge/AI-Assisted-blue)

A minimal async library to control Sensio (EOPT Home) smart house systems. Designed for easy integration with Home Assistant.

## Features (v1.3.0)

- **Unity and HA pilot** — Supports getting devices from both `unity` and `ha-pilot`
- **Local control & live state feedback** — Sends commands directly to your controller on the LAN and listens to its RSN event stream for real-time state updates (including changes from physical wall switches)
- **Automatic reconnect** — Automatically reconnects with exponential backoff if the connection to the controller drops
- **Hub validation** — Verifies hub identity (serial, firmware, MAC, product ID) upon connection
- **Cloud API** — Fetch device configuration from the EOPT cloud (one-time setup)
- **Lights** — Turn individual relay lights on/off with live state tracking
- **Dimmers** — Set brightness (`0–100%`) and turn dimmers on/off (restoring previous brightness), with live brightness feedback
- **Thermostats (Heated Floors)** — Read current/target temperatures and active heating status, and set target temperatures (`0.5°C` precision)
- **Zones (Rooms)** — Resolves human-readable zone names and exposes `zone_name` on all devices
- **Scenes** — Activate house-level lighting scenes

## Architecture

The library separates cloud access from local control:

- **`SensioApi`** — Authenticates with the Sensio cloud and fetches device data. Used once during setup; the result can be cached.
- **`Hub`** — Connects to your local controller and sends commands. Works entirely offline using cached device data.

## Quick Start

### First-time setup (fetch device data from cloud)

```python
from sensio_lib import SensioApi

async with SensioApi(username, password) as api:
    projects = await api.login()
    project_id = next(iter(projects.values()))
    functions_data = await api.get_devices(project_id)
    # Cache functions_data for future use
```

### Local control (from cached data)

```python
from sensio_lib import Hub

async with Hub("192.168.1.100") as hub:
    await hub.connect(cached_functions_data)

    for light in hub.get_lights():
        await light.turn_on()

    for scene in hub.get_scenes():
        await scene.activate()
```

## Device Support

This library has been tested with a Sensio X1 controller. Testing is limited, so your experience may vary.

## Requirements

- Python 3.10+
- `aiohttp`

## Testing

Example script reads env params for sensitive data and does not store anything. Example for launching it and testing:

```bash
SENSIO_USERNAME="your user name / email" SENSIO_PASSWORD="your password" SENSIO_HUB_IP="your hub IP" python example.py
```

You can also optionally specify `SENSIO_ENV` to target a different cloud environment (defaults to `unity`, can also be `ha-pilot`):

```bash
SENSIO_ENV="ha-pilot" SENSIO_USERNAME="your user name / email" SENSIO_PASSWORD="your password" SENSIO_HUB_IP="your hub IP" python example.py
```