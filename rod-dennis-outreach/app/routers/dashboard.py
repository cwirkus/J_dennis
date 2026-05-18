from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.database import get_db

router = APIRouter(prefix="/api/v1/dashboard", tags=["dashboard"])


@router.get("/pending-outreach")
def pending_outreach():
    db = get_db()

    drafts = (
        db.table("outreach_drafts")
        .select("*")
        .eq("status", "pending")
        .order("created_at", desc=False)
        .execute()
        .data or []
    )

    if not drafts:
        return []

    prospect_ids = [d["prospect_id"] for d in drafts if d.get("prospect_id")]
    prospects_map: dict = {}
    if prospect_ids:
        rows = (
            db.table("prospects")
            .select("id, name, organization, category, country, email, notes, priority")
            .in_("id", prospect_ids)
            .execute()
            .data or []
        )
        prospects_map = {r["id"]: r for r in rows}

    result = []
    for d in drafts:
        p = prospects_map.get(d.get("prospect_id"), {})
        result.append({
            "id": d["id"],
            "prospect_name": p.get("name", ""),
            "organization": p.get("organization", ""),
            "category": p.get("category", ""),
            "country": p.get("country", ""),
            "email": p.get("email", ""),
            "subject": d.get("subject", ""),
            "body": d.get("body", ""),
            "notes": p.get("notes", ""),
            "created_at": d.get("created_at", ""),
        })
    return result


@router.post("/approve-outreach/{draft_id}")
def approve_outreach(draft_id: str):
    db = get_db()

    draft_rows = (
        db.table("outreach_drafts")
        .select("*")
        .eq("id", draft_id)
        .execute()
        .data or []
    )
    if not draft_rows:
        raise HTTPException(status_code=404, detail="Draft not found")
    draft = draft_rows[0]

    now = datetime.now(timezone.utc).isoformat()
    db.table("outreach_drafts").update({
        "status": "approved",
        "approved_at": now,
    }).eq("id", draft_id).execute()

    prospect_id = draft.get("prospect_id")
    prospect_email = ""
    if prospect_id:
        db.table("prospects").update({
            "status": "sent",
            "last_activity": now,
        }).eq("id", prospect_id).execute()

        p_rows = (
            db.table("prospects")
            .select("email")
            .eq("id", prospect_id)
            .execute()
            .data or []
        )
        prospect_email = p_rows[0]["email"] if p_rows else ""

    return {
        "success": True,
        "message": "Draft approved — ready to send",
        "draft_id": draft_id,
        "prospect_email": prospect_email,
        "subject": draft.get("subject", ""),
        "body": draft.get("body", ""),
    }


@router.post("/reject-outreach/{draft_id}")
def reject_outreach(draft_id: str):
    db = get_db()
    rows = db.table("outreach_drafts").select("id").eq("id", draft_id).execute().data or []
    if not rows:
        raise HTTPException(status_code=404, detail="Draft not found")
    db.table("outreach_drafts").update({"status": "rejected"}).eq("id", draft_id).execute()
    return {"success": True, "message": "Draft rejected"}


class EditBody(BaseModel):
    subject: str
    body: str


@router.patch("/edit-outreach/{draft_id}")
def edit_outreach(draft_id: str, payload: EditBody):
    db = get_db()
    rows = db.table("outreach_drafts").select("id").eq("id", draft_id).execute().data or []
    if not rows:
        raise HTTPException(status_code=404, detail="Draft not found")

    db.table("outreach_drafts").update(
        {"subject": payload.subject, "body": payload.body}
    ).eq("id", draft_id).execute()

    refreshed = (
        db.table("outreach_drafts").select("*").eq("id", draft_id).execute().data or []
    )
    return refreshed[0] if refreshed else {}


@router.get("/stats")
def stats():
    db = get_db()

    def count(table: str, **filters) -> int:
        q = db.table(table).select("*", count="exact")
        for col, val in filters.items():
            if val is None:
                q = q.not_.is_(col, "null")
            else:
                q = q.eq(col, val)
        return q.execute().count or 0

    return {
        "total_prospects":  count("prospects"),
        "not_contacted":    count("prospects", status="not_contacted"),
        "sent":             count("prospects", status="sent"),
        "pending_drafts":   count("outreach_drafts", status="pending"),
        "approved_drafts":  count("outreach_drafts", status="approved"),
        "emails_available": count("prospects", email=None),
    }


class PipelineParams(BaseModel):
    limit: int = 10
    priority: int = 1
    country: Optional[str] = None


@router.post("/run-pipeline")
def run_pipeline_endpoint(params: PipelineParams):
    from app.services.pipeline import run_pipeline

    db = get_db()
    before = len(
        db.table("outreach_drafts").select("id").eq("status", "pending").execute().data or []
    )

    run_pipeline(limit=params.limit, priority=params.priority, country=params.country)

    after = len(
        db.table("outreach_drafts").select("id").eq("status", "pending").execute().data or []
    )
    return {"new_drafts": max(0, after - before)}


@router.post("/run-discovery")
async def run_discovery_endpoint():
    from app.services.discovery_agent import run_discovery
    result = await run_discovery()
    return {
        "prospects_found": result["prospects_found"],
        "prospects_added": result["prospects_added"],
        "new_prospects": result["new_prospects"],
    }


@router.get("/discovery-log")
def discovery_log():
    db = get_db()
    rows = (
        db.table("discovery_log")
        .select("source, prospects_found, prospects_added, run_at")
        .order("run_at", desc=True)
        .limit(10)
        .execute()
        .data or []
    )
    return rows
