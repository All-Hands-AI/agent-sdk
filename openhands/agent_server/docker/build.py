#!/usr/bin/env python3
"""
Simple Docker build helper for agent-server images.

- Targets: binary | binary-minimal | source | source-minimal
- Multi-tagging via CUSTOM_TAGS (comma-separated)
- Versioned tag includes primary custom tag: v{SDK}_{BASE_SLUG}
- Branch-scoped cache keys
- CI (push) vs local (load) behavior
"""

import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, field_validator

VALID_TARGETS = {"binary", "binary-minimal", "source", "source-minimal"}

TargetType = Literal["binary", "binary-minimal", "source", "source-minimal"]
PlatformType = Literal["linux/amd64", "linux/arm64"]


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


def _run(cmd: list[str], cwd: str | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=cwd, text=True, capture_output=True, check=True)



def build_agent_image(opts: BuildOptions) -> list[str]:
    # Resolve paths
    dockerfile = Path(opts.dockerfile)
    if not dockerfile.exists():
        raise FileNotFoundError(f"Dockerfile not found at {dockerfile}")
    
    context = Path(opts.context_dir)
    if not context.exists():
        raise FileNotFoundError(f"Context directory not found at {context}")

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


# -------- CLI --------

def _env(name: str, default: str) -> str:
    v = os.environ.get(name)
    return v if v is not None and v != "" else default


def main(argv: list[str]) -> int:
    # Minimal, env-first CLI to keep it simple
    # Use argparse if you need help text; keeping it lean per your preference.
    opts = BuildOptions(
        base_image=_env("BASE_IMAGE", "nikolaik/python-nodejs:python3.12-nodejs22"),
        dockerfile=os.environ.get("DOCKERFILE"),  # type: ignore
        context_dir=os.environ.get("AGENT_SDK_PATH"), # type: ignore
        image=_env("IMAGE", "ghcr.io/all-hands-ai/agent-server"),
        custom_tags=_env("CUSTOM_TAGS", "python"),
        target=_env("TARGET", "binary"), # type: ignore
        platforms=list(_env("PLATFORMS", "linux/amd64,linux/arm64").split(",")), # type: ignore
        push=(True if os.environ.get("PUSH") == "1" else False if os.environ.get("LOAD") == "1" else None),
    )
    tags = build_agent_image(opts)
    # print CSV for easy piping
    print(",".join(tags))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
