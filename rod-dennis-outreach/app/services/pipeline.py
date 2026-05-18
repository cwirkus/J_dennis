import os
import time
from datetime import datetime, timezone

from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

from app.services.research_service import research_prospect
from app.services.outreach_generator import generate_outreach


def _get_db():
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    return create_client(url, key)


def run_pipeline(limit: int = 10, priority: int = 1, country: str = None):
    db = _get_db()

    query = (
        db.table("prospects")
        .select("*")
        .eq("status", "not_contacted")
        .eq("priority", priority)
        .order("priority")
        .order("created_at")
        .limit(limit)
    )
    if country:
        query = query.eq("country", country)

    result = query.execute()
    prospects = result.data or []

    if not prospects:
        print(f"No prospects found (priority={priority}, country={country}).")
        return

    print(f"Found {len(prospects)} prospects. Starting pipeline...\n")
    count = 0

    for prospect in prospects:
        name = prospect.get("name", "Unknown")
        org = prospect.get("organization", "Unknown")
        ctry = prospect.get("country", "")

        print(f"[{count + 1}/{len(prospects)}] {name} | {org} | {ctry}")

        research = research_prospect(prospect)
        print(f"  Research done — best angle: {research.get('best_angle', '')[:100]}")

        draft = generate_outreach(prospect, research)
        subject = draft.get("subject", "")
        body = draft.get("body", "")

        db.table("outreach_drafts").insert({
            "prospect_id": prospect["id"],
            "subject": subject,
            "body": body,
            "status": "pending",
        }).execute()

        db.table("prospects").update({
            "last_activity": datetime.now(timezone.utc).isoformat(),
        }).eq("id", prospect["id"]).execute()

        first_para = body.split("\n\n")[0] if body else ""
        print(f"  Subject : {subject}")
        print(f"  Opening : {first_para[:250]}")
        print()

        count += 1
        time.sleep(1)

    print(f"Done. {count} draft{'s' if count != 1 else ''} generated and saved to outreach_drafts table.")
