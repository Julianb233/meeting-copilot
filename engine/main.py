"""Meeting Copilot Engine — FastAPI server with WebSocket + REST API."""

from __future__ import annotations

import logging
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

import config
from api import router as api_router
from ws_handler import manager

# Logging
logging.basicConfig(
    level=logging.DEBUG if config.DEBUG else logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger("copilot")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    logger.info(f"Meeting Copilot Engine starting on {config.HOST}:{config.PORT}")
    logger.info(f"CORS allowed origin: {config.PANEL_ORIGIN}")
    logger.info(f"Debug mode: {config.DEBUG}")
    yield


# App
app = FastAPI(
    title="Meeting Copilot Engine",
    version="0.1.0",
    docs_url="/api/docs" if config.DEBUG else None,
    lifespan=lifespan,
)

# CORS for Zoom iframe
app.add_middleware(
    CORSMiddleware,
    allow_origins=[config.PANEL_ORIGIN],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# REST API
app.include_router(api_router)


# WebSocket endpoint
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            await manager.handle_message(websocket, data)
    except WebSocketDisconnect:
        manager.disconnect(websocket)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=config.HOST,
        port=config.PORT,
        reload=config.DEBUG,
        log_level="debug" if config.DEBUG else "info",
    )
