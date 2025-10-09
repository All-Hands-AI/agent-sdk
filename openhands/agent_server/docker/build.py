#!/usr/bin/env python3
"""
Single-entry build helper for agent-server images.

- Targets: binary | binary-minimal | source | source-minimal
- Multi-tagging via CUSTOM_TAGS (comma-separated)
- Versioned tag includes primary custom tag: v{SDK}_{BASE_SLUG}
- Branch-scoped cache keys
- CI (push) vs local (load) behavior
- sdist-based builds: Uses `uv build` to create clean build contexts
- One entry: build(opts: BuildOptions)
- Automatically detects sdk_project_root (no manual arg)
- No local artifacts left behind (uses tempfile dirs only)
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
from openhands.sdk import get_logger

logger = get_logger(__name__)

VALID_TARGETS = {"binary", "binary-minimal", "source", "source-minimal"}
TargetType = Literal["binary", "binary-minimal", "source", "source-minimal"]
PlatformType = Literal["linux/amd64", "linux/arm64"]


# --- helpers ---

def _run(cmd: list[str], cwd: str | None = None) -> subprocess.CompletedProcess:
    logger.debug(f"$ {' '.join(cmd)} (cwd={cwd})")
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


# --- options ---

def _default_sdk_project_root() -> Path:
    """Resolve the root of the OpenHands SDK project."""
    try:
        import importlib.util
        spec = importlib.util.find_spec("openhands.agent_server")
        if spec and spec.origin:
            return Path(spec.origin).parent.parent.parent.resolve()
    except Exception:
        pass

    raise RuntimeError("Could not resolve OpenHands SDK project root. "
                           "Please set AGENT_SDK_PATH environment variable.")


class BuildOptions(BaseModel):
    base_image: str = Field(default="nikolaik/python-nodejs:python3.12-nodejs22")
    sdk_project_root: Path = Field(
        default_factory=_default_sdk_project_root,
        description="Path to OpenHands SDK root. Auto if None."
    )
    custom_tags: str = Field(default="", description="Comma-separated list of custom tags.")
    image: str = Field(default="ghcr.io/all-hands-ai/agent-server")
    target: TargetType = Field(default="binary")
    platforms: list[PlatformType] = Field(default=["linux/amd64"])
    push: bool | None = Field(default=None, description="None=auto (CI push, local load)")

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
        return f"v{SDK_VERSION}_{self.base_image_slug}"

    @property
    def cache_tags(self) -> tuple[str, str]:
        base = f"buildcache-{self.target}-{self.base_image_slug}"
        if GIT_REF in ("main", "refs/heads/main"):
            return f"{base}-main", base
        elif GIT_REF != "unknown":
            return f"{base}-{_sanitize_branch(GIT_REF)}", base
        else:
            return base, base

    @property
    def all_tags(self) -> list[str]:
        tags: list[str] = []
        for t in self.custom_tag_list:
            tags.append(f"{self.image}:{SHORT_SHA}-{t}")
        if GIT_REF in ("main", "refs/heads/main"):
            for t in self.custom_tag_list:
                tags.append(f"{self.image}:main-{t}")
        tags.append(f"{self.image}:{self.versioned_tag}")
        if self.is_dev:
            tags = [f"{t}-dev" for t in tags]
        return tags


# --- build helpers ---

def _extract_tarball(tarball: Path, dest: Path) -> None:
    with tarfile.open(tarball, "r:gz") as tar:
        for m in tar.getmembers():
            p = Path(m.name)
            if ".." in p.parts or p.is_absolute():
                raise RuntimeError(f"Unsafe path in sdist: {m.name}")
        tar.extractall(dest)


def _build_sdists(workspace_root: Path, output_dir: Path) -> list[Path]:
    import tomllib
    config = tomllib.loads((workspace_root / "pyproject.toml").read_text("utf-8"))
    members = config.get("tool", {}).get("uv", {}).get("workspace", {}).get("members", [])
    if not members:
        raise ValueError("No workspace members found in pyproject.toml")

    sdists: list[Path] = []
    for member in members:
        member_path = workspace_root / member
        if not member_path.exists():
            logger.info(f"[build] WARNING: Workspace member {member} not found")
            continue
        _run(["uv", "build", "--sdist", "--out-dir", str(output_dir.resolve())],
             cwd=str(member_path.resolve()))
        latest = sorted(output_dir.glob("*.tar.gz"), key=lambda p: p.stat().st_mtime)
        if latest:
            sdists.append(latest[-1])
    return sdists


def _make_clean_context(sdk_project_root: Path) -> Path:
    tmp_root = Path(tempfile.mkdtemp(prefix="agent-build-", dir=None)).resolve()
    sdist_dir = Path(tempfile.mkdtemp(prefix="agent-sdist-", dir=None)).resolve()
    try:
        sdists = _build_sdists(sdk_project_root, sdist_dir)
        for s in sdists:
            logger.debug(f"[build] Extracting sdist {s} to clean context {tmp_root}")
            _extract_tarball(s, tmp_root)
        return tmp_root
    except Exception:
        shutil.rmtree(tmp_root, ignore_errors=True)
        raise
    finally:
        shutil.rmtree(sdist_dir, ignore_errors=True)


# --- single entry point ---

def build(opts: BuildOptions) -> list[str]:
    """Single entry point for building the agent-server image."""
    dockerfile_path = (
        opts.sdk_project_root / "openhands" / "agent_server" / "docker" / "Dockerfile"
    )
    if not dockerfile_path.exists():
        raise FileNotFoundError(f"Dockerfile not found at {dockerfile_path}")

    push = opts.push
    if push is None:
        push = bool(os.environ.get("GITHUB_ACTIONS") or os.environ.get("CI"))

    tags = opts.all_tags
    cache_tag, cache_tag_base = opts.cache_tags

    ctx = _make_clean_context(opts.sdk_project_root)
    logger.info(f"[build] Clean build context: {ctx}")

    args = [
        "docker", "buildx", "build",
        "--file", str(dockerfile_path),
        "--target", opts.target,
        "--build-arg", f"BASE_IMAGE={opts.base_image}",
    ]
    if push:
        args += ["--platform", ",".join(opts.platforms), "--push"]
    else:
        args += ["--load"]

    for t in tags:
        args += ["--tag", t]

    args += [
        "--cache-from", f"type=registry,ref={opts.image}:{cache_tag}",
        "--cache-from", f"type=registry,ref={opts.image}:{cache_tag_base}-main",
        "--cache-to",   f"type=registry,ref={opts.image}:{cache_tag},mode=max",
        str(ctx),
    ]

    logger.info(f"[build] Building target='{opts.target}' image='{opts.image}' custom_tags='{opts.custom_tags}' "
          f"from base='{opts.base_image}' for platforms='{opts.platforms if push else 'local-arch'}'")
    logger.info(f"[build] Git ref='{GIT_REF}' sha='{GIT_SHA}' version='{SDK_VERSION}'")
    logger.info(f"[build] Cache tag: {cache_tag}")
    logger.info("[build] Tags:")
    for t in tags:
        logger.info(f" - {t}")

    try:
        res = _run(args, cwd=str(ctx))
        sys.stdout.write(res.stdout or "")
    except subprocess.CalledProcessError as e:
        sys.stdout.write(e.stdout or "")
        sys.stderr.write(e.stderr or "")
        raise
    finally:
        logger.info(f"[build] Cleaning {ctx}")
        shutil.rmtree(ctx, ignore_errors=True)

    logger.info("[build] Done. Tags:")
    for t in tags:
        logger.info(f" - {t}")
    return tags


# --- CLI shim ---

def _env(name: str, default: str) -> str:
    v = os.environ.get(name)
    return v if v else default


def main(argv: list[str]) -> int:
    extra_kwargs = {}
    if sdk_project_root := os.environ.get("AGENT_SDK_PATH"):
        sdk_project_root = Path(sdk_project_root).expanduser().resolve()
        if not sdk_project_root.exists():
            logger.info(f"[build] Provided ERROR: AGENT_SDK_PATH '{sdk_project_root}' does not exist", file=sys.stderr)
            return 1
        extra_kwargs["sdk_project_root"] = sdk_project_root

    opts = BuildOptions(
        base_image=_env("BASE_IMAGE", "nikolaik/python-nodejs:python3.12-nodejs22"),
        custom_tags=_env("CUSTOM_TAGS", ""),
        image=_env("IMAGE", "ghcr.io/all-hands-ai/agent-server"),
        target=_env("TARGET", "binary"),  # type: ignore
        platforms=[p.strip() for p in _env("PLATFORMS", "linux/amd64,linux/arm64").split(",")],  # type: ignore
        push=(True if os.environ.get("PUSH") == "1" else False if os.environ.get("LOAD") == "1" else None),
        **extra_kwargs,
    )
    tags = build(opts)
    logger.info(",".join(tags))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
