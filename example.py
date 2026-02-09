"""Async example for controlling Sensio smart house devices."""

import asyncio
import logging
import os

from sensio_lib import Hub, SensioAuthenticationError, SensioConnectionError

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def main():
    # Set these environment variables before running:
    #   export SENSIO_USERNAME="your_username"
    #   export SENSIO_PASSWORD="your_password"
    #   export SENSIO_HUB_IP="192.168.x.x"
    hub_address = os.environ["SENSIO_HUB_IP"]
    username = os.environ["SENSIO_USERNAME"]
    password = os.environ["SENSIO_PASSWORD"]

    try:
        async with Hub(hub_address, username, password) as hub:
            # Authenticate with Sensio cloud
            projects = await hub.login()
            logger.info("Available projects: %s", list(projects.keys()))

            if not projects:
                logger.error("No projects found")
                return

            # Select the first project
            project_name, project_id = next(iter(projects.items()))
            logger.info("Using project: %s", project_name)
            await hub.set_project(project_id)

            # List all lights
            lights = hub.get_lights()
            for i, light in enumerate(lights):
                logger.info("Light %d: %s", i, light)

            # List all scenes
            scenes = hub.get_scenes()
            for i, scene in enumerate(scenes):
                logger.info("Scene %d: %s", i, scene)

            # Interactive light toggle
            while True:
                choice = input("Enter light number to toggle (or 'q' to quit): ")
                if choice.lower() == "q":
                    break
                if choice.isdigit() and int(choice) < len(lights):
                    light = lights[int(choice)]
                    if light.is_on:
                        logger.info("Turning off: %s", light.name)
                        await light.turn_off()
                    else:
                        logger.info("Turning on: %s", light.name)
                        await light.turn_on()
                else:
                    logger.error("Invalid selection")

    except SensioAuthenticationError as err:
        logger.error("Authentication failed: %s", err)
    except SensioConnectionError as err:
        logger.error("Connection error: %s", err)


if __name__ == "__main__":
    asyncio.run(main())