"""Tests for desktop router."""

from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from openhands.agent_server.desktop_router import DesktopUrlResponse, get_desktop_url


class TestDesktopRouter:
    """Test cases for desktop router endpoints."""

    @pytest.mark.asyncio
    async def test_get_desktop_url_service_disabled(self):
        """Test get_desktop_url when desktop service is disabled."""
        with patch(
            "openhands.agent_server.desktop_router.get_desktop_service",
            return_value=None,
        ):
            with pytest.raises(HTTPException) as exc_info:
                await get_desktop_url()

            assert exc_info.value.status_code == 503
            assert "Desktop is disabled in configuration" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_get_desktop_url_success(self):
        """Test get_desktop_url successful response."""
        mock_service = MagicMock()
        mock_service.get_vnc_url.return_value = (
            "http://localhost:8002/vnc.html?autoconnect=1&resize=remote"
        )

        with patch(
            "openhands.agent_server.desktop_router.get_desktop_service",
            return_value=mock_service,
        ):
            response = await get_desktop_url("http://localhost:8002")

            assert isinstance(response, DesktopUrlResponse)
            assert (
                response.url
                == "http://localhost:8002/vnc.html?autoconnect=1&resize=remote"
            )
            mock_service.get_vnc_url.assert_called_once_with("http://localhost:8002")

    @pytest.mark.asyncio
    async def test_get_desktop_url_default_base_url(self):
        """Test get_desktop_url with default base URL."""
        mock_service = MagicMock()
        mock_service.get_vnc_url.return_value = (
            "http://localhost:8002/vnc.html?autoconnect=1&resize=remote"
        )

        with patch(
            "openhands.agent_server.desktop_router.get_desktop_service",
            return_value=mock_service,
        ):
            response = await get_desktop_url()

            assert isinstance(response, DesktopUrlResponse)
            assert (
                response.url
                == "http://localhost:8002/vnc.html?autoconnect=1&resize=remote"
            )
            mock_service.get_vnc_url.assert_called_once_with("http://localhost:8002")

    @pytest.mark.asyncio
    async def test_get_desktop_url_service_exception(self):
        """Test get_desktop_url when service raises exception."""
        mock_service = MagicMock()
        mock_service.get_vnc_url.side_effect = Exception("VNC connection failed")

        with patch(
            "openhands.agent_server.desktop_router.get_desktop_service",
            return_value=mock_service,
        ):
            with pytest.raises(HTTPException) as exc_info:
                await get_desktop_url()

            assert exc_info.value.status_code == 500
            assert exc_info.value.detail == "Failed to get desktop URL"

    @pytest.mark.asyncio
    async def test_get_desktop_url_none_response(self):
        """Test get_desktop_url when service returns None."""
        mock_service = MagicMock()
        mock_service.get_vnc_url.return_value = None

        with patch(
            "openhands.agent_server.desktop_router.get_desktop_service",
            return_value=mock_service,
        ):
            response = await get_desktop_url()

            assert isinstance(response, DesktopUrlResponse)
            assert response.url is None


class TestDesktopUrlResponse:
    """Test cases for DesktopUrlResponse model."""

    def test_desktop_url_response_with_url(self):
        """Test DesktopUrlResponse with URL."""
        response = DesktopUrlResponse(url="http://example.com/vnc.html")
        assert response.url == "http://example.com/vnc.html"

    def test_desktop_url_response_with_none(self):
        """Test DesktopUrlResponse with None URL."""
        response = DesktopUrlResponse(url=None)
        assert response.url is None

    def test_desktop_url_response_serialization(self):
        """Test DesktopUrlResponse serialization."""
        response = DesktopUrlResponse(url="http://example.com/vnc.html")
        data = response.model_dump()
        assert data == {"url": "http://example.com/vnc.html"}

    def test_desktop_url_response_none_serialization(self):
        """Test DesktopUrlResponse serialization with None."""
        response = DesktopUrlResponse(url=None)
        data = response.model_dump()
        assert data == {"url": None}
