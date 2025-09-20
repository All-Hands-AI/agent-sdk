from fastapi import FastAPI, HTTPException
from fastapi.responses import RedirectResponse

from .docker_service import (
    RuntimeNotFoundError,
    pause_runtime,
    resume_runtime,
    start_runtime,
    stop_runtime,
)
from .models import (
    RuntimeActionRequest,
    RuntimeActionResponse,
    RuntimeStartRequest,
    RuntimeStartResponse,
)


api = FastAPI(
    title="OpenHands Runtime Server",
    description="Lightweight REST API for managing Docker runtimes",
)


@api.get("/", include_in_schema=False)
async def root():
    return RedirectResponse(url="/docs")


@api.post("/start", response_model=RuntimeStartResponse, status_code=201)
def start_runtime_route(request: RuntimeStartRequest) -> RuntimeStartResponse:
    try:
        return start_runtime(request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@api.post("/stop", response_model=RuntimeActionResponse)
def stop_runtime_route(request: RuntimeActionRequest) -> RuntimeActionResponse:
    try:
        return stop_runtime(request)
    except RuntimeNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@api.post("/pause", response_model=RuntimeActionResponse)
def pause_runtime_route(request: RuntimeActionRequest) -> RuntimeActionResponse:
    try:
        return pause_runtime(request)
    except RuntimeNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@api.post("/resume", response_model=RuntimeActionResponse)
def resume_runtime_route(request: RuntimeActionRequest) -> RuntimeActionResponse:
    try:
        return resume_runtime(request)
    except RuntimeNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
