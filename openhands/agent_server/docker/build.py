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
import argparse
import subprocess
import threading
import sys
import tarfile
import tempfile
from contextlib import chdir
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from openhands.sdk.logger import get_logger, rolling_log_view


logger = get_logger(__name__)

VALID_TARGETS = {"binary", "binary-minimal", "source", "source-minimal"}
TargetType = Literal["binary", "binary-minimal", "source", "source-minimal"]
PlatformType = Literal["linux/amd64", "linux/arm64"]


# --- helpers ---

def _run(
    cmd: list[str],
    cwd: str | None = None,
) -> subprocess.CompletedProcess:
    """
    Stream stdout and stderr concurrently into the rolling logger,
    while capturing FULL stdout/stderr.
    Returns CompletedProcess(stdout=<full>, stderr=<full>).
    Raises CalledProcessError with both output and stderr on failure.
    """
    logger.info(f"$ {' '.join(cmd)} (cwd={cwd})")

    proc = subprocess.Popen(
        cmd,
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,   # keep separate
        bufsize=1,                # line-buffered
    )
    assert proc.stdout is not None and proc.stderr is not None

    out_lines: list[str] = []
    err_lines: list[str] = []

    def pump(stream, sink: list[str], log_fn, prefix: str) -> None:
        for line in stream:
            line = line.rstrip("\n")
            sink.append(line)
            log_fn(f"{prefix}{line}")

    with rolling_log_view(
        logger,
        header="$ " + " ".join(cmd) + (f" (cwd={cwd})" if cwd else ""),
    ):
        t_out = threading.Thread(target=pump, args=(proc.stdout, out_lines, logger.info,  "[stdout] "))
        t_err = threading.Thread(target=pump, args=(proc.stderr, err_lines, logger.warning, "[stderr] "))
        t_out.start(); t_err.start()
        t_out.join(); t_err.join()

    rc = proc.wait()
    stdout = ("\n".join(out_lines) + "\n") if out_lines else ""
    stderr = ("\n".join(err_lines) + "\n") if err_lines else ""

    result = subprocess.CompletedProcess(cmd, rc, stdout=stdout, stderr=stderr)

    if rc != 0:
        # Include full outputs on failure
        raise subprocess.CalledProcessError(rc, cmd, output=stdout, stderr=stderr)

    return result


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
            git_ref = _run(
                ["git", "symbolic-ref", "-q", "--short", "HEAD"]
            ).stdout.strip()
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

    raise RuntimeError(
        "Could not resolve OpenHands SDK project root. "
        "Please set AGENT_SDK_PATH environment variable."
    )


class BuildOptions(BaseModel):
    base_image: str = Field(default="nikolaik/python-nodejs:python3.12-nodejs22")
    sdk_project_root: Path = Field(
        default_factory=_default_sdk_project_root,
        description="Path to OpenHands SDK root. Auto if None.",
    )
    custom_tags: str = Field(
        default="", description="Comma-separated list of custom tags."
    )
    image: str = Field(default="ghcr.io/all-hands-ai/agent-server")
    target: TargetType = Field(default="binary")
    platforms: list[PlatformType] = Field(default=["linux/amd64"])
    push: bool | None = Field(
        default=None, description="None=auto (CI push, local load)"
    )

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
    dest = dest.resolve()
    dest.mkdir(parents=True, exist_ok=True)
    with tarfile.open(tarball, "r:gz") as tar, chdir(dest):
        # Pre-validate entries
        for m in tar.getmembers():
            name = m.name.lstrip("./")
            p = Path(name)
            if p.is_absolute() or ".." in p.parts:
                raise RuntimeError(f"Unsafe path in sdist: {m.name}")
        # Safe(-r) extraction: no symlinks/devices
        tar.extractall(path=".", filter="data")


