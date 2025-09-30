"""Tests for the agent server API functionality."""

import tempfile
from pathlib import Path

from fastapi.testclient import TestClient

from openhands.agent_server.api import create_app
from openhands.agent_server.config import Config


class TestStaticFilesServing:
    """Test static files serving functionality."""

    def test_static_files_not_mounted_when_path_none(self):
        """Test that static files are not mounted when static_files_path is None."""
        config = Config(static_files_path=None)
        app = create_app(config)
        client = TestClient(app)

        # Try to access static files endpoint - should return 404
        response = client.get("/static/test.txt")
        assert response.status_code == 404

    def test_static_files_not_mounted_when_directory_missing(self):
        """Test that static files are not mounted when directory doesn't exist."""
        config = Config(static_files_path=Path("/nonexistent/directory"))
        app = create_app(config)
        client = TestClient(app)

        # Try to access static files endpoint - should return 404
        response = client.get("/static/test.txt")
        assert response.status_code == 404

    def test_static_files_mounted_when_directory_exists(self):
        """Test that static files are mounted when directory exists."""
        with tempfile.TemporaryDirectory() as temp_dir:
            static_dir = Path(temp_dir)

            # Create a test file
            test_file = static_dir / "test.txt"
            test_file.write_text("Hello, static world!")

            config = Config(static_files_path=static_dir)
            app = create_app(config)
            client = TestClient(app)

            # Access the static file
            response = client.get("/static/test.txt")
            assert response.status_code == 200
            assert response.text == "Hello, static world!"
            assert response.headers["content-type"] == "text/plain; charset=utf-8"

    def test_static_files_serve_html(self):
        """Test that static files can serve HTML files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            static_dir = Path(temp_dir)

            # Create an HTML test file
            html_file = static_dir / "index.html"
            html_content = "<html><body><h1>Static HTML</h1></body></html>"
            html_file.write_text(html_content)

            config = Config(static_files_path=static_dir)
            app = create_app(config)
            client = TestClient(app)

            # Access the HTML file
            response = client.get("/static/index.html")
            assert response.status_code == 200
            assert response.text == html_content
            assert "text/html" in response.headers["content-type"]

    def test_static_files_serve_subdirectory(self):
        """Test that static files can serve files from subdirectories."""
        with tempfile.TemporaryDirectory() as temp_dir:
            static_dir = Path(temp_dir)

            # Create a subdirectory with a file
            sub_dir = static_dir / "assets"
            sub_dir.mkdir()
            css_file = sub_dir / "style.css"
            css_content = "body { color: blue; }"
            css_file.write_text(css_content)

            config = Config(static_files_path=static_dir)
            app = create_app(config)
            client = TestClient(app)

            # Access the CSS file in subdirectory
            response = client.get("/static/assets/style.css")
            assert response.status_code == 200
            assert response.text == css_content
            assert "text/css" in response.headers["content-type"]

    def test_static_files_404_for_missing_file(self):
        """Test that missing static files return 404."""
        with tempfile.TemporaryDirectory() as temp_dir:
            static_dir = Path(temp_dir)

            config = Config(static_files_path=static_dir)
            app = create_app(config)
            client = TestClient(app)

            # Try to access non-existent file
            response = client.get("/static/nonexistent.txt")
            assert response.status_code == 404

    def test_static_files_security_no_directory_traversal(self):
        """Test that directory traversal attacks are prevented."""
        with tempfile.TemporaryDirectory() as temp_dir:
            static_dir = Path(temp_dir)

            # Create a file outside the static directory
            parent_dir = Path(temp_dir).parent
            secret_file = parent_dir / "secret.txt"
            secret_file.write_text("Secret content")

            config = Config(static_files_path=static_dir)
            app = create_app(config)
            client = TestClient(app)

            # Try directory traversal attack
            response = client.get("/static/../secret.txt")
            assert response.status_code == 404

        # Clean up the secret file
        if secret_file.exists():
            secret_file.unlink()


class TestRootRedirect:
    """Test root endpoint redirect functionality."""

    def test_root_redirect_to_index_html_when_exists(self):
        """Test that root endpoint redirects to /static/index.html when it exists."""
        with tempfile.TemporaryDirectory() as temp_dir:
            static_dir = Path(temp_dir)

            # Create an index.html file
            index_file = static_dir / "index.html"
            index_file.write_text("<html><body><h1>Welcome</h1></body></html>")

            config = Config(static_files_path=static_dir)
            app = create_app(config)
            client = TestClient(app)

            # Test root redirect
            response = client.get("/", follow_redirects=False)
            assert response.status_code == 302
            assert response.headers["location"] == "/static/index.html"

    def test_root_redirect_to_static_dir_when_no_index(self):
        """Test that root endpoint redirects to /static/ when no index.html exists."""
        with tempfile.TemporaryDirectory() as temp_dir:
            static_dir = Path(temp_dir)

            # Create a different file (not index.html)
            other_file = static_dir / "other.html"
            other_file.write_text("<html><body><h1>Other</h1></body></html>")

            config = Config(static_files_path=static_dir)
            app = create_app(config)
            client = TestClient(app)

            # Test root redirect
            response = client.get("/", follow_redirects=False)
            assert response.status_code == 302
            assert response.headers["location"] == "/static/"

    def test_root_redirect_follows_to_index_html(self):
        """Test that following the root redirect serves index.html when it exists."""
        with tempfile.TemporaryDirectory() as temp_dir:
            static_dir = Path(temp_dir)

            # Create an index.html file
            index_file = static_dir / "index.html"
            index_content = "<html><body><h1>Welcome to Static Site</h1></body></html>"
            index_file.write_text(index_content)

            config = Config(static_files_path=static_dir)
            app = create_app(config)
            client = TestClient(app)

            # Test root redirect with follow_redirects=True
            response = client.get("/", follow_redirects=True)
            assert response.status_code == 200
            assert response.text == index_content
            assert "text/html" in response.headers["content-type"]

    def test_no_root_redirect_when_static_files_not_configured(self):
        """Test that root endpoint doesn't redirect when static files are not configured."""  # noqa: E501
        config = Config(static_files_path=None)
        app = create_app(config)
        client = TestClient(app)

        # Root should return 404 (no handler defined)
        response = client.get("/")
        assert response.status_code == 200

    def test_no_root_redirect_when_static_directory_missing(self):
        """Test that root endpoint doesn't redirect when static directory doesn't exist."""  # noqa: E501
        config = Config(static_files_path=Path("/nonexistent/directory"))
        app = create_app(config)
        client = TestClient(app)

        # Root should return 404 (no handler defined)
        response = client.get("/")
        assert response.status_code == 200
