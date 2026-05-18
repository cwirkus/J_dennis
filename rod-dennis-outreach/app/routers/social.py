from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services import csv_service, social_generator

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

    drafts = []
    for platform, content in result.items():
        draft = csv_service.append_social_draft(
            {
                "platform": platform,
                "content": content,
                "trigger_event": req.trigger_event,
                "status": "pending",
            }
        )
        drafts.append(draft)

    return {"drafts": drafts}


@router.get("/pending")
def get_pending():
    rows = csv_service.get_social_drafts_by_status("pending")
    rows.sort(key=lambda r: r.get("created_at", ""), reverse=True)
    return rows


@router.patch("/{draft_id}/approve")
def approve(draft_id: str):
    draft = csv_service.get_social_draft_by_id(draft_id)
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")
    csv_service.update_social_draft(
        draft_id,
        {
            "status": "approved",
            "approved_at": datetime.now(timezone.utc).isoformat(),
        },
    )
    # Rod copies this text and posts himself — nothing posts automatically
    return {"success": True, "platform": draft["platform"], "content": draft["content"]}


@router.patch("/{draft_id}/edit")
def edit(draft_id: str, req: EditRequest):
    updated = csv_service.update_social_draft(draft_id, {"content": req.content})
    if not updated:
        raise HTTPException(status_code=404, detail="Draft not found")
    return csv_service.get_social_draft_by_id(draft_id)


@router.patch("/{draft_id}/unapprove")
def unapprove(draft_id: str):
    draft = csv_service.get_social_draft_by_id(draft_id)
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")
    csv_service.update_social_draft(draft_id, {"status": "pending", "approved_at": ""})
    return {"success": True}


@router.delete("/{draft_id}")
def delete(draft_id: str):
    deleted = csv_service.delete_social_draft(draft_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Draft not found")
    return {"success": True}
