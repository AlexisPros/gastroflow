from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect, status
from jose import JWTError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_access_token
from app.core.websocket_manager import websocket_manager
from app.crud import user as crud_user
from app.db.session import get_db

router = APIRouter(tags=["WebSocket"])

CHANNEL_ROLES = {
    "waiters": {"ADMIN", "MANAGER", "WAITER"},
    "kitchen": {"ADMIN", "MANAGER", "KITCHEN", "CHEF", "WYDAWKA"},
    "bar": {"ADMIN", "MANAGER", "BARTENDER"},
    "floor": {"ADMIN", "MANAGER", "WAITER"},
    "managers": {"ADMIN", "MANAGER"},
}


@router.websocket("/ws/{channel}")
async def websocket_endpoint(
    websocket: WebSocket,
    channel: str,
    token: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    if channel not in websocket_manager.allowed_channels:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    if channel == "public_qr":
        await websocket_manager.connect(channel=channel, websocket=websocket)
        await websocket.send_json(
            {
                "event": "connected",
                "data": {
                    "channel": channel,
                },
            },
        )
        try:
            while True:
                await websocket.receive_text()
        except WebSocketDisconnect:
            websocket_manager.disconnect(channel=channel, websocket=websocket)
        return

    if token is None:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    try:
        payload = decode_access_token(token)
        user_id = int(payload.get("sub", ""))
    except (JWTError, ValueError):
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    current_user = await crud_user.get(db, user_id)
    if current_user is None or not current_user.is_active:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    if current_user.role not in CHANNEL_ROLES[channel]:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await websocket_manager.connect(channel=channel, websocket=websocket)
    await websocket.send_json(
        {
            "event": "connected",
            "data": {
                "channel": channel,
                "user_id": current_user.id,
            },
        },
    )

    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        websocket_manager.disconnect(channel=channel, websocket=websocket)
