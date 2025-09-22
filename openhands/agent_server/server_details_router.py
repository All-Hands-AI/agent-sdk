import time

from fastapi import APIRouter
from pydantic import BaseModel


router = APIRouter(prefix="")
_start_time = time.time()
_last_event_time = time.time()


class ServerInfo(BaseModel):
    uptime: float
    idle_time: float


def update_last_execution_time():
    global _last_event_time
    _last_event_time = time.time()


@router.get("/alive")
async def alive():
    return {"status": "ok"}


@router.get("/health")
async def health() -> str:
    return "OK"


@router.get("/server_info")
async def get_server_info() -> ServerInfo:
    now = time.time()
    return ServerInfo(
        uptime=now - _start_time,
        idle_time=now - _last_event_time,
    )
