#!/usr/bin/env python3
"""
Simple Docker build helper for agent-server images.

- Targets: binary | binary-minimal | source | source-minimal
- Multi-tagging via CUSTOM_TAGS (comma-separated)
- Versioned tag includes primary custom tag: v{SDK}_{BASE_SLUG}
- Branch-scoped cache keys
- CI (push) vs local (load) behavior
- sdist-based builds: Uses `uv build` to create clean build contexts
"""

import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, field_validator

VALID_TARGETS = {"binary", "binary-minimal", "source", "source-minimal"}

TargetType = Literal["binary", "binary-minimal", "source", "source-minimal"]
PlatformType = Literal["linux/amd64", "linux/arm64"]


def _run(cmd: list[str], cwd: str | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=cwd, text=True, capture_output=True, check=True)


def _base_slug(image: str) -> str:
    return image.replace("/", "_s_").replace(":", "_tag_")

def _sanitize_branch(ref: str) -> str:
    ref = re.sub(r"^refs/heads/", "", ref or "unknown")
    return re.sub(r"[^a-zA-Z0-9.-]+", "-", ref).lower()

def _sdk_version() -> str:
    from importlib.metadata import version
    return version("openhands-sdk")


def _git_info() -> tuple[str, str, str]:
    git_sha = os.environ.get("GITHUB_SHA")
    if not git_sha:
        try:
            git_sha = _run(["git", "rev-parse", "--verify", "HEAD"]).stdout.strip()
        except subprocess.CalledProcessError:
            git_sha = "unknown"
    short_sha = git_sha[:7] if git_sha != "unknown" else "unknown"

    git_ref = os.environ.get("GITHUB_REF")
    if not git_ref:
        try:
            git_ref = _run(["git", "symbolic-ref", "-q", "--short", "HEAD"]).stdout.strip()
        except subprocess.CalledProcessError:
            git_ref = "unknown"
    return git_ref, git_sha, short_sha

GIT_REF, GIT_SHA, SHORT_SHA = _git_info()
SDK_VERSION = _sdk_version()

class BuildOptions(BaseModel):
    base_image: str = Field(
        default="nikolaik/python-nodejs:python3.12-nodejs22",
        description="Base image name.",
    )
    dockerfile: str = Field(
        description="Path to the Dockerfile."
    )
    context_dir: str = Field(
        description="Path to the build context directory."
    )
    custom_tags: str = Field(
        default="",
        description="Comma-separated list of custom tags.",
    )
    image: str = Field(
        default="ghcr.io/all-hands-ai/agent-server",
        description="Target image name.",
    )
    target: TargetType = Field(
        default="binary",
        description="Build target.",
    )
    platforms: list[PlatformType] = Field(
        default=["linux/amd64", "linux/arm64"],
        description="List of target platforms.",
    )
    push: bool | None = Field(default=None)  # None => auto: push in CI, load locally

    @field_validator("target")
    @classmethod
    def _valid_target(cls, v: str) -> str:
        if v not in VALID_TARGETS:
            raise ValueError(f"target must be one of {sorted(VALID_TARGETS)}")
        return v

    @property
    def custom_tag_list(self) -> list[str]:
        return [t.strip() for t in self.custom_tags.split(",") if t.strip()]

    @property
    def base_image_slug(self) -> str:
        return _base_slug(self.base_image)

    @property
    def is_dev(self) -> bool:
        return self.target in ("source", "source-minimal")

    @property
    def versioned_tag(self) -> str:
        """Versioned tag including primary custom tag."""
        return f"v{SDK_VERSION}_{self.base_image_slug}"

    @property
    def cache_tags(self) -> tuple[str, str]:
        """Cache tags based on primary custom tag.
        
        It returns a tuple of (full cache tag, base cache tag).
        """
        base = f"buildcache-{self.target}-{self.base_image_slug}"
        if GIT_REF in ("main", "refs/heads/main"):
            return f"{base}-main", base
        elif GIT_REF != "unknown":
            return f"{base}-{_sanitize_branch(GIT_REF)}", base
        else:
            return base, base

    @property
    def all_tags(self) -> list[str]:
        """Compute all tags to apply to the built image."""
        tags: list[str] = []
        # Per-sha tags
        for t in self.custom_tag_list:
            tags.append(f"{self.image}:{SHORT_SHA}-{t}")
        # Git ref tags
        if GIT_REF in ("main", "refs/heads/main"):
            for t in self.custom_tag_list:
                tags.append(f"{self.image}:main-{t}")
        tags.append(f"{self.image}:{self.versioned_tag}")

        # If dev target, add -dev suffix to all tags
        if self.is_dev:
            tags = [f"{t}-dev" for t in tags]
        return tags


