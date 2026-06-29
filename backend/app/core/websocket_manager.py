from typing import Any

from fastapi import WebSocket
from starlette.websockets import WebSocketState


class WebSocketManager:
    allowed_channels = {"waiters", "kitchen", "bar", "floor", "managers", "public_qr"}

    def __init__(self) -> None:
        self._connections: dict[str, set[WebSocket]] = {
            channel: set()
            for channel in self.allowed_channels
        }

    async def connect(self, *, channel: str, websocket: WebSocket) -> None:
        await websocket.accept()
        self._connections[channel].add(websocket)

    def disconnect(self, *, channel: str, websocket: WebSocket) -> None:
        self._connections[channel].discard(websocket)

    async def broadcast(
        self,
        *,
        channel: str,
        event: str,
        data: dict[str, Any],
    ) -> None:
        if channel not in self.allowed_channels:
            return

        message = {
            "event": event,
            "data": data,
        }
        stale_connections: list[WebSocket] = []

        for websocket in self._connections[channel].copy():
            try:
                if websocket.client_state == WebSocketState.CONNECTED:
                    await websocket.send_json(message)
                else:
                    stale_connections.append(websocket)
            except RuntimeError:
                stale_connections.append(websocket)

        for websocket in stale_connections:
            self.disconnect(channel=channel, websocket=websocket)

    async def broadcast_many(
        self,
        *,
        channels: list[str],
        event: str,
        data: dict[str, Any],
    ) -> None:
        for channel in channels:
            await self.broadcast(channel=channel, event=event, data=data)


websocket_manager = WebSocketManager()
