from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.config import settings
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
            "priority": p.get("priority", 2),
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


@router.get("/all-prospects")
def all_prospects(offset: int = 0, limit: int = 100, search: Optional[str] = None):
    db = get_db()
    q = (
        db.table("prospects")
        .select("id, name, organization, category, country, email, notes, priority, status")
        .order("priority")
        .order("name")
        .range(offset, offset + limit - 1)
    )
    rows = q.execute().data or []
    if search:
        s = search.lower()
        rows = [r for r in rows if s in (r.get("name") or "").lower() or s in (r.get("organization") or "").lower()]
    return rows


class RewriteBody(BaseModel):
    draft_id: str
    notes: str = ""


@router.post("/rewrite-draft")
def rewrite_draft(payload: RewriteBody):
    import anthropic
    import json
    import os

    from app.services.outreach_generator import ROD_VOICE_SYSTEM_PROMPT, _strip_fences

    db = get_db()

    draft_rows = db.table("outreach_drafts").select("*").eq("id", payload.draft_id).execute().data or []
    if not draft_rows:
        raise HTTPException(status_code=404, detail="Draft not found")
    draft = draft_rows[0]

    prospect_rows = db.table("prospects").select("*").eq("id", draft["prospect_id"]).execute().data or []
    prospect = prospect_rows[0] if prospect_rows else {}

    user_msg = (
        "Write an outreach email to this prospect.\n\n"
        f"Prospect: {prospect.get('name', '')} at {prospect.get('organization', '')}, {prospect.get('country', '')}\n"
        f"Category: {prospect.get('category', '')}\n"
        f"Notes: {prospect.get('notes', '')}\n"
    )
    if payload.notes and payload.notes.strip():
        user_msg += f"\nRod's specific direction for this rewrite: {payload.notes.strip()}\n"
    user_msg += "\nReturn JSON only with keys: subject (str), body (str)"

    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    try:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=2048,
            system=ROD_VOICE_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_msg}],
        )
        text = _strip_fences(response.content[0].text)
        result = json.loads(text)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Generation failed: {exc}")

    db.table("outreach_drafts").update({
        "subject": result.get("subject", ""),
        "body": result.get("body", ""),
    }).eq("id", payload.draft_id).execute()

    return {"subject": result.get("subject", ""), "body": result.get("body", "")}


@router.post("/send-digest")
def send_digest():
    from app.services.tracking_service import send_weekly_digest
    counts = send_weekly_digest()
    return {"success": True, "sent_to": settings.rod_email, **counts}


class DraftForProspectBody(BaseModel):
    prospect_id: str


@router.post("/draft-for-prospect")
def draft_for_prospect(payload: DraftForProspectBody):
    from app.services.research_service import research_prospect
    from app.services.outreach_generator import generate_outreach

    db = get_db()
    prospect_id = payload.prospect_id

    existing = (
        db.table("outreach_drafts")
        .select("*")
        .eq("prospect_id", prospect_id)
        .eq("status", "pending")
        .execute()
        .data or []
    )

    p_rows = db.table("prospects").select("*").eq("id", prospect_id).execute().data or []
    if not p_rows:
        raise HTTPException(status_code=404, detail="Prospect not found")
    prospect = p_rows[0]

    def _build(draft_row):
        return {
            "id": draft_row.get("id", ""),
            "prospect_id": prospect_id,
            "prospect_name": prospect.get("name", ""),
            "organization": prospect.get("organization", ""),
            "category": prospect.get("category", ""),
            "country": prospect.get("country", ""),
            "email": prospect.get("email", ""),
            "subject": draft_row.get("subject", ""),
            "body": draft_row.get("body", ""),
            "notes": prospect.get("notes", ""),
            "created_at": draft_row.get("created_at", ""),
        }

    if existing:
        return _build(existing[0])

    research = research_prospect(prospect)
    draft_content = generate_outreach(prospect, research)

    now = datetime.now(timezone.utc).isoformat()
    result = db.table("outreach_drafts").insert({
        "prospect_id": prospect_id,
        "subject": draft_content.get("subject", ""),
        "body": draft_content.get("body", ""),
        "status": "pending",
    }).execute()

    db.table("prospects").update({"last_activity": now}).eq("id", prospect_id).execute()

    draft_row = result.data[0] if result.data else {"subject": draft_content.get("subject", ""), "body": draft_content.get("body", "")}
    return _build(draft_row)
