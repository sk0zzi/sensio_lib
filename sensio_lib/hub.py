from sensio_lib.const import SENSIO_AGENT_REQUEST, SENSIO_TOKEN_URL, SENSIO_PROJECTS_URL, SENSIO_BASE_URL
from sensio_lib.light import Light
import requests
import logging
import base64

logger = logging.getLogger(__name__)

class Hub:
    def __init__(self, server_address: str, username: str, password: str):
        self.username = username
        self.password = password
        self.server_address = server_address      

    def login(self) -> list:
        ''' Authenticate with the Sensio API and retrieve a list of projects '''

        self.token = self._get_auth_token()
        return self._get_projects()
    
    def get_lights(self, project_id) -> list:
        ''' Retrieve a list of lights for the specified project '''

        entities_url = f'{SENSIO_BASE_URL}/projects/{project_id}/functions'
        entities_response = requests.get(entities_url, headers={'Authorization': f'Token {self.token}'})
        if entities_response.status_code != 200:
            raise Exception("Failed to retrieve entities")
        
        logger.debug(entities_response.json())
        
        switches = self._create_function_list(entities_response.json())
        return [Light(switch['switch']['name'], switch['switch']['command_on'], switch['switch']['command_off'], self.server_address) for switch in switches]
        
        
    def _get_auth_token(self):
        response = requests.post(SENSIO_TOKEN_URL, auth=(self.username, self.password), json=SENSIO_AGENT_REQUEST, headers={"Content-Type": "application/json"})
        if response.status_code != 200:
            raise Exception("Failed to retrieve token")
        
        token_str = f'{response.json()["tokenId"]}:{response.json()["tokenSecret"]}'
        token_bytes = token_str.encode('utf-8')
        return base64.b64encode(token_bytes).decode('utf-8')
        
    def _get_projects(self):
        if not self.token:
            raise Exception("Token not set")

        # Get a list of projects
        project_response = requests.get(SENSIO_PROJECTS_URL, headers={'Authorization': f'Token {self.token}'})
        if project_response.status_code != 200:
            raise Exception("Failed to retrieve projects")
        
        # We want to populate projects with the project ID and project name for each project
        return {project['name']: project['projectId'] for project in project_response.json()['projects']}
    
    
    def _create_function_list(self, entity_json) -> list:
        ''' Create a list of functions from the entity data. This is.....ugly.'''
        
        switch_info = []
        intermediate_switches = {}

        for switch in entity_json['functions']:
            name = switch['name']
            sub_type = switch['subType']
            # Strip postfix to get the base name
            base_name = name.rsplit('_', 1)[0]
            # Determine command based on postfix
            if sub_type in ['light_on', 'light_off', 'LightOffRoom', 'LightOnRoom']:
                if base_name not in intermediate_switches:
                    intermediate_switches[base_name] = {
                        'name': base_name,
                        'command_on': '',
                        'command_off': ''
                    }

                if name.endswith('_OFF'):
                    intermediate_switches[base_name]['command_off'] = switch["address"]
                elif name.endswith('_ON'):
                    intermediate_switches[base_name]['command_on'] = switch["address"]

                if intermediate_switches[base_name]['command_on'] and intermediate_switches[base_name]['command_off']:
                    switch_info.append({'switch': intermediate_switches.pop(base_name)})
        
        return switch_info