from datetime import datetime, timezone
from urllib.parse import unquote

from fastapi import APIRouter, HTTPException, Query

from app.database import get_db
from app.services import artsy_service, hunter_service, outreach_generator, research_service

router = APIRouter(prefix="/api/v1/prospects", tags=["prospects"])

_PROSPECT_COLS = (
    "id,name,organization,category,country,email,phone,website,"
    "priority,status,notes,date_contacted,last_activity,source,created_at"
)
_ALLOWED_UPDATE = {
    "name", "organization", "category", "country", "email", "phone",
    "website", "priority", "status", "notes", "date_contacted", "last_activity",
}


def _by_email(email: str) -> dict | None:
    rows = get_db().table("prospects").select(_PROSPECT_COLS).eq("email", email).execute().data or []
    return rows[0] if rows else None


@router.post("/import-from-artsy")
def import_from_artsy():
    db = get_db()
    galleries = artsy_service.search_galleries()
    added = skipped = 0
    for g in galleries:
        if not g.get("email") and g.get("website"):
            domain = g["website"].removeprefix("https://").removeprefix("http://").split("/")[0]
            g["email"] = hunter_service.find_email(domain, g.get("name")) or ""
        email = g.get("email", "")
        if email and db.table("prospects").select("id").eq("email", email).execute().data:
            skipped += 1
            continue
        db.table("prospects").insert({
            "name": g.get("name", ""),
            "organization": g.get("name", ""),
            "category": "gallery",
            "country": "",
            "email": email,
            "phone": "",
            "website": g.get("website", ""),
            "priority": 2,
            "status": "not_contacted",
            "notes": g.get("location", ""),
            "source": "artsy",
        }).execute()
        added += 1
    return {"added": added, "skipped": skipped}


@router.get("")
def list_prospects(
    status: str | None = Query(None),
    country: str | None = Query(None),
):
    db = get_db()
    q = db.table("prospects").select(_PROSPECT_COLS)
    if status:
        q = q.eq("status", status)
    if country:
        q = q.ilike("country", country)
    return q.execute().data or []


@router.get("/{email}")
def get_prospect(email: str):
    row = _by_email(unquote(email))
    if not row:
        raise HTTPException(status_code=404, detail="Prospect not found")
    return row


@router.patch("/{email}")
def patch_prospect(email: str, updates: dict):
    decoded = unquote(email)
    if not _by_email(decoded):
        raise HTTPException(status_code=404, detail="Prospect not found")
    safe = {k: v for k, v in updates.items() if k in _ALLOWED_UPDATE}
    get_db().table("prospects").update(safe).eq("email", decoded).execute()
    return _by_email(decoded)


@router.delete("/{email}")
def delete_prospect(email: str):
    decoded = unquote(email)
    if not _by_email(decoded):
        raise HTTPException(status_code=404, detail="Prospect not found")
    get_db().table("prospects").delete().eq("email", decoded).execute()
    return {"deleted": True}


@router.post("/{email}/research")
async def research_prospect_endpoint(email: str):
    decoded = unquote(email)
    prospect = _by_email(decoded)
    if not prospect:
        raise HTTPException(status_code=404, detail="Prospect not found")

    research = await research_service.research_prospect(prospect)
    qualified, score_reason = await research_service.qualify_prospect(prospect, research)

    notes = prospect.get("notes", "")
    if research.get("recent_activity"):
        notes = notes + ("\n---\n" if notes else "") + research["recent_activity"]

    get_db().table("prospects").update({
        "notes": notes,
        "last_activity": datetime.now(timezone.utc).isoformat(),
    }).eq("email", decoded).execute()

    return {"prospect": decoded, "research": research, "qualified": qualified, "score_reason": score_reason}


@router.post("/{email}/generate-outreach")
async def generate_outreach_endpoint(email: str):
    decoded = unquote(email)
    prospect = _by_email(decoded)
    if not prospect:
        raise HTTPException(status_code=404, detail="Prospect not found")

    result = await outreach_generator.generate_outreach(prospect, {"notes": prospect.get("notes", "")})

    row = get_db().table("outreach_drafts").insert({
        "prospect_id": prospect["id"],
        "subject": result.get("subject", ""),
        "body": result.get("body", ""),
        "status": "pending",
    }).execute().data
    return row[0] if row else {}


@router.get("/{email}/drafts")
def get_drafts_for_prospect(email: str):
    decoded = unquote(email)
    prospect = _by_email(decoded)
    if not prospect:
        return []
    return get_db().table("outreach_drafts").select("*").eq("prospect_id", prospect["id"]).execute().data or []
