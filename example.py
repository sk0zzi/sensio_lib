from sensio_lib import Light
from sensio_lib.light_state import LightState
from sensio_lib.hub import Hub
import logging

# Configure the root logger
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

def main():
    logger.info("Starting Sensio integration")

    # Configure the system. Replace the IP address with the IP address of your Sensio hub on your LAN. 
    # Replace SENSIO_USERNAME and SENSIO_PASSWORD with your Sensio credentials (same username and password you use to log in to the Sensio app)
    hub_adress = '192.168.xx.xx'
    username = 'SENSIO_USERNAME'
    password = 'SENSIO_PASSWORD'
    hub = Hub(hub_adress, username, password)

    # Login to Sensio cloud
    hub.login()

    # Retrieve all projects
    if not hub.projects or len(hub.projects) == 0:
        logger.error("No projects found")
        return
    else:
        logger.info(hub.projects)

    # Set the first project as the active project. Note: If you have multiple projects, you can select the project you want to control instead by using hub.projects['my_project_name']. 
    # All available projects should be listed by the log command above when the script is run
    project = hub.projects.popitem()[1]

    # By setting the project in the hub the hub will add all lights to the hub.lights list
    hub.set_project(project)

    [logger.info(f'Light {i}: {light}') for i, light in enumerate(hub.lights)]
    while True:
        light = input("Enter light number: ")
        if light.isdigit():
            light = int(light)
            if light < len(hub.lights):
                if hub.lights[light].get_light_state() == LightState.ON or hub.lights[light].get_light_state() == LightState.UNKNOWN:
                    logger.info(f'Light state is {hub.lights[light].get_light_state()}, turning off')
                    hub.lights[light].turn_off()
                else:
                    logger.info(f'Light state is {hub.lights[light].get_light_state()}, turning on')
                    hub.lights[light].turn_on()
            else:
                logger.error('Invalid light number to toggle')

if __name__ == "__main__":
    main()