def _extract_tarball(tarball: Path, dest: Path) -> Path:
    """Extract a tarball and return the root directory."""
    with tarfile.open(tarball, "r:gz") as tar:
        tar.extractall(dest)
    # Find the extracted directory (usually has a single top-level dir)
    dirs = [d for d in dest.iterdir() if d.is_dir()]
    if len(dirs) == 1:
        return dirs[0]
    return dest


def build_workspace_sdists(workspace_root: Path, output_dir: Path) -> list[Path]:
    """Build sdists for all workspace packages.
    
    Returns a list of paths to the built sdist tarballs.
    """
    print(f"[build] Building sdists from workspace at {workspace_root}")
    
    # Read workspace members from pyproject.toml
    import tomllib
    with open(workspace_root / "pyproject.toml", "rb") as f:
        config = tomllib.load(f)
    
    workspace_members = config.get("tool", {}).get("uv", {}).get("workspace", {}).get("members", [])
    if not workspace_members:
        raise ValueError("No workspace members found in pyproject.toml")
    
    sdist_paths: list[Path] = []
    
    for member in workspace_members:
        member_path = workspace_root / member
        if not member_path.exists():
            print(f"[build] WARNING: Workspace member {member} not found at {member_path}")
            continue
        
        print(f"[build] Building sdist for {member}...")
        
        # Use uv build to create sdist
        try:
            result = _run(["uv", "build", "--sdist", "--out-dir", str(output_dir)], cwd=str(member_path))
            print(result.stdout)
        except subprocess.CalledProcessError as e:
            print(f"[build] ERROR building sdist for {member}: {e.stderr}")
            raise
        # Find the created sdist (most recent .tar.gz in output_dir)
        sdists = sorted(output_dir.glob("*.tar.gz"), key=lambda p: p.stat().st_mtime)
        if sdists:
            latest_sdist = sdists[-1]
            sdist_paths.append(latest_sdist)
            print(f"[build] Built: {latest_sdist.name}")
    return sdist_paths


def create_clean_build_context(workspace_root: Path) -> Path:
    """Create a clean build context by building and extracting sdists.
    
    Builds sdists for all workspace packages using `uv build --sdist`,
    extracts them to a temp directory, and adds necessary build files.
    
    Returns the path to the temporary build context directory.
    """
    build_context = Path(tempfile.mkdtemp(prefix="agent-server-build-"))
    print(f"[build] Creating clean build context at {build_context}")
    
    # Create a temp directory for sdist output
    sdist_dir = Path(tempfile.mkdtemp(prefix="agent-server-sdist-"))
    
    try:
        # Build sdists for all workspace packages
        sdist_paths = build_workspace_sdists(workspace_root, sdist_dir)
        
        if not sdist_paths:
            raise RuntimeError("No sdists were built")
        
        print(f"[build] Built {len(sdist_paths)} sdist(s)")
        
        # Extract all sdists to build context
        for sdist_path in sdist_paths:
            print(f"[build] Extracting {sdist_path.name}...")
            extracted_dir = _extract_tarball(sdist_path, build_context)
            
            # Move contents of extracted directory up to build context root
            # This handles the package-name-version directory structure
            if extracted_dir != build_context:
                for item in extracted_dir.iterdir():
                    dest = build_context / item.name
                    if dest.exists():
                        if dest.is_dir():
                            shutil.rmtree(dest)
                        else:
                            dest.unlink()
                    shutil.move(str(item), str(dest))
                extracted_dir.rmdir()
        
        # Copy essential root files that may not be in sdists
        for file in ["pyproject.toml", "uv.lock", "README.md", "LICENSE"]:
            src = workspace_root / file
            dest = build_context / file
            if src.exists() and not dest.exists():
                shutil.copy2(src, dest)
        
        # Copy Docker-specific files (not included in sdists)
        docker_src = workspace_root / "openhands" / "agent_server" / "docker"
        if (docker_src / "wallpaper.svg").exists():
            docker_dest = build_context / "openhands" / "agent_server" / "docker"
            docker_dest.mkdir(parents=True, exist_ok=True)
            shutil.copy2(docker_src / "wallpaper.svg", docker_dest / "wallpaper.svg")
        
        # Copy Dockerfile to build context
        if (docker_src / "Dockerfile").exists():
            docker_dest = build_context / "openhands" / "agent_server" / "docker"
            docker_dest.mkdir(parents=True, exist_ok=True)
            shutil.copy2(docker_src / "Dockerfile", docker_dest / "Dockerfile")
        
        print(f"[build] Build context ready at {build_context}")
        return build_context
        
    finally:
        # Clean up sdist directory
        if sdist_dir.exists():
            shutil.rmtree(sdist_dir, ignore_errors=True)


