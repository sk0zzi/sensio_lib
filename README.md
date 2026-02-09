# Sensio Library

A minimal async library to control Sensio smart house systems. Designed for easy integration with Home Assistant.

This library was developed by reverse engineering the communication between the Sensio app and the controller. It retrieves device configuration from the Sensio cloud on initial setup, then controls devices 100% locally over your LAN.

## Features (v1.5.0)

- **Async/await** — Built for Home Assistant and asyncio applications
- **Cloud authentication** — Login to Sensio cloud to discover devices
- **Local control** — All device commands sent directly to your controller on the LAN
- **Lights** — Turn individual lights and room-level lights on/off
- **Scenes** — Activate lighting scenes

## Quick Start

```python
import asyncio
from sensio_lib import Hub

async def main():
    async with Hub("192.168.1.100", "username", "password") as hub:
        # Authenticate and discover devices
        projects = await hub.login()
        await hub.set_project(projects["My Home"])

        # Control lights
        lights = hub.get_lights()
        await lights[0].turn_on()

        # Activate scenes
        scenes = hub.get_scenes()
        await scenes[0].activate()

asyncio.run(main())
```

## Device Support

This library has been tested with a Sensio X1 controller. Testing is limited, so your experience may vary.

## Requirements

- Python 3.10+
- `aiohttp`