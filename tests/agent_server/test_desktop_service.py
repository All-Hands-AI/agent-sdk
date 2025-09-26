"""Tests for desktop service."""

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from openhands.agent_server.desktop_service import DesktopService, get_desktop_service


class TestDesktopService:
    """Test cases for DesktopService."""

    def test_desktop_service_initialization(self):
        """Test desktop service initialization."""
        service = DesktopService()
        assert service._proc is None
        assert service.novnc_port == int(os.getenv("NOVNC_PORT", "8002"))

    def test_desktop_service_custom_port(self):
        """Test desktop service with custom port."""
        with patch.dict(os.environ, {"NOVNC_PORT": "9999"}):
            service = DesktopService()
            assert service.novnc_port == 9999

    @pytest.mark.asyncio
    async def test_start_desktop_already_running(self):
        """Test starting desktop when it's already running."""
        service = DesktopService()

        with patch.object(service, "is_running", return_value=True):
            result = await service.start()
            assert result is True

    @pytest.mark.asyncio
    async def test_start_desktop_directory_creation_failure(self):
        """Test starting desktop when directory creation fails."""
        service = DesktopService()

        with (
            patch.object(service, "is_running", return_value=False),
            patch("pathlib.Path.mkdir", side_effect=Exception("Permission denied")),
        ):
            result = await service.start()
            assert result is False

    @pytest.mark.asyncio
    async def test_start_desktop_xstartup_creation_failure(self):
        """Test starting desktop when xstartup creation fails."""
        service = DesktopService()

        with (
            patch.object(service, "is_running", return_value=False),
            patch("pathlib.Path.mkdir"),
            patch("pathlib.Path.exists", return_value=False),
            patch("pathlib.Path.write_text", side_effect=Exception("Write failed")),
        ):
            result = await service.start()
            assert result is False

    @pytest.mark.asyncio
    async def test_start_desktop_vncserver_failure(self):
        """Test starting desktop when vncserver fails."""
        service = DesktopService()

        mock_result = MagicMock()
        mock_result.returncode = 1

        with (
            patch.object(service, "is_running", return_value=False),
            patch("pathlib.Path.mkdir"),
            patch("pathlib.Path.exists", return_value=True),
            patch("subprocess.run", return_value=mock_result),
        ):
            result = await service.start()
            assert result is False

    @pytest.mark.asyncio
    async def test_start_desktop_novnc_proxy_not_found(self):
        """Test starting desktop when noVNC proxy is not found."""
        service = DesktopService()

        mock_xvnc_result = MagicMock()
        mock_xvnc_result.returncode = 1  # Xvnc not running

        mock_vncserver_result = MagicMock()
        mock_vncserver_result.returncode = 0  # vncserver success

        mock_novnc_result = MagicMock()
        mock_novnc_result.returncode = 1  # noVNC not running

        def mock_exists(self):
            path_str = str(self)
            return path_str.endswith("xstartup") and not path_str.endswith(
                "novnc_proxy"
            )

        with (
            patch.object(service, "is_running", return_value=False),
            patch("pathlib.Path.mkdir"),
            patch("pathlib.Path.exists", mock_exists),
            patch(
                "subprocess.run",
                side_effect=[
                    mock_xvnc_result,
                    mock_vncserver_result,
                    mock_novnc_result,
                ],
            ),
        ):
            result = await service.start()
            assert result is False

    @pytest.mark.asyncio
    async def test_start_desktop_success_with_existing_novnc(self):
        """Test starting desktop successfully with existing noVNC."""
        service = DesktopService()

        mock_xvnc_result = MagicMock()
        mock_xvnc_result.returncode = 1  # Xvnc not running

        mock_vncserver_result = MagicMock()
        mock_vncserver_result.returncode = 0  # vncserver success

        mock_novnc_result = MagicMock()
        mock_novnc_result.returncode = 0  # noVNC already running

        with (
            patch.object(service, "is_running", return_value=True),
            patch("pathlib.Path.mkdir"),
            patch("pathlib.Path.exists", return_value=True),
            patch(
                "subprocess.run",
                side_effect=[
                    mock_xvnc_result,
                    mock_vncserver_result,
                    mock_novnc_result,
                ],
            ),
            patch("asyncio.sleep"),
        ):
            result = await service.start()
            assert result is True
            assert service._proc is None  # We didn't start noVNC ourselves

    @pytest.mark.asyncio
    async def test_start_desktop_success_with_new_novnc(self):
        """Test starting desktop successfully with new noVNC process."""
        service = DesktopService()

        mock_xvnc_result = MagicMock()
        mock_xvnc_result.returncode = 1  # Xvnc not running

        mock_vncserver_result = MagicMock()
        mock_vncserver_result.returncode = 0  # vncserver success

        mock_novnc_result = MagicMock()
        mock_novnc_result.returncode = 1  # noVNC not running

        mock_proc = MagicMock()
        mock_proc.returncode = None

        with (
            patch.object(
                service, "is_running", side_effect=[False, False, True]
            ),  # Not running initially, then running after start
            patch("pathlib.Path.mkdir"),
            patch("pathlib.Path.exists", return_value=True),
            patch(
                "subprocess.run",
                side_effect=[
                    mock_xvnc_result,
                    mock_vncserver_result,
                    mock_novnc_result,
                ],
            ),
            patch("asyncio.create_subprocess_exec", return_value=mock_proc),
            patch("asyncio.sleep"),
        ):
            result = await service.start()
            assert result is True
            assert service._proc is mock_proc

    @pytest.mark.asyncio
    async def test_start_desktop_novnc_creation_failure(self):
        """Test starting desktop when noVNC process creation fails."""
        service = DesktopService()

        mock_xvnc_result = MagicMock()
        mock_xvnc_result.returncode = 1  # Xvnc not running

        mock_vncserver_result = MagicMock()
        mock_vncserver_result.returncode = 0  # vncserver success

        mock_novnc_result = MagicMock()
        mock_novnc_result.returncode = 1  # noVNC not running

        with (
            patch.object(service, "is_running", return_value=False),
            patch("pathlib.Path.mkdir"),
            patch("pathlib.Path.exists", return_value=True),
            patch(
                "subprocess.run",
                side_effect=[
                    mock_xvnc_result,
                    mock_vncserver_result,
                    mock_novnc_result,
                ],
            ),
            patch(
                "asyncio.create_subprocess_exec",
                side_effect=Exception("Failed to start"),
            ),
        ):
            result = await service.start()
            assert result is False

    @pytest.mark.asyncio
    async def test_stop_desktop_no_process(self):
        """Test stopping desktop when no process is running."""
        service = DesktopService()
        service._proc = None

        await service.stop()  # Should not raise any exception

    @pytest.mark.asyncio
    async def test_stop_desktop_graceful(self):
        """Test stopping desktop gracefully."""
        service = DesktopService()
        mock_proc = AsyncMock()
        mock_proc.returncode = None
        service._proc = mock_proc

        await service.stop()

        mock_proc.terminate.assert_called_once()
        mock_proc.wait.assert_called_once()
        assert service._proc is None

    @pytest.mark.asyncio
    async def test_stop_desktop_timeout(self):
        """Test stopping desktop with timeout."""
        service = DesktopService()
        mock_proc = MagicMock()
        mock_proc.returncode = None

        mock_proc.terminate = MagicMock()
        mock_proc.kill = MagicMock()

        # Mock wait to raise TimeoutError on first call, then succeed on second call
        wait_calls = 0

        async def mock_wait():
            nonlocal wait_calls
            wait_calls += 1
            if wait_calls == 1:
                raise TimeoutError()
            return None

        mock_proc.wait = mock_wait
        service._proc = mock_proc

        await service.stop()

        mock_proc.terminate.assert_called_once()
        mock_proc.kill.assert_called_once()
        assert service._proc is None

    @pytest.mark.asyncio
    async def test_stop_desktop_exception(self):
        """Test stopping desktop with exception."""
        service = DesktopService()
        mock_proc = AsyncMock()
        mock_proc.returncode = None
        mock_proc.terminate.side_effect = Exception("Terminate failed")
        service._proc = mock_proc

        await service.stop()

        assert service._proc is None

    def test_is_running_with_process(self):
        """Test is_running when process is active."""
        service = DesktopService()
        mock_proc = MagicMock()
        mock_proc.returncode = None
        service._proc = mock_proc

        assert service.is_running() is True

    def test_is_running_with_dead_process(self):
        """Test is_running when process is dead."""
        service = DesktopService()
        mock_proc = MagicMock()
        mock_proc.returncode = 1
        service._proc = mock_proc

        mock_result = MagicMock()
        mock_result.returncode = 0

        with patch("subprocess.run", return_value=mock_result):
            assert service.is_running() is True

    def test_is_running_no_process_vnc_running(self):
        """Test is_running when no managed process but VNC is running."""
        service = DesktopService()
        service._proc = None

        mock_result = MagicMock()
        mock_result.returncode = 0

        with patch("subprocess.run", return_value=mock_result):
            assert service.is_running() is True

    def test_is_running_no_process_vnc_not_running(self):
        """Test is_running when no process and VNC not running."""
        service = DesktopService()
        service._proc = None

        mock_result = MagicMock()
        mock_result.returncode = 1

        with patch("subprocess.run", return_value=mock_result):
            assert service.is_running() is False

    def test_is_running_subprocess_exception(self):
        """Test is_running when subprocess raises exception."""
        service = DesktopService()
        service._proc = None

        with patch("subprocess.run", side_effect=Exception("Command failed")):
            assert service.is_running() is False

    def test_get_vnc_url_running(self):
        """Test get_vnc_url when desktop is running."""
        service = DesktopService()

        with patch.object(service, "is_running", return_value=True):
            url = service.get_vnc_url("http://example.com:8000")
            assert url == "http://example.com:8000/vnc.html?autoconnect=1&resize=remote"

    def test_get_vnc_url_not_running(self):
        """Test get_vnc_url when desktop is not running."""
        service = DesktopService()

        with patch.object(service, "is_running", return_value=False):
            url = service.get_vnc_url("http://example.com:8000")
            assert url is None

    def test_get_vnc_url_default_base(self):
        """Test get_vnc_url with default base URL."""
        service = DesktopService()

        with patch.object(service, "is_running", return_value=True):
            url = service.get_vnc_url()
            assert url == "http://localhost:8003/vnc.html?autoconnect=1&resize=remote"


