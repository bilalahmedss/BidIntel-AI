import json
from collections import defaultdict
from typing import Dict, Optional

from fastapi import WebSocket

COLORS = ["#4ade80", "#f472b6", "#60a5fa", "#fb923c", "#a78bfa", "#34d399", "#fbbf24", "#f87171"]


class ConnectionManager:
    def __init__(self):
        self._rooms: Dict[int, Dict[int, WebSocket]] = defaultdict(dict)
        self._locks: Dict[int, Optional[int]] = {}
        self._meta: Dict[int, dict] = {}

    async def connect(self, ws: WebSocket, section_id: int, user_id: int, full_name: str):
        await ws.accept()
        self._rooms[section_id][user_id] = ws
        self._meta[user_id] = {
            "user_id": user_id,
            "full_name": full_name or f"User {user_id}",
            "color": COLORS[user_id % len(COLORS)],
        }
        await self._push_presence(section_id)

    def disconnect(self, section_id: int, user_id: int):
        self._rooms[section_id].pop(user_id, None)
        if self._locks.get(section_id) == user_id:
            self._locks[section_id] = None
        if not self._rooms[section_id]:
            self._rooms.pop(section_id, None)
            self._locks.pop(section_id, None)

    def try_lock(self, section_id: int, user_id: int) -> bool:
        holder = self._locks.get(section_id)
        if holder is None or holder == user_id:
            self._locks[section_id] = user_id
            return True
        return False

    def release_lock(self, section_id: int, user_id: int):
        if self._locks.get(section_id) == user_id:
            self._locks[section_id] = None

    def get_presence(self, section_id: int) -> list:
        holder = self._locks.get(section_id)
        return [{**self._meta[uid], "locked": uid == holder} for uid in self._rooms.get(section_id, {})]

    def get_lock_holder_meta(self, section_id: int) -> Optional[dict]:
        holder = self._locks.get(section_id)
        return self._meta.get(holder) if holder else None

    async def send(self, section_id: int, user_id: int, msg: dict):
        ws = self._rooms.get(section_id, {}).get(user_id)
        if ws:
            try:
                await ws.send_text(json.dumps(msg))
            except Exception:
                self.disconnect(section_id, user_id)

    async def broadcast(self, section_id: int, msg: dict, exclude: int | None = None):
        dead = []
        for uid, ws in list(self._rooms.get(section_id, {}).items()):
            if uid == exclude:
                continue
            try:
                await ws.send_text(json.dumps(msg))
            except Exception:
                dead.append(uid)
        for uid in dead:
            self.disconnect(section_id, uid)

    async def _push_presence(self, section_id: int):
        await self.broadcast(section_id, {
            "type": "presence_update",
            "section_id": section_id,
            "users": self.get_presence(section_id),
            "lock_holder": self.get_lock_holder_meta(section_id),
        })


manager = ConnectionManager()
