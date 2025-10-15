"""Test DockerWorkspace import and basic functionality."""


def test_docker_workspace_import():
    """Test that DockerWorkspace can be imported from the new package."""
    from openhands_workspace import DockerWorkspace

    assert DockerWorkspace is not None
    assert hasattr(DockerWorkspace, "__init__")


def test_docker_workspace_inheritance():
    """Test that DockerWorkspace inherits from RemoteWorkspace."""
    from openhands_sdk.workspace import RemoteWorkspace
    from openhands_workspace import DockerWorkspace

    assert issubclass(DockerWorkspace, RemoteWorkspace)
