from enum import StrEnum

SENSIO_AGENT_REQUEST = {
  "DeviceName": "sdk_gphone_x86",
  "DeviceId": "97e2cd6e-002d-4cfe-a596-5eb7a34c7582",
  "DeviceOsVersion": "11 (sdk_gphone_x86-userdebug 11 RSR1.210722.013.A2 10067904 dev-keys)",
  "DeviceType": "Android",
  "ClientType": "SensioHaPanelApp",
  "ClientVersion": "6.12.2 (320)"
}

# URLS
# Sensio (Unity)
SENSIO_BASE_URL = 'https://unity.eopthome.no/api/v1'
SENSIO_TOKEN_URL = 'https://unity.eopthome.no/api/v1/tokens'
SENSIO_PROJECTS_URL = 'https://unity.eopthome.no/api/v1/users/self/projects?include=controllers&installerProjectsOnly=false&siteIdentifier=self'

# Sensio HA Pilot
SENSIO_HA_PILOT_BASE_URL = 'https://ha-pilot.eopthome.no/api/v1'
SENSIO_HA_PILOT_TOKEN_URL = 'https://ha-pilot.eopthome.no/api/v1/tokens'
SENSIO_HA_PILOT_PROJECTS_URL = 'https://ha-pilot.eopthome.no/api/v1/users/self/projects?include=controllers&installerProjectsOnly=false&siteIdentifier=self'

# Hex
COMMAND_PREFIX = '\x01'
COMMAND_POSTFIX = '\x02'

class SensioEnvironment(StrEnum):
    UNITY = "unity"
    PILOT_HA = "pilot-ha"