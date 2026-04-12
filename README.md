# Sensio Library

A minimal async library to control Sensio (EOPT Home) smart house systems. Designed for easy integration with Home Assistant.

It retrieves device configuration from the EOPT cloud on initial setup, then controls devices 100% locally over your LAN.

## Features (v1.0.0)

- **Local control** — All device commands sent directly to your controller on the LAN
- **Lights** — Turn individual lights and room-level lights on/off
- **Scenes** — Activate lighting scenes

## Device Support

This library has been tested with a Sensio X1 controller. Testing is limited, so your experience may vary. Device support is also very limited to only scenes and lights. There is no reading of data back from the controller only sending of commands.

## Requirements

- Python 3.10+
- `aiohttp`

## Testing

Example script reads env params for sensitive data and does not store anything. Example for lunching it and testing:

```
SENSIO_USERNAME="your user name / email" SENSIO_PASSWORD="your password" SENSIO_HUB_IP="your hub IP" python example.py
```