def _build_with_options(opts: BuildOptions, clean_context_dir: Path) -> list[str]:
    """Internal function to build Docker image with BuildOptions and a clean context."""
    # Resolve paths
    dockerfile = Path(opts.dockerfile)
    if not dockerfile.exists():
        raise FileNotFoundError(f"Dockerfile not found at {dockerfile}")
    
    context = clean_context_dir
    print(f"[build] Using clean build context at {context}")

    tags = opts.all_tags

    # Decide push vs load
    push = opts.push
    if push is None:
        push = bool(os.environ.get("GITHUB_ACTIONS") or os.environ.get("CI"))

    # Buildx args (single list; minimal branching)
    args: list[str] = [
        "docker", "buildx", "build",
        "--file", str(dockerfile),
        "--target", opts.target,
        "--build-arg", f"BASE_IMAGE={opts.base_image}",
    ]
    if push:
        # ensure builder exists (harmless if it does)
        subprocess.run(["docker", "buildx", "create", "--use", "--name", "agentserver-builder"],
                       text=True, capture_output=True)
        args += ["--platform", opts.platforms, "--push"]
    else:
        args += ["--load"]

    for t in tags:
        args += ["--tag", t]

    # Build Caching
    cache_tag, cache_tag_base = opts.cache_tags
    args += [
        "--cache-from", f"type=registry,ref={opts.image}:{cache_tag}",
        "--cache-from", f"type=registry,ref={opts.image}:{cache_tag_base}-main",
        "--cache-to",   f"type=registry,ref={opts.image}:{cache_tag},mode=max",
        str(context),
    ]

    # Pretty logs (stable)
    print(f"[build] Building target='{opts.target}' image='{opts.image}' custom_tags='{opts.custom_tags}' "
          f"from base='{opts.base_image}' for platforms='{opts.platforms if push else 'local-arch'}'")
    print(f"[build] Git ref='{GIT_REF}' sha='{GIT_SHA}' version='{SDK_VERSION}'")
    print(f"[build] Cache tag: {cache_tag}")
    print("[build] Tags:", file=sys.stderr)
    for t in tags:
        print(f" - {t}", file=sys.stderr)

    # Execute
    try:
        res = _run(args, cwd=str(context))
    except subprocess.CalledProcessError as e:
        # surface docker/buildx output
        sys.stdout.write(e.stdout or "")
        sys.stderr.write(e.stderr or "")
        raise

    # Footer for compatibility with existing parsers
    print("[build] Done. Tags:")
    for t in tags:
        print(f" - {t}")
    return tags


# -------- Public API --------

