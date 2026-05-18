from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services import chat_service, csv_service

router = APIRouter(prefix="/api/v1/chat", tags=["chat"])


class InboundRequest(BaseModel):
    sender_name: str
    sender_email: str
    channel: str
    message: str


class EditResponseRequest(BaseModel):
    draft_response: str


def _add_priority(row: dict) -> dict:
    row["high_priority"] = (
        row.get("high_priority") == "True"
        or chat_service.is_high_priority(
            row.get("sender_email", ""),
            row.get("sender_name", ""),
            row.get("message", ""),
        )
    )
    return row


@router.post("/inbound")
async def receive_inbound(req: InboundRequest):
    priority = chat_service.is_high_priority(req.sender_email, req.sender_name, req.message)

    saved = csv_service.append_inbound(
        {
            "sender_name": req.sender_name,
            "sender_email": req.sender_email,
            "channel": req.channel,
            "message": req.message,
            "status": "pending",
            "high_priority": str(priority),
        }
    )

    draft = await chat_service.draft_response(
        req.sender_name, req.sender_email, req.channel, req.message
    )
    csv_service.update_inbound(saved["id"], {"draft_response": draft})
    saved["draft_response"] = draft
    saved["high_priority"] = priority

    return saved


@router.get("/pending")
def get_pending():
    rows = csv_service.get_inbound_by_status("pending")
    rows = [_add_priority(r) for r in rows]
    rows.sort(key=lambda r: (not r["high_priority"], r.get("created_at", "")), reverse=False)
    rows.sort(key=lambda r: r.get("created_at", ""), reverse=True)
    rows.sort(key=lambda r: r["high_priority"], reverse=True)
    return rows


@router.get("/high-priority")
def get_high_priority():
    rows = csv_service.get_inbound_by_status("pending")
    rows = [_add_priority(r) for r in rows]
    high = [r for r in rows if r["high_priority"]]
    return sorted(high, key=lambda r: r.get("created_at", ""), reverse=True)


@router.post("/{message_id}/approve-response")
def approve_response(message_id: str):
    msg = csv_service.get_inbound_by_id(message_id)
    if not msg:
        raise HTTPException(status_code=404, detail="Message not found")
    csv_service.update_inbound(
        message_id,
        {
            "status": "approved",
            "sent_at": datetime.now(timezone.utc).isoformat(),
        },
    )
    # Rod copies this text and sends from Gmail himself — nothing sends automatically
    return {
        "success": True,
        "sender_email": msg["sender_email"],
        "draft_response": msg.get("draft_response", ""),
    }


@router.patch("/{message_id}/edit-response")
def edit_response(message_id: str, req: EditResponseRequest):
    updated = csv_service.update_inbound(
        message_id, {"draft_response": req.draft_response}
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Message not found")
    return _add_priority(csv_service.get_inbound_by_id(message_id))


@router.delete("/{message_id}")
def delete_message(message_id: str):
    deleted = csv_service.delete_inbound(message_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Message not found")
    return {"success": True}
