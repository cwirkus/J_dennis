import json
import re
from datetime import datetime, timezone

import anthropic

from app.config import settings
from app.database import get_db

DISCOVERY_PROMPT = """You are researching art world contacts for J. Rodney Dennis, a classical realist painter. His work: Old Master technique applied to African American figurative narrative subjects. 2024 ARC Salon Chairman's Choice Award. Wall Street Journal featured. Florence Academy of Art trained. Paintings start at $25,000.

Find NEW contacts that are NOT in the provided existing list who would be strong prospects for Rod's work:

Galleries that represent classical realism or Old Master technique painters
Galleries or advisors focused on African American fine art
Museum curators actively acquiring figurative realist work
Art foundations that fund or collect this type of work
Corporate collections with African American art programs
Private collectors known to collect figurative realism or African American art
International institutions with diaspora art programs

For each prospect return these exact fields:
name, organization, category, country, email, phone, website, priority (1 or 2), notes (why they are relevant to Rod specifically)
Return ONLY a valid JSON array. No preamble, no explanation, no markdown. Maximum 20 prospects per run."""


def _fetch_all_existing() -> list[dict]:
    db = get_db()
    all_rows: list[dict] = []
    offset = 0
    chunk = 1000
    while True:
        rows = (
            db.table("prospects")
            .select("name, organization")
            .range(offset, offset + chunk - 1)
            .execute()
            .data or []
        )
        all_rows.extend(rows)
        if len(rows) < chunk:
            break
        offset += chunk
    return all_rows


def _log_run(run_at: str, found: int, added: int) -> None:
    try:
        get_db().table("discovery_log").insert({
            "source": "claude_discovery",
            "prospects_found": found,
            "prospects_added": added,
            "run_at": run_at,
        }).execute()
    except Exception as exc:
        print(f"[discovery_agent] log error: {exc}")


def _parse_response(raw: str) -> list | None:
    raw = re.sub(r"^```[a-z]*\n?", "", raw.strip(), flags=re.MULTILINE)
    raw = re.sub(r"\n?```$", "", raw.strip(), flags=re.MULTILINE)
    try:
        parsed = json.loads(raw.strip())
        return parsed if isinstance(parsed, list) else None
    except json.JSONDecodeError:
        return None


async def run_discovery() -> dict:
    run_at = datetime.now(timezone.utc).isoformat()
    try:
        existing = _fetch_all_existing()
        existing_list = "\n".join(
            f"{r.get('name', '')} / {r.get('organization', '')}"
            for r in existing
            if r.get("name") or r.get("organization")
        ) or "None"

        existing_set = {
            (r.get("name", "").lower().strip(), r.get("organization", "").lower().strip())
            for r in existing
        }

        user_msg = (
            f"Existing prospects to exclude:\n{existing_list}\n\n"
            "Find 20 new art world prospects for Rod."
        )

        client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

        async def _call(extra: str = "") -> str:
            msg = await client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=4096,
                system=DISCOVERY_PROMPT,
                messages=[{"role": "user", "content": user_msg + extra}],
            )
            return msg.content[0].text

        prospects = _parse_response(await _call())
        if prospects is None:
            prospects = _parse_response(
                await _call(" Respond with ONLY a valid JSON array, no other text.")
            )
        if prospects is None:
            print("[discovery_agent] malformed JSON after retry — aborting")
            _log_run(run_at, 0, 0)
            return {"prospects_found": 0, "prospects_added": 0, "new_prospects": []}

        prospects_found = len(prospects)
        prospects_added = 0
        new_prospects: list[dict] = []
        db = get_db()

        for p in prospects:
            name = str(p.get("name") or "").strip()
            org = str(p.get("organization") or "").strip()
            if not name and not org:
                continue
            key = (name.lower(), org.lower())
            if key in existing_set:
                continue
            existing_set.add(key)

            try:
                priority = int(p.get("priority", 2))
                if priority not in (1, 2):
                    priority = 2
            except (TypeError, ValueError):
                priority = 2

            db.table("prospects").insert({
                "name": name,
                "organization": org,
                "category": str(p.get("category") or ""),
                "country": str(p.get("country") or ""),
                "email": str(p.get("email") or ""),
                "phone": str(p.get("phone") or ""),
                "website": str(p.get("website") or ""),
                "priority": priority,
                "notes": str(p.get("notes") or ""),
                "source": "discovery_agent",
                "status": "not_contacted",
            }).execute()
            prospects_added += 1
            new_prospects.append({
                "name": name,
                "organization": org,
                "country": str(p.get("country") or ""),
            })

        _log_run(run_at, prospects_found, prospects_added)
        return {
            "prospects_found": prospects_found,
            "prospects_added": prospects_added,
            "new_prospects": new_prospects,
        }

    except Exception as exc:
        print(f"[discovery_agent] error: {exc}")
        _log_run(run_at, 0, 0)
        return {"prospects_found": 0, "prospects_added": 0, "new_prospects": []}
