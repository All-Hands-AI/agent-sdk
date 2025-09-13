"""
System-level APIs: health check, version, exec, filesystem ops.
"""

import asyncio
import os
import time
from pathlib import Path
from typing import Iterator

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from openhands.server.auth import get_master_key


router = APIRouter(
    prefix="/server", tags=["server"], dependencies=[Depends(get_master_key)]
)

# ---------- Config ----------
FS_ROOT = Path(os.getenv("FS_ROOT", "/")).resolve()


# ---------- Helpers ----------
def _safe_path(path: str) -> Path:
    p = (FS_ROOT / path.lstrip("/")).resolve()
    try:
        p.relative_to(FS_ROOT)
    except ValueError:
        raise HTTPException(status_code=400, detail="Path escapes FS_ROOT")
    return p


def _iter_file_chunks(fp, chunk_size: int = 1024 * 1024) -> Iterator[bytes]:
    while True:
        chunk = fp.read(chunk_size)
        if not chunk:
            break
        yield chunk


# ---------- Models ----------
class CmdExecRequest(BaseModel):
    command: list[str] = Field(..., description="Executable and args; no shell.")
    timeout: int = Field(30, ge=1, le=600)
    cwd: str | None = Field(None, description="Working directory under FS_ROOT.")
    env: dict[str, str] | None = None
    max_output_bytes: int = Field(1_000_000, ge=1, le=10_000_000)


class CmdExecResponse(BaseModel):
    stdout: str
    stderr: str
    return_code: int
    timed_out: bool
    duration_ms: int


class FSMkdirRequest(BaseModel):
    path: str
    parents: bool = True


class FSMoveRequest(BaseModel):
    src: str
    dst: str


class FSCopyRequest(BaseModel):
    src: str
    dst: str
    recursive: bool = False


class FSDeleteRequest(BaseModel):
    path: str
    recursive: bool = False


class FSListItem(BaseModel):
    path: str
    is_dir: bool
    size: int | None = None


class FSListResponse(BaseModel):
    root: str
    items: list[FSListItem]


@router.post(
    "/exec",
    response_model=CmdExecResponse,
    summary="Execute a bash command via subprocess.",
)
async def server_exec(req: CmdExecRequest):
    start = time.monotonic()

    env = os.environ.copy()
    if req.env:
        for k, v in req.env.items():
            if isinstance(k, str) and isinstance(v, str):
                env[k] = v

    cwd_path = _safe_path(req.cwd) if req.cwd else FS_ROOT
    if not cwd_path.exists():
        raise HTTPException(status_code=400, detail="cwd does not exist")

    proc = await asyncio.create_subprocess_exec(
        *req.command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=str(cwd_path),
        env=env,
    )

    timed_out = False
    try:
        out_b, err_b = await asyncio.wait_for(proc.communicate(), timeout=req.timeout)
        rc = proc.returncode or -1
    except asyncio.TimeoutError:
        timed_out = True
        rc = -1
        proc.kill()
        try:
            out_b, err_b = await asyncio.wait_for(proc.communicate(), timeout=2)
        except Exception:
            out_b, err_b = b"", b""
        err_b = (err_b or b"") + b"\n[Process timed out]"

    maxb = req.max_output_bytes
    stdout = (out_b or b"")[:maxb].decode(errors="replace")
    stderr = (err_b or b"")[:maxb].decode(errors="replace")
    duration_ms = int((time.monotonic() - start) * 1000)

    return CmdExecResponse(
        stdout=stdout,
        stderr=stderr,
        return_code=rc,
        timed_out=timed_out,
        duration_ms=duration_ms,
    )


@router.post(
    "/fs/upload",
    summary="Upload a file to the server filesystem.",
)
async def fs_upload(
    dest_path: str = Query(
        ...,
        description='Destination file path under FS_ROOT (default "/"). '
        "If exists, will overwrite. "
        "Intermediate directories will be created as needed.",
    ),
    file: UploadFile = File(...),
):
    dest = _safe_path(dest_path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    with dest.open("wb") as f:
        while True:
            chunk = await file.read(1024 * 1024)
            if not chunk:
                break
            f.write(chunk)
    return {"uploaded": str(dest.relative_to(FS_ROOT)), "size": dest.stat().st_size}


@router.get("/fs/download")
def fs_download(path: str = Query(..., description="File path under FS_ROOT.")):
    p = _safe_path(path)
    if not p.exists() or not p.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(str(p), filename=p.name)
