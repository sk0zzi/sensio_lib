import pytest
import requests
from unittest.mock import patch, Mock
from sensio_lib.hub import Hub

# Mock constants
SENSIO_PROJECTS_URL = "https://example.com/projects"

@pytest.fixture
def hub():
    with patch('sensio_lib.hub.SENSIO_PROJECTS_URL', SENSIO_PROJECTS_URL):
        with patch.object(Hub, '_get_auth_token', return_value="mocked_token"):
            with patch.object(Hub, '_get_projects', return_value={}):
                return Hub("1.1.1.1", "username", "password")

def test_get_projects_success(hub):
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        'projects': [
            {'name': 'Project1', 'projectId': '123'},
            {'name': 'Project2', 'projectId': '456'}
        ]
    }

    with patch('requests.get', return_value=mock_response):
        projects = hub._get_projects()
        assert projects == {'Project1': '123', 'Project2': '456'}

def test_get_auth_token_success(hub):
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        'tokenId': 'mocked_token_id',
        'tokenSecret': 'mocked_token_secret'
    }

    with patch('requests.post', return_value=mock_response):
        token = hub._get_auth_token()
        assert token == "bW9ja2VkX3Rva2VuX2lkOm1vY2tlZF90b2tlbl9zZWNyZXQ="

def test_get_projects_no_token(hub):
    hub.token = None
    with pytest.raises(Exception, match="Token not set"):
        hub._get_projects()

def test_get_projects_failure(hub):
    mock_response = Mock()
    mock_response.status_code = 500

    with patch('requests.get', return_value=mock_response):
        with pytest.raises(Exception, match="Failed to retrieve projects"):
            hub._get_projects()

def test_create_function_list(hub):
    mock_entity_json = {
        'functions': [
            {'name': 'light_1_OFF', 'subType': 'light_off', 'address': '0'},
            {'name': 'light_1_ON', 'subType': 'light_on', 'address': '1'},
            {'name': 'light_2_OFF', 'subType': 'light_off', 'address': '2'},
            {'name': 'light_2_ON', 'subType': 'light_on', 'address': '3'},
        ]
    }

    light_list = hub._create_function_list(mock_entity_json)
    assert light_list == [
        { 'switch': {'name': 'light_1', 'command_on': '1', 'command_off': '0'}},
        { 'switch': {'name': 'light_2', 'command_on': '3', 'command_off': '2'}}
    ]
        