# Sensio Library

A small library designed to control the Sensio smart house controller. This library was developed by reverse engineering the communication between the Sensio smart home app and the controller. It retrieves all device information from the Sensio cloud, but after the initial setup, all devices can be controlled 100% locally from your LAN.

More features could probably be implemented by additional reverse engineering.

## Features (v0.1.0)

- **Login to Sensio Cloud**
  - Select between multiple projects
  - Get a list of all light devices
- **Basic Light Control**
  - Turn lights on/off (Note: no actual state of lights is implemented)

## Device Support

This library has been tested with a Sensio X1 controller. Testing is limited, so your experience may vary.