class TestGetDesktopService:
    """Test cases for get_desktop_service function."""

    def setup_method(self):
        """Reset global state before each test."""
        import openhands.agent_server.desktop_service

        openhands.agent_server.desktop_service._desktop_service = None

    def test_get_desktop_service_vnc_enabled(self):
        """Test getting desktop service when VNC is enabled."""
        mock_config = MagicMock()
        mock_config.enable_vnc = True

        with patch(
            "openhands.agent_server.config.get_default_config", return_value=mock_config
        ):
            service = get_desktop_service()
            assert service is not None
            assert isinstance(service, DesktopService)

    def test_get_desktop_service_vnc_disabled(self):
        """Test getting desktop service when VNC is disabled."""
        mock_config = MagicMock()
        mock_config.enable_vnc = False

        with patch(
            "openhands.agent_server.config.get_default_config", return_value=mock_config
        ):
            service = get_desktop_service()
            assert service is None

    def test_get_desktop_service_singleton(self):
        """Test that get_desktop_service returns the same instance."""
        mock_config = MagicMock()
        mock_config.enable_vnc = True

        with patch(
            "openhands.agent_server.config.get_default_config", return_value=mock_config
        ):
            service1 = get_desktop_service()
            service2 = get_desktop_service()
            assert service1 is service2

    def test_get_desktop_service_reset_global(self):
        """Test resetting the global desktop service."""
        mock_config = MagicMock()
        mock_config.enable_vnc = True

        with patch(
            "openhands.agent_server.config.get_default_config", return_value=mock_config
        ):
            service = get_desktop_service()
            assert service is not None
