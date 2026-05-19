from datetime import datetime, timedelta, timezone

from app.config import settings
from app.database import get_db
from app.services import gmail_service

_HP_CATEGORIES = {"foundation", "museum", "auction house"}


def send_weekly_digest(recipient_email: str = None) -> dict:
    db = get_db()
    now = datetime.now(timezone.utc)
    week_ago = (now - timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%SZ")
    date_str = now.strftime("%Y-%m-%d")

    outreach_count = (
        db.table("outreach_drafts")
        .select("*", count="exact")
        .eq("status", "pending")
        .execute()
        .count or 0
    )

    social_count = (
        db.table("social_drafts")
        .select("*", count="exact")
        .eq("status", "pending")
        .execute()
        .count or 0
    )

    inbox_count = (
        db.table("inbound_messages")
        .select("*", count="exact")
        .eq("status", "pending")
        .execute()
        .count or 0
    )

    new_prospects_count = (
        db.table("prospects")
        .select("*", count="exact")
        .gte("created_at", week_ago)
        .execute()
        .count or 0
    )

    subject = f"Rod — weekly dashboard summary {date_str}"
    body = (
        f"Here is what is waiting for your review this week:\n\n"
        f"Outreach emails ready to approve: {outreach_count}\n"
        f"Social posts ready to review: {social_count}\n"
        f"Inbound messages to respond to: {inbox_count}\n"
        f"New prospects added this week: {new_prospects_count}\n\n"
        f"Open your dashboard to review: {settings.dashboard_url}"
    )

    to = recipient_email or settings.rod_email
    gmail_service.send_email(to=to, subject=subject, body=body)
    print(
        f"[tracking] weekly digest sent to={to} — outreach={outreach_count} social={social_count} "
        f"inbox={inbox_count} new_prospects={new_prospects_count}"
    )

    return {
        "outreach_pending": outreach_count,
        "social_pending": social_count,
        "inbox_pending": inbox_count,
        "new_prospects": new_prospects_count,
    }


def send_priority_nudge() -> None:
    db = get_db()
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=48)).strftime("%Y-%m-%dT%H:%M:%SZ")

    drafts = (
        db.table("outreach_drafts")
        .select("id, prospect_id, created_at")
        .eq("status", "pending")
        .lte("created_at", cutoff)
        .execute()
        .data or []
    )

    if not drafts:
        return

    prospect_ids = [d["prospect_id"] for d in drafts if d.get("prospect_id")]
    if not prospect_ids:
        return

    prospects_rows = (
        db.table("prospects")
        .select("id, name, organization, category")
        .in_("id", prospect_ids)
        .execute()
        .data or []
    )
    prospects_map = {p["id"]: p for p in prospects_rows}

    for draft in drafts:
        p = prospects_map.get(draft.get("prospect_id"), {})
        category = (p.get("category") or "").lower().strip()
        if category not in _HP_CATEGORIES:
            continue

        name = p.get("name", "Unknown")
        org = p.get("organization", "")
        subject = f"Rod — high priority draft waiting {name}"
        body = (
            f"You have a high priority outreach draft that has been waiting for review "
            f"for more than 48 hours:\n\n"
            f"{name} — {org} — {p.get('category', '')}\n\n"
            f"Open your dashboard to review: {settings.dashboard_url}"
        )
        gmail_service.send_email(to=settings.rod_email, subject=subject, body=body)
        print(f"[tracking] priority nudge sent for {name} ({org})")
