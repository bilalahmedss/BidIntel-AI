import json
from collections import Counter
from typing import Any

from fastapi import APIRouter, Depends, Query

from backend.database import get_db, rows
from backend.deps import get_current_user
from backend.safety import CONFIDENTIALITY_NOTICE, HUMAN_REVIEW_NOTICE, load_recent_safety_events, load_red_team_summary

router = APIRouter()


def build_safety_summary() -> dict[str, Any]:
    db = get_db()
    raw_events = rows(
        db.execute(
            """
            SELECT route, context, event_type, entity_types_json
            FROM safety_events
            ORDER BY created_at DESC, id DESC
            """
        ).fetchall()
    )
    db.close()

    route_counter: Counter[str] = Counter()
    entity_counter: Counter[str] = Counter()
    event_counter: Counter[str] = Counter()
    history_redactions = 0

    for event in raw_events:
        route_counter[event["route"]] += 1
        event_counter[event["event_type"]] += 1
        entity_types = json.loads(event.get("entity_types_json") or "[]")
        for entity_type in entity_types:
            entity_counter[entity_type] += 1
        if event["event_type"] == "pii_redaction" and event["context"] == "chat_history":
            history_redactions += 1

    return {
        "totals": {
            "events": len(raw_events),
            "pii_redactions": event_counter["pii_redaction"],
            "unsafe_output_fallbacks": event_counter["unsafe_output_fallback"],
            "prompt_injection_detections": event_counter["prompt_injection_detected"],
            "history_redactions": history_redactions,
            "confidentiality_events": event_counter["confidentiality_notice_enforced"],
        },
        "route_breakdown": dict(route_counter),
        "entity_breakdown": dict(entity_counter),
        "confidentiality": {
            "classification": "confidential_by_default",
            "notice": CONFIDENTIALITY_NOTICE,
            "human_review_notice": HUMAN_REVIEW_NOTICE,
        },
        "red_team": load_red_team_summary(),
    }


@router.get("/summary")
def summary(user: dict = Depends(get_current_user)):
    return {
        **build_safety_summary(),
        "recent_events": load_recent_safety_events(limit=12),
    }


@router.get("/events")
def events(limit: int = Query(25, ge=1, le=100), user: dict = Depends(get_current_user)):
    return load_recent_safety_events(limit=limit)