def build_agent_image(
    base_image: str,
    target: str = "source",
    variant_name: str = "custom",
    platforms: str = "linux/amd64",
    project_root: str | None = None,
) -> str:
    """Build the agent-server Docker image.

    This creates a clean build context from sdists in a temporary directory
    and builds the Docker image, cleaning up afterwards.

    Args:
        base_image: Base Docker image to use (e.g., "nikolaik/python-nodejs:python3.12-nodejs22")
        target: Build target (source, source-minimal, binary, binary-minimal)
        variant_name: Custom tag variant name
        platforms: Comma-separated list of platforms (e.g., "linux/amd64,linux/arm64")
        project_root: Path to project root (auto-detected if not provided)

    Returns:
        The first image tag built

    Raises:
        FileNotFoundError: If Dockerfile cannot be located
        RuntimeError: If build fails
    """
    # Auto-detect project root if not provided
    if not project_root:
        # Try to locate project root via importlib
        try:
            import importlib.util
            spec = importlib.util.find_spec("openhands.agent_server")
            if spec and spec.origin:
                # spec.origin points to __init__.py
                # Go up 3 levels: __init__.py -> agent_server -> openhands -> root
                project_root = str(Path(spec.origin).parent.parent.parent)
        except Exception:
            pass
        
        if not project_root:
            # Fall back to detecting from this file's location
            # This file is: openhands/agent_server/docker/build.py
            # Go up 3 levels to get to root
            project_root = str(Path(__file__).resolve().parents[3])

    # Locate the Dockerfile
    dockerfile_path = Path(project_root) / "openhands" / "agent_server" / "docker" / "Dockerfile"
    if not dockerfile_path.exists():
        raise FileNotFoundError(
            f"Could not locate Dockerfile at {dockerfile_path}. "
            "Ensure you're running in the OpenHands repo or pass an explicit "
            "project_root."
        )

    print(
        f"[build] Building agent-server image with base '{base_image}', target '{target}', "
        f"variant '{variant_name}' for platforms '{platforms}'"
    )

    # Parse platforms
    platform_list = [p.strip() for p in platforms.split(",")]

    # Create BuildOptions
    opts = BuildOptions(
        base_image=base_image,
        dockerfile=str(dockerfile_path),
        context_dir=project_root,  # Only used for reference, not actual build
        custom_tags=variant_name,
        target=target,  # type: ignore
        platforms=platform_list,  # type: ignore
        push=False,  # Always load locally for workspace builds
    )

    # Create clean build context in temp directory and build image
    workspace_root = Path(project_root).resolve()
    clean_context = None
    try:
        # Create temporary clean build context from sdists
        clean_context = create_clean_build_context(workspace_root)
        
        # Build the Docker image using the clean context
        tags = _build_with_options(opts, clean_context_dir=clean_context)
        
        if not tags:
            raise RuntimeError("No tags returned from build")
        
        image = tags[0]
        print(f"[build] Using image: {image}")
        return image
    finally:
        # Always clean up temporary build context
        if clean_context and clean_context.exists():
            print(f"[build] Cleaning up temporary build context at {clean_context}")
            shutil.rmtree(clean_context, ignore_errors=True)





# -------- CLI --------

def _env(name: str, default: str) -> str:
    v = os.environ.get(name)
    return v if v is not None and v != "" else default


def main(argv: list[str]) -> int:
    # Minimal, env-first CLI to keep it simple
    # For advanced control (push, custom image names), use BuildOptions + _build_with_options
    # For simple builds, use build_agent_image
    
    base_image = _env("BASE_IMAGE", "nikolaik/python-nodejs:python3.12-nodejs22")
    target = _env("TARGET", "binary")
    variant_name = _env("CUSTOM_TAGS", "python")
    platforms = _env("PLATFORMS", "linux/amd64,linux/arm64")
    project_root = os.environ.get("AGENT_SDK_PATH")
    
    # Check if advanced options are needed
    needs_advanced = (
        os.environ.get("PUSH") == "1" or
        os.environ.get("IMAGE") or
        os.environ.get("DOCKERFILE")
    )
    
    if needs_advanced:
        # Use advanced BuildOptions API for full control
        opts = BuildOptions(
            base_image=base_image,
            dockerfile=os.environ.get("DOCKERFILE"),  # type: ignore
            context_dir=project_root or ".", # type: ignore
            image=_env("IMAGE", "ghcr.io/all-hands-ai/agent-server"),
            custom_tags=variant_name,
            target=target, # type: ignore
            platforms=list(platforms.split(",")), # type: ignore
            push=(True if os.environ.get("PUSH") == "1" else False if os.environ.get("LOAD") == "1" else None),
        )
        
        workspace_root = Path(opts.context_dir).resolve()
        clean_context = None
        try:
            clean_context = create_clean_build_context(workspace_root)
            tags = _build_with_options(opts, clean_context_dir=clean_context)
            print(",".join(tags))
            return 0
        finally:
            if clean_context and clean_context.exists():
                print(f"[build] Cleaning up temporary build context at {clean_context}")
                shutil.rmtree(clean_context, ignore_errors=True)
    else:
        # Use simple build_agent_image API
        image = build_agent_image(
            base_image=base_image,
            target=target,
            variant_name=variant_name,
            platforms=platforms,
            project_root=project_root,
        )
        print(image)
        return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