def _make_build_context(sdk_project_root: Path) -> Path:
    tmp_root = Path(tempfile.mkdtemp(prefix="agent-build-", dir=None)).resolve()
    sdist_dir = Path(tempfile.mkdtemp(prefix="agent-sdist-", dir=None)).resolve()
    try:
        # sdists = _build_sdists(sdk_project_root, sdist_dir)
        _run(
            ["uv", "build", "--sdist", "--out-dir", str(sdist_dir.resolve())],
            cwd=str(sdk_project_root.resolve()),
        )
        sdists = sorted(sdist_dir.glob("*.tar.gz"), key=lambda p: p.stat().st_mtime)
        logger.info(
            f"[build] Built {len(sdists)} sdists for clean context: {', '.join(str(s) for s in sdists)}"
        )
        assert len(sdists) == 1, "Expected exactly one sdist"
        logger.debug(f"[build] Extracting sdist {sdists[0]} to clean context {tmp_root}")
        _extract_tarball(sdists[0], tmp_root)
        
        # assert only one folder created
        entries = list(tmp_root.iterdir())
        assert len(entries) == 1 and entries[0].is_dir(), "Expected single folder in sdist"
        tmp_root = entries[0].resolve()
        logger.debug(f"[build] Clean context ready at {tmp_root}")
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

    ctx = _make_build_context(opts.sdk_project_root)
    logger.info(f"[build] Clean build context: {ctx}")

    args = [
        "docker",
        "buildx",
        "build",
        "--file",
        str(dockerfile_path),
        "--target",
        opts.target,
        "--build-arg",
        f"BASE_IMAGE={opts.base_image}",
    ]
    if push:
        args += ["--platform", ",".join(opts.platforms), "--push"]
    else:
        args += ["--load"]

    for t in tags:
        args += ["--tag", t]

    args += [
        "--cache-from",
        f"type=registry,ref={opts.image}:{cache_tag}",
        "--cache-from",
        f"type=registry,ref={opts.image}:{cache_tag_base}-main",
        "--cache-to",
        f"type=registry,ref={opts.image}:{cache_tag},mode=max",
        str(ctx),
    ]

    logger.info(
        f"[build] Building target='{opts.target}' image='{opts.image}' custom_tags='{opts.custom_tags}' "
        f"from base='{opts.base_image}' for platforms='{opts.platforms if push else 'local-arch'}'"
    )
    logger.info(f"[build] Git ref='{GIT_REF}' sha='{GIT_SHA}' version='{SDK_VERSION}'")
    logger.info(f"[build] Cache tag: {cache_tag}")
    logger.info("[build] Tags:")
    for t in tags:
        logger.info(f" - {t}")


    try:
        res = _run(args, cwd=str(ctx))
        sys.stdout.write(res.stdout or "")
    except subprocess.CalledProcessError as e:
        logger.error(f"[build] ERROR: Build failed with exit code {e.returncode}")
        logger.error(f"[build] Command: {' '.join(e.cmd)}")
        logger.error(f"[build] Full stdout:\n{e.output}")
        logger.error(f"[build] Full stderr:\n{e.stderr}")
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
    # ---- argparse ----
    parser = argparse.ArgumentParser(
        description="Single-entry build helper for agent-server images."
    )
    parser.add_argument(
        "--base-image",
        default=_env("BASE_IMAGE", "nikolaik/python-nodejs:python3.12-nodejs22"),
        help="Base image to use (default from $BASE_IMAGE).",
    )
    parser.add_argument(
        "--custom-tags",
        default=_env("CUSTOM_TAGS", ""),
        help="Comma-separated custom tags (default from $CUSTOM_TAGS).",
    )
    parser.add_argument(
        "--image",
        default=_env("IMAGE", "ghcr.io/all-hands-ai/agent-server"),
        help="Image repo/name (default from $IMAGE).",
    )
    parser.add_argument(
        "--target",
        default=_env("TARGET", "binary"),
        choices=sorted(VALID_TARGETS),
        help="Build target (default from $TARGET).",
    )
    parser.add_argument(
        "--platforms",
        default=_env("PLATFORMS", "linux/amd64,linux/arm64"),
        help="Comma-separated platforms (default from $PLATFORMS).",
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--push",
        action="store_true",
        help="Force push via buildx (overrides env).",
    )
    group.add_argument(
        "--load",
        action="store_true",
        help="Force local load (overrides env).",
    )
    parser.add_argument(
        "--sdk-project-root",
        type=Path,
        default=None,
        help="Path to OpenHands SDK root (default: auto-detect or $AGENT_SDK_PATH).",
    )
    parser.add_argument(
        "--build-ctx-only",
        action="store_true",
        help="Only create the clean build context directory and print its path.",
    )

    args = parser.parse_args(argv)

    # ---- resolve sdk project root ----
    sdk_project_root = args.sdk_project_root
    if sdk_project_root is None:
        if os.environ.get("AGENT_SDK_PATH"):
            sdk_project_root = Path(os.environ["AGENT_SDK_PATH"]).expanduser().resolve()
            if not sdk_project_root.exists():
                print(
                    f"[build] ERROR: AGENT_SDK_PATH '{sdk_project_root}' does not exist",
                    file=sys.stderr,
                )
                return 1
        else:
            try:
                sdk_project_root = _default_sdk_project_root()
            except Exception as e:
                logger.error(str(e))
                return 1

    # ---- build-ctx-only path ----
    if args.build_ctx_only:
        ctx = _make_build_context(sdk_project_root)
        logger.info(f"[build] Clean build context (kept for debugging): {ctx}")
        # Print path to stdout so other tooling can capture it
        print(str(ctx))
        return 0


    # ---- push/load resolution (CLI wins over env, else auto) ----
    push: bool | None
    if args.push:
        push = True
    elif args.load:
        push = False
    else:
        push = (
            True
            if os.environ.get("PUSH") == "1"
            else False
            if os.environ.get("LOAD") == "1"
            else None
        )

    # ---- normal build path ----
    opts = BuildOptions(
        base_image=args.base_image,
        custom_tags=args.custom_tags,
        image=args.image,
        target=args.target,  # type: ignore
        platforms=[p.strip() for p in args.platforms.split(",") if p.strip()],  # type: ignore
        push=push,
        sdk_project_root=sdk_project_root,
    )
    tags = build(opts)
    logger.info(",".join(tags))
    return 0

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
