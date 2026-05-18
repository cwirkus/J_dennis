from datetime import datetime, timezone
from urllib.parse import unquote

from fastapi import APIRouter, HTTPException, Query

from app.services import artsy_service, csv_service, hunter_service, outreach_generator, research_service

router = APIRouter(prefix="/api/v1/prospects", tags=["prospects"])


@router.post("/import-from-artsy")
def import_from_artsy():
    galleries = artsy_service.search_galleries()
    added = 0
    skipped = 0
    for g in galleries:
        if not g.get("email") and g.get("website"):
            domain = g["website"].removeprefix("https://").removeprefix("http://").split("/")[0]
            g["email"] = hunter_service.find_email(domain, g.get("name")) or ""
        prospect = {
            "name": g.get("name", ""),
            "organization": g.get("name", ""),
            "category": "gallery",
            "country": "",
            "email": g.get("email", ""),
            "phone": "",
            "website": g.get("website", ""),
            "priority": 2,
            "status": "not_contacted",
            "notes": g.get("location", ""),
            "date_contacted": "",
            "last_activity": "",
            "source": "artsy",
        }
        if csv_service.append_prospect(prospect):
            added += 1
        else:
            skipped += 1
    return {"added": added, "skipped": skipped}


@router.get("")
def list_prospects(
    status: str | None = Query(None),
    country: str | None = Query(None),
):
    rows = csv_service.get_all_prospects()
    if status:
        rows = [r for r in rows if r.get("status") == status]
    if country:
        rows = [r for r in rows if r.get("country", "").lower() == country.lower()]
    return rows


@router.get("/{email}")
def get_prospect(email: str):
    row = csv_service.find_by_email(unquote(email))
    if not row:
        raise HTTPException(status_code=404, detail="Prospect not found")
    return row


@router.patch("/{email}")
def patch_prospect(email: str, updates: dict):
    if not csv_service.update_prospect(unquote(email), updates):
        raise HTTPException(status_code=404, detail="Prospect not found")
    return csv_service.find_by_email(unquote(email))


@router.delete("/{email}")
def delete_prospect(email: str):
    if not csv_service.delete_by_email(unquote(email)):
        raise HTTPException(status_code=404, detail="Prospect not found")
    return {"deleted": True}


@router.post("/{email}/research")
async def research_prospect_endpoint(email: str):
    decoded = unquote(email)
    prospect = csv_service.find_by_email(decoded)
    if not prospect:
        raise HTTPException(status_code=404, detail="Prospect not found")

    research = await research_service.research_prospect(prospect)
    qualified, score_reason = await research_service.qualify_prospect(prospect, research)

    notes_update = prospect.get("notes", "")
    if research.get("recent_activity"):
        separator = "\n---\n" if notes_update else ""
        notes_update = notes_update + separator + research["recent_activity"]

    csv_service.update_prospect(decoded, {
        "notes": notes_update,
        "last_activity": datetime.now(timezone.utc).isoformat(),
    })

    return {
        "prospect": decoded,
        "research": research,
        "qualified": qualified,
        "score_reason": score_reason,
    }


@router.post("/{email}/generate-outreach")
async def generate_outreach_endpoint(email: str):
    decoded = unquote(email)
    prospect = csv_service.find_by_email(decoded)
    if not prospect:
        raise HTTPException(status_code=404, detail="Prospect not found")

    research = {"notes": prospect.get("notes", "")}
    result = await outreach_generator.generate_outreach(prospect, research)

    draft = csv_service.append_draft({
        "prospect_email": decoded,
        "subject": result.get("subject", ""),
        "body": result.get("body", ""),
        "status": "pending",
    })
    return draft


@router.get("/{email}/drafts")
def get_drafts_for_prospect(email: str):
    decoded = unquote(email)
    all_drafts = csv_service.get_all_drafts()
    return [d for d in all_drafts if d.get("prospect_email", "").lower() == decoded.lower()]
