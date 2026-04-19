import json

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from backend.auth_utils import decode_token
from backend.database import get_db, row
from backend.ws_manager import manager

ws_router = APIRouter()


@ws_router.websocket("/ws/section/{section_id}")
async def section_ws(ws: WebSocket, section_id: int, token: str = Query(...)):
    payload = decode_token(token)
    if not payload:
        await ws.close(code=4001, reason="Unauthorized")
        return

    user_id = int(payload["sub"])
    db = get_db()
    user = row(db.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone())
    section = row(db.execute("SELECT * FROM sections WHERE id=?", (section_id,)).fetchone())
    db.close()

    if not user or not section:
        await ws.close(code=4004, reason="Not found")
        return

    full_name = user.get("full_name") or user.get("email", f"User {user_id}")
    await manager.connect(ws, section_id, user_id, full_name)

    # Send current content on connect
    await ws.send_text(json.dumps({
        "type": "init",
        "section_id": section_id,
        "content": section["content"],
        "users": manager.get_presence(section_id),
        "lock_holder": manager.get_lock_holder_meta(section_id),
    }))

    try:
        while True:
            raw = await ws.receive_text()
            msg = json.loads(raw)
            msg_type = msg.get("type")

            if msg_type == "text_change":
                content = msg.get("content", "")
                db2 = get_db()
                db2.execute(
                    "UPDATE sections SET content=?, updated_at=datetime('now') WHERE id=?",
                    (content, section_id),
                )
                db2.commit()
                db2.close()
                await manager.broadcast(section_id, {
                    "type": "text_broadcast",
                    "section_id": section_id,
                    "content": content,
                    "sender_id": user_id,
                    "sender_name": full_name,
                }, exclude=user_id)
                await manager.send(section_id, user_id, {"type": "save_ack", "section_id": section_id})

            elif msg_type == "lock_request":
                granted = manager.try_lock(section_id, user_id)
                if granted:
                    await manager.send(section_id, user_id, {"type": "lock_granted", "section_id": section_id})
                    await manager._push_presence(section_id)
                else:
                    holder = manager.get_lock_holder_meta(section_id)
                    await manager.send(section_id, user_id, {
                        "type": "lock_denied", "section_id": section_id, "held_by": holder
                    })

            elif msg_type == "lock_release":
                manager.release_lock(section_id, user_id)
                await manager._push_presence(section_id)

            elif msg_type == "ping":
                await ws.send_text(json.dumps({"type": "pong"}))

    except WebSocketDisconnect:
        manager.release_lock(section_id, user_id)
        manager.disconnect(section_id, user_id)
        await manager._push_presence(section_id)
