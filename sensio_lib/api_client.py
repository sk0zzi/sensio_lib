"""Async client for the Sensio cloud API."""

import base64
import logging

import aiohttp

from sensio_lib.const import (
    SENSIO_AGENT_REQUEST,
    SENSIO_BASE_URL,
    SENSIO_PROJECTS_URL,
    SENSIO_TOKEN_URL,
    SENSIO_HA_PILOT_BASE_URL,
    SENSIO_HA_PILOT_PROJECTS_URL,
    SENSIO_HA_PILOT_TOKEN_URL,
    SensioEnvironment,
)
from sensio_lib.exceptions import SensioAuthenticationError, SensioException

logger = logging.getLogger(__name__)


class SensioApiClient:
    """Handles authentication and data retrieval from the Sensio cloud API."""

    def __init__(self, username: str, password: str, environment: SensioEnvironment = SensioEnvironment.UNITY) -> None:
        self._username = username
        self._password = password
        self._environment = environment

        if self._environment == SensioEnvironment.PILOT_HA:
            self._base_url = SENSIO_HA_PILOT_BASE_URL
            self._token_url = SENSIO_HA_PILOT_TOKEN_URL
            self._projects_url = SENSIO_HA_PILOT_PROJECTS_URL
        else:
            self._base_url = SENSIO_BASE_URL
            self._token_url = SENSIO_TOKEN_URL
            self._projects_url = SENSIO_PROJECTS_URL

        self._token: str | None = None
        self._session: aiohttp.ClientSession | None = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def authenticate(self) -> None:
        """Authenticate with the Sensio API and store the token."""
        session = await self._get_session()
        auth = aiohttp.BasicAuth(self._username, self._password)

        try:
            async with session.post(
                self._token_url,
                auth=auth,
                json=SENSIO_AGENT_REQUEST,
                headers={"Content-Type": "application/json"},
            ) as response:
                if response.status != 200:
                    raise SensioAuthenticationError(
                        f"Authentication failed with status {response.status}"
                    )
                data = await response.json()
                token_str = f'{data["tokenId"]}:{data["tokenSecret"]}'
                self._token = base64.b64encode(token_str.encode("utf-8")).decode(
                    "utf-8"
                )
        except aiohttp.ClientError as err:
            raise SensioAuthenticationError(
                f"Failed to connect to Sensio API: {err}"
            ) from err

    async def get_projects(self) -> dict[str, str]:
        """Retrieve available projects. Returns {name: project_id}."""
        if not self._token:
            raise SensioException("Not authenticated. Call authenticate() first.")

        session = await self._get_session()

        try:
            async with session.get(
                self._projects_url,
                headers={"Authorization": f"Token {self._token}"},
            ) as response:
                if response.status != 200:
                    raise SensioException(
                        f"Failed to retrieve projects (status {response.status})"
                    )
                data = await response.json()
                return {
                    project["name"]: project["projectId"]
                    for project in data["projects"]
                }
        except aiohttp.ClientError as err:
            raise SensioException(f"Failed to retrieve projects: {err}") from err

    async def get_functions(self, project_id: str) -> dict:
        """Retrieve the functions JSON for a project."""
        if not self._token:
            raise SensioException("Not authenticated. Call authenticate() first.")

        session = await self._get_session()
        url = f"{self._base_url}/projects/{project_id}/functions"

        try:
            async with session.get(
                url,
                headers={"Authorization": f"Token {self._token}"},
            ) as response:
                if response.status != 200:
                    raise SensioException(
                        f"Failed to retrieve functions (status {response.status})"
                    )
                return await response.json()
        except aiohttp.ClientError as err:
            raise SensioException(f"Failed to retrieve functions: {err}") from err

    async def close(self) -> None:
        """Close the HTTP session."""
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None
