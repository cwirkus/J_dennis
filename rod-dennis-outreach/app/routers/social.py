from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.database import get_db
from app.services import social_generator

router = APIRouter(prefix="/api/v1/social", tags=["social"])


class GenerateRequest(BaseModel):
    trigger_event: str
    context: str = ""
    platforms: list[str] = ["linkedin", "twitter", "instagram"]


class EditRequest(BaseModel):
    content: str


@router.post("/generate")
async def generate(req: GenerateRequest):
    result = await social_generator.generate_social_content(
        trigger_event=req.trigger_event,
        context=req.context,
        platforms=req.platforms,
    )
    db = get_db()
    drafts = []
    for platform, content in result.items():
        row = db.table("social_drafts").insert({
            "platform": platform,
            "content": content,
            "trigger_event": req.trigger_event,
            "status": "pending",
        }).execute().data
        if row:
            drafts.append(row[0])
    return {"drafts": drafts}


@router.get("/pending")
def get_pending():
    return (
        get_db().table("social_drafts")
        .select("*")
        .eq("status", "pending")
        .order("created_at", desc=True)
        .execute()
        .data or []
    )


@router.patch("/{draft_id}/approve")
def approve(draft_id: str):
    db = get_db()
    rows = db.table("social_drafts").select("*").eq("id", draft_id).execute().data or []
    if not rows:
        raise HTTPException(status_code=404, detail="Draft not found")
    draft = rows[0]
    db.table("social_drafts").update({
        "status": "approved",
        "approved_at": datetime.now(timezone.utc).isoformat(),
    }).eq("id", draft_id).execute()
    return {"success": True, "platform": draft["platform"], "content": draft["content"]}


@router.patch("/{draft_id}/edit")
def edit(draft_id: str, req: EditRequest):
    db = get_db()
    if not db.table("social_drafts").select("id").eq("id", draft_id).execute().data:
        raise HTTPException(status_code=404, detail="Draft not found")
    db.table("social_drafts").update({"content": req.content}).eq("id", draft_id).execute()
    rows = db.table("social_drafts").select("*").eq("id", draft_id).execute().data or []
    return rows[0] if rows else {}


@router.patch("/{draft_id}/unapprove")
def unapprove(draft_id: str):
    db = get_db()
    if not db.table("social_drafts").select("id").eq("id", draft_id).execute().data:
        raise HTTPException(status_code=404, detail="Draft not found")
    db.table("social_drafts").update({"status": "pending", "approved_at": None}).eq("id", draft_id).execute()
    return {"success": True}


@router.delete("/{draft_id}")
def delete(draft_id: str):
    db = get_db()
    if not db.table("social_drafts").select("id").eq("id", draft_id).execute().data:
        raise HTTPException(status_code=404, detail="Draft not found")
    db.table("social_drafts").delete().eq("id", draft_id).execute()
    return {"success": True}
