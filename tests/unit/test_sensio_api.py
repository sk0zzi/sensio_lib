"""Tests for the SensioApi cloud interface."""

from unittest.mock import AsyncMock, patch

import pytest

from sensio_lib.sensio_api import SensioApi
from sensio_lib.const import SensioEnvironment


@pytest.fixture
def api():
    return SensioApi("testuser", "testpass")


class TestSensioApi:
    """Tests for login, get_devices, close."""

    def test_environment_passed_to_client(self):
        """SensioApi should pass the environment parameter down to the client."""
        api = SensioApi("user", "pass", environment=SensioEnvironment.PILOT_HA)
        assert api._api_client._environment == SensioEnvironment.PILOT_HA

    @pytest.mark.asyncio
    async def test_login_returns_projects(self, api):
        """login() should authenticate and return projects."""
        with patch.object(api._api_client, "authenticate", new_callable=AsyncMock) as mock_auth, \
             patch.object(api._api_client, "get_projects", new_callable=AsyncMock, return_value={"Home": "p1"}) as mock_proj:
            result = await api.login()

            mock_auth.assert_called_once()
            mock_proj.assert_called_once()
            assert result == {"Home": "p1"}

    @pytest.mark.asyncio
    async def test_get_devices_returns_functions(self, api):
        """get_devices() should fetch and return functions data."""
        functions_data = {"functions": [{"address": 1, "subType": "light_on"}]}
        with patch.object(api._api_client, "get_functions", new_callable=AsyncMock, return_value=functions_data) as mock_func:
            result = await api.get_devices("project-123")

            mock_func.assert_called_once_with("project-123")
            assert result == functions_data

    @pytest.mark.asyncio
    async def test_close(self, api):
        """close() should close the API client."""
        with patch.object(api._api_client, "close", new_callable=AsyncMock) as mock_close:
            await api.close()

            mock_close.assert_called_once()

    @pytest.mark.asyncio
    async def test_context_manager(self):
        """SensioApi should work as an async context manager."""
        with patch.object(SensioApi, "close", new_callable=AsyncMock) as mock_close:
            async with SensioApi("user", "pass") as api:
                assert api is not None

            mock_close.assert_called_once()
