from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.database import get_db
from app.services import chat_service, inbox_monitor

router = APIRouter(prefix="/api/v1/chat", tags=["chat"])

_MSG_COLS = (
    "id,sender_name,sender_email,channel,message,draft_response,"
    "status,sent_at,created_at,high_priority,prospect_org,original_subject,original_body"
)


class InboundRequest(BaseModel):
    sender_name: str
    sender_email: str
    channel: str
    message: str


class EditResponseRequest(BaseModel):
    draft_response: str


def _add_priority(row: dict) -> dict:
    hp = row.get("high_priority")
    if not isinstance(hp, bool):
        hp = chat_service.is_high_priority(
            row.get("sender_email", ""),
            row.get("sender_name", ""),
            row.get("message", ""),
        )
    row["high_priority"] = hp
    return row


@router.post("/inbound")
async def receive_inbound(req: InboundRequest):
    db = get_db()
    priority = chat_service.is_high_priority(req.sender_email, req.sender_name, req.message)

    result = db.table("inbound_messages").insert({
        "sender_name": req.sender_name,
        "sender_email": req.sender_email,
        "channel": req.channel,
        "message": req.message,
        "status": "pending",
        "high_priority": priority,
    }).execute()
    saved = result.data[0] if result.data else {}

    draft = await chat_service.draft_response(
        req.sender_name, req.sender_email, req.channel, req.message
    )
    db.table("inbound_messages").update({"draft_response": draft}).eq("id", saved["id"]).execute()
    saved["draft_response"] = draft
    saved["high_priority"] = priority
    return saved


@router.get("/pending")
def get_pending():
    rows = (
        get_db().table("inbound_messages")
        .select(_MSG_COLS)
        .eq("status", "pending")
        .order("created_at", desc=True)
        .execute()
        .data or []
    )
    rows = [_add_priority(r) for r in rows]
    rows.sort(key=lambda r: r.get("high_priority", False), reverse=True)
    return rows


@router.get("/prospect-replies")
def get_prospect_replies():
    rows = (
        get_db().table("inbound_messages")
        .select(_MSG_COLS)
        .eq("status", "pending")
        .not_.is_("prospect_org", "null")
        .order("created_at", desc=True)
        .execute()
        .data or []
    )
    return [r for r in rows if r.get("prospect_org")]


@router.get("/high-priority")
def get_high_priority():
    rows = (
        get_db().table("inbound_messages")
        .select(_MSG_COLS)
        .eq("status", "pending")
        .execute()
        .data or []
    )
    rows = [_add_priority(r) for r in rows]
    return sorted([r for r in rows if r["high_priority"]], key=lambda r: r.get("created_at", ""), reverse=True)


@router.post("/{message_id}/approve-response")
def approve_response(message_id: str):
    db = get_db()
    rows = db.table("inbound_messages").select(_MSG_COLS).eq("id", message_id).execute().data or []
    if not rows:
        raise HTTPException(status_code=404, detail="Message not found")
    msg = rows[0]

    draft_text = msg.get("draft_response", "")
    to_email = msg["sender_email"]
    original_subject = msg.get("original_subject") or ""
    reply_subject = f"Re: {original_subject}" if original_subject else "Re: Your inquiry"

    sent = inbox_monitor.send_reply(to_email, reply_subject, draft_text)

    db.table("inbound_messages").update({
        "status": "approved",
        "sent_at": datetime.now(timezone.utc).isoformat(),
    }).eq("id", message_id).execute()

    return {"success": True, "sent": sent, "sender_email": to_email, "draft_response": draft_text}


@router.patch("/{message_id}/edit-response")
def edit_response(message_id: str, req: EditResponseRequest):
    db = get_db()
    if not db.table("inbound_messages").select("id").eq("id", message_id).execute().data:
        raise HTTPException(status_code=404, detail="Message not found")
    db.table("inbound_messages").update({"draft_response": req.draft_response}).eq("id", message_id).execute()
    rows = db.table("inbound_messages").select(_MSG_COLS).eq("id", message_id).execute().data or []
    return _add_priority(rows[0]) if rows else {}


@router.delete("/{message_id}")
def delete_message(message_id: str):
    db = get_db()
    if not db.table("inbound_messages").select("id").eq("id", message_id).execute().data:
        raise HTTPException(status_code=404, detail="Message not found")
    db.table("inbound_messages").delete().eq("id", message_id).execute()
    return {"success": True}
