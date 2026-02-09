"""Tests for the SensioApiClient."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from sensio_lib.api_client import SensioApiClient
from sensio_lib.exceptions import SensioAuthenticationError, SensioException


@pytest.fixture
def client():
    return SensioApiClient("testuser", "testpass")


class TestAuthenticate:
    """Tests for API authentication."""

    @pytest.mark.asyncio
    async def test_authenticate_success(self, client):
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={
            "tokenId": "tid",
            "tokenSecret": "tsecret",
        })
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=False)

        mock_session = AsyncMock()
        mock_session.post = MagicMock(return_value=mock_response)
        mock_session.closed = False

        with patch.object(client, "_get_session", return_value=mock_session):
            await client.authenticate()

        assert client._token is not None

    @pytest.mark.asyncio
    async def test_authenticate_failure(self, client):
        mock_response = AsyncMock()
        mock_response.status = 401
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=False)

        mock_session = AsyncMock()
        mock_session.post = MagicMock(return_value=mock_response)
        mock_session.closed = False

        with patch.object(client, "_get_session", return_value=mock_session):
            with pytest.raises(SensioAuthenticationError):
                await client.authenticate()


class TestGetProjects:
    """Tests for project retrieval."""

    @pytest.mark.asyncio
    async def test_get_projects_not_authenticated(self, client):
        with pytest.raises(SensioException, match="Not authenticated"):
            await client.get_projects()

    @pytest.mark.asyncio
    async def test_close(self, client):
        mock_session = AsyncMock()
        mock_session.closed = False
        client._session = mock_session

        await client.close()

        mock_session.close.assert_called_once()
