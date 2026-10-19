"""Async example for controlling Sensio smart house devices."""

import asyncio
import logging
import os

from sensio_lib import (
    Dimmer,
    Hub,
    Light,
    SensioApi,
    SensioAuthenticationError,
    SensioConnectionError,
    SensioEnvironment,
)

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def on_state_change(device):
    """Called by the hub when a device state changes via RSN."""
    logger.info("State changed: %s", device)


def _list_devices(lights: list[Light], dimmers: list[Dimmer]) -> None:
    print("\n--- Lights ---")
    for i, light in enumerate(lights):
        print(f"  [{i}] {light.name}  ({light.state.value})")
    print("\n--- Dimmers ---")
    for i, dimmer in enumerate(dimmers):
        brightness = (
            f"{dimmer.brightness}%" if dimmer.brightness is not None else "unknown"
        )
        print(f"  [d{i}] {dimmer.name}  ({dimmer.state.value}, brightness={brightness})")
    print()


async def _control_light(light: Light) -> None:
    action = await asyncio.to_thread(
        input,
        f"  Selected: {light.name} (state: {light.state.value})\n"
        "  [1] Turn ON  [2] Turn OFF  [Enter] Cancel\n  > ",
    )
    if action == "1":
        logger.info("Turning on: %s", light.name)
        await light.turn_on()
    elif action == "2":
        logger.info("Turning off: %s", light.name)
        await light.turn_off()


async def _control_dimmer(dimmer: Dimmer) -> None:
    brightness_str = (
        f"{dimmer.brightness}%" if dimmer.brightness is not None else "unknown"
    )
    action = await asyncio.to_thread(
        input,
        f"  Selected: {dimmer.name} (state: {dimmer.state.value},"
        f" brightness={brightness_str})\n"
        "  [1] Turn ON  [2] Turn OFF  [0-100] Set brightness  [Enter] Cancel\n  > ",
    )
    if action == "1":
        logger.info("Turning on: %s", dimmer.name)
        await dimmer.turn_on()
    elif action == "2":
        logger.info("Turning off: %s", dimmer.name)
        await dimmer.turn_off()
    elif action.isdigit() and 0 <= int(action) <= 100:
        level = int(action)
        logger.info("Setting %s to %d%%", dimmer.name, level)
        await dimmer.set_brightness(level)
    elif action != "":
        logger.error("Invalid input: %r", action)


async def main():
    # Set these environment variables before running:
    #   export SENSIO_HUB_IP="192.168.x.x"
    #   export SENSIO_USERNAME="your_username"
    #   export SENSIO_PASSWORD="your_password"
    #   export SENSIO_ENV="unity"  # or "ha-pilot"
    hub_address = os.environ["SENSIO_HUB_IP"]
    username = os.environ["SENSIO_USERNAME"]
    password = os.environ["SENSIO_PASSWORD"]
    env_str = os.environ.get("SENSIO_ENV", "unity")

    try:
        environment = SensioEnvironment(env_str)
    except ValueError:
        logger.warning("Invalid SENSIO_ENV '%s', defaulting to unity", env_str)
        environment = SensioEnvironment.UNITY

    try:
        # Step 1: Fetch device data from the Sensio cloud
        async with SensioApi(username, password, environment) as api:
            projects = await api.login()
            logger.info("Available projects: %s", list(projects.keys()))

            if not projects:
                logger.error("No projects found")
                return

            project_name, project_id = next(iter(projects.items()))
            logger.info("Using project: %s", project_name)
            functions_data = await api.get_devices(project_id)

        # Step 2: Connect to the local controller with cached data
        async with Hub(hub_address) as hub:
            await hub.connect(functions_data)

            identity = hub.hub_identity
            if identity:
                logger.info(
                    "Hub: serial=%s, firmware=%s, ip=%s",
                    identity.serial,
                    identity.firmware,
                    identity.ip,
                )

            hub.set_state_callback(on_state_change)

            lights = hub.get_lights()
            dimmers = hub.get_dimmers()
            scenes = hub.get_scenes()

            logger.info(
                "Discovered: %d lights, %d dimmers, %d scenes",
                len(lights), len(dimmers), len(scenes),
            )
            _list_devices(lights, dimmers)

            # Interactive control loop
            # Lights: plain number  (0, 1, 2, ...)
            # Dimmers: d-prefixed   (d0, d1, d2, ...)
            while True:
                choice = await asyncio.to_thread(
                    input,
                    "Select device:  [0-N] light  [d0-dN] dimmer"
                    "  [l] list  [q] quit\n> ",
                )
                choice = choice.strip().lower()

                if choice == "q":
                    break

                if choice == "l":
                    _list_devices(lights, dimmers)
                    continue

                if choice.startswith("d") and choice[1:].isdigit():
                    idx = int(choice[1:])
                    if idx >= len(dimmers):
                        logger.error("No dimmer at index %d (have %d)", idx, len(dimmers))
                        continue
                    await _control_dimmer(dimmers[idx])
                    continue

                if choice.isdigit():
                    idx = int(choice)
                    if idx >= len(lights):
                        logger.error("No light at index %d (have %d)", idx, len(lights))
                        continue
                    await _control_light(lights[idx])
                    continue

                logger.error("Unknown input %r — type 'l' to list devices", choice)

    except SensioAuthenticationError as err:
        logger.error("Authentication failed: %s", err)
    except SensioConnectionError as err:
        logger.error("Connection error: %s", err)


if __name__ == "__main__":
    asyncio.run(main())