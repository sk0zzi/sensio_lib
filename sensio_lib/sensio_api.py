"""Public cloud API for the Sensio smart house system."""

from __future__ import annotations

from sensio_lib.api_client import SensioApiClient
from sensio_lib.const import SensioEnvironment


class SensioApi:
    """High-level interface for Sensio cloud authentication and device discovery.

    Use this to authenticate, list projects, and fetch device configuration.
    The returned functions data can be cached and passed to Hub.connect().
    """

    def __init__(self, username: str, password: str, environment: SensioEnvironment = SensioEnvironment.UNITY) -> None:
        self._api_client = SensioApiClient(username, password, environment)

    async def login(self) -> dict[str, str]:
        """Authenticate with the Sensio cloud and return available projects.

        Returns:
            Dictionary of {project_name: project_id}.
        """
        await self._api_client.authenticate()
        return await self._api_client.get_projects()

    async def get_devices(self, project_id: str) -> dict:
        """Fetch device functions data for a project.

        The returned dict can be cached and later passed to Hub.connect()
        to set up local device control without cloud access.

        Returns:
            Functions JSON dict as returned by the Sensio API.
        """
        return await self._api_client.get_functions(project_id)

    async def close(self) -> None:
        """Close the HTTP session."""
        await self._api_client.close()

    async def __aenter__(self) -> SensioApi:
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.close()
