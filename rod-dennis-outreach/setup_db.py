#!/usr/bin/env python3
"""
Phase 2, Step 1 — Supabase schema setup and CSV import
for J. Rodney Dennis Art Market Outreach System.

Usage:
    python setup_db.py

Requires:  pip install supabase python-dotenv requests
"""

import csv
import os
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# ── Config ──────────────────────────────────────────────────────────────────
SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
PROJECT_REF  = SUPABASE_URL.split("//")[1].split(".")[0] if SUPABASE_URL else ""
CSV_PATH     = Path(__file__).parent / "data" / "JRD_COMPLETE_MASTER_ENRICHED_V2.csv"

if not SUPABASE_URL or not SUPABASE_KEY:
    print("✗  SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set in .env")
    sys.exit(1)

# ── Connect ──────────────────────────────────────────────────────────────────
try:
    from supabase import create_client
    client = create_client(SUPABASE_URL, SUPABASE_KEY)
    print("✓  Connected to Supabase")
except ImportError:
    print("✗  supabase not installed.  Run: pip install supabase")
    sys.exit(1)
except Exception as exc:
    print(f"✗  Supabase connection failed: {exc}")
    sys.exit(1)

# ── Schema SQL ───────────────────────────────────────────────────────────────
SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS prospects (
  id             uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  name           text,
  organization   text,
  category       text,
  country        text,
  email          text,
  phone          text,
  website        text,
  priority       int         DEFAULT 2,
  status         text        DEFAULT 'not_contacted',
  notes          text,
  date_contacted timestamptz,
  last_activity  timestamptz,
  source         text        DEFAULT 'master_import',
  hunter_source  text,
  created_at     timestamptz DEFAULT now()
);

CREATE TABLE IF NOT EXISTS outreach_drafts (
  id          uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  prospect_id uuid        REFERENCES prospects(id) ON DELETE CASCADE,
  subject     text,
  body        text,
  status      text        DEFAULT 'pending',
  approved_at timestamptz,
  sent_at     timestamptz,
  opened      bool        DEFAULT false,
  replied     bool        DEFAULT false,
  created_at  timestamptz DEFAULT now()
);

CREATE TABLE IF NOT EXISTS social_drafts (
  id            uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  platform      text,
  content       text,
  trigger_event text,
  status        text        DEFAULT 'pending',
  approved_at   timestamptz,
  created_at    timestamptz DEFAULT now()
);

CREATE TABLE IF NOT EXISTS inbound_messages (
  id             uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  sender_name    text,
  sender_email   text,
  channel        text,
  message        text,
  draft_response text,
  status         text        DEFAULT 'pending',
  sent_at        timestamptz,
  created_at     timestamptz DEFAULT now()
);

CREATE TABLE IF NOT EXISTS discovery_log (
  id               uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  source           text,
  prospects_found  int,
  prospects_added  int,
  run_at           timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_prospects_status      ON prospects(status);
CREATE INDEX IF NOT EXISTS idx_prospects_priority    ON prospects(priority);
CREATE INDEX IF NOT EXISTS idx_prospects_country     ON prospects(country);
CREATE INDEX IF NOT EXISTS idx_od_status             ON outreach_drafts(status);
CREATE INDEX IF NOT EXISTS idx_od_prospect_id        ON outreach_drafts(prospect_id);
"""

ADD_HUNTER_SOURCE = (
    "ALTER TABLE prospects ADD COLUMN IF NOT EXISTS hunter_source text;"
)

# ── Helpers ──────────────────────────────────────────────────────────────────

def _table_exists(table: str) -> bool:
    """Return False on any 'table not found' signal from PostgREST or PostgreSQL."""
    try:
        client.table(table).select("id").limit(0).execute()
        return True
    except Exception as exc:
        msg = str(exc)
        # PostgREST: PGRST205 = table not in schema cache (i.e. does not exist)
        # PostgreSQL native: 42P01 = undefined_table
        if (
            "PGRST205" in msg
            or "42P01" in msg
            or "does not exist" in msg.lower()
            or "schema cache" in msg.lower()
        ):
            return False
        # Any other error (auth etc.) — don't assume the table is missing
        print(f"  ⚠  Unexpected error checking table '{table}': {exc}")
        return True


def _normalize_status(raw: str) -> str:
    cleaned = raw.strip().lower().replace(" ", "_")
    return cleaned if cleaned else "not_contacted"


def _parse_int(raw: str, default: int = 2) -> int:
    try:
        return int(raw.strip())
    except (ValueError, AttributeError):
        return default


def _parse_date(raw: str):
    if not raw or not raw.strip():
        return None
    for fmt in ("%m/%d/%Y", "%Y-%m-%d", "%d/%m/%Y", "%B %d, %Y", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(raw.strip(), fmt).isoformat()
        except ValueError:
            pass
    return None


# ── Step 2: Schema ───────────────────────────────────────────────────────────

SQL_EDITOR_URL = (
    f"https://supabase.com/dashboard/project/{PROJECT_REF}/sql/new"
)


def _print_manual_sql(sql: str, title: str = "MANUAL ACTION REQUIRED") -> None:
    bar = "═" * 66
    print(f"\n{bar}")
    print(f"  {title}")
    print(f"  Open this URL and paste the SQL below:")
    print(f"  {SQL_EDITOR_URL}")
    print(bar)
    print()
    print(sql.strip())
    print()
    print(bar)


def setup_schema():
    print("\n─── STEP 2: Database Schema ────────────────────────────────────────")

    if _table_exists("prospects"):
        print("  ✓  prospects table exists — will add hunter_source if missing")
        print()
        print("  If the hunter_source column is missing, run this SQL once:")
        print(f"  {SQL_EDITOR_URL}")
        print()
        print(f"  {ADD_HUNTER_SOURCE}")
        return

    # Tables don't exist — DDL requires either a PAT (Management API)
    # or a direct PostgreSQL password (psycopg2). The service role key
    # is a JWT scoped to PostgREST and cannot execute DDL.
    _print_manual_sql(
        SCHEMA_SQL,
        title="STEP 2 — Create tables (one-time setup needed)",
    )
    print("After running the SQL, re-run this script to import data.")
    sys.exit(0)


# ── Step 3: CSV Import ────────────────────────────────────────────────────────

def import_csv():
    print("\n─── STEP 3: CSV Import ─────────────────────────────────────────────")

    if not CSV_PATH.exists():
        print(f"  ✗  CSV not found at {CSV_PATH}")
        return 0

    # Fetch existing (name, organization) pairs for dedup
    print("  Fetching existing records for duplicate check…")
    existing: set[tuple] = set()
    try:
        offset = 0
        page   = 1000
        while True:
            res = (
                client.table("prospects")
                .select("name,organization")
                .range(offset, offset + page - 1)
                .execute()
            )
            for row in res.data:
                existing.add((row.get("name") or "", row.get("organization") or ""))
            if len(res.data) < page:
                break
            offset += page
    except Exception as exc:
        print(f"  ⚠  Could not pre-fetch existing rows: {exc}")

    print(f"  Existing records: {len(existing)}")

    # Parse CSV
    to_insert     = []
    skipped_blank = 0
    skipped_dup   = 0

    with open(CSV_PATH, newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            name = (row.get("Name") or "").strip()
            org  = (row.get("Organization") or "").strip()

            if not name and not org:
                skipped_blank += 1
                continue

            key = (name, org)
            if key in existing:
                skipped_dup += 1
                continue

            to_insert.append({
                "name":           name  or None,
                "organization":   org   or None,
                "category":       (row.get("Category") or "").strip() or None,
                "country":        (row.get("Country") or "").strip() or None,
                "email":          (row.get("Email") or "").strip() or None,
                "phone":          (row.get("Phone") or "").strip() or None,
                "website":        (row.get("Website") or "").strip() or None,
                "priority":       _parse_int(row.get("Priority") or "", default=2),
                "status":         _normalize_status(row.get("Status") or ""),
                "notes":          (row.get("Notes") or "").strip() or None,
                "date_contacted": _parse_date(row.get("Date Contacted") or ""),
                "last_activity":  _parse_date(row.get("Date of Last Activity") or ""),
                "source":         "master_import",
                "hunter_source":  (row.get("Hunter_Source") or "").strip() or None,
            })
            existing.add(key)   # prevent within-batch dupes

    print(f"  To insert:               {len(to_insert)}")
    print(f"  Skipped (blank name+org): {skipped_blank}")
    print(f"  Skipped (duplicates):     {skipped_dup}")

    if not to_insert:
        print("  ✓  Nothing new to import.")
        return 0

    # Batch insert
    BATCH = 100
    inserted = 0
    errors   = 0

    for i in range(0, len(to_insert), BATCH):
        batch = to_insert[i : i + BATCH]
        batch_num = i // BATCH + 1
        try:
            res = client.table("prospects").insert(batch).execute()
            inserted += len(res.data)
            print(f"  Batch {batch_num:3d} — inserted {len(res.data):3d} rows")
        except Exception as exc:
            print(f"  ✗  Batch {batch_num} failed: {exc}")
            errors += len(batch)

    print(f"\n  ✓  Import complete — {inserted} inserted, {errors} errors")
    return inserted


# ── Step 4: Verification ──────────────────────────────────────────────────────

def _fetch_all(columns: str) -> list[dict]:
    """Paginate through all rows, bypassing the default 1,000-row REST limit."""
    rows: list[dict] = []
    page = 1000
    offset = 0
    while True:
        res = (
            client.table("prospects")
            .select(columns)
            .range(offset, offset + page - 1)
            .execute()
        )
        rows.extend(res.data)
        if len(res.data) < page:
            break
        offset += page
    return rows


def verify():
    print("\n─── STEP 4: Verification ────────────────────────────────────────────")

    try:
        # Total — server-side count, no row cap
        res = client.table("prospects").select("*", count="exact").execute()
        total = res.count
        print(f"\n  Total prospects in database : {total}")

        # All rows for breakdowns (paginated so we always get every record)
        rows = _fetch_all("country,status,priority,email")

        # Count by country (top 10)
        countries = Counter(r.get("country") for r in rows if r.get("country"))
        print("\n  Top 10 Countries:")
        for country, cnt in countries.most_common(10):
            print(f"    {country:<30} {cnt:>4}")

        # Count by status
        statuses = Counter(r.get("status") for r in rows)
        print("\n  By Status:")
        for status, cnt in statuses.most_common():
            label = status or "(null)"
            print(f"    {label:<30} {cnt:>4}")

        # Count by priority
        priorities = Counter(r.get("priority") for r in rows)
        print("\n  By Priority:")
        for prio, cnt in sorted(priorities.items(), key=lambda x: (x[0] is None, x[0])):
            label = str(prio) if prio is not None else "(null)"
            print(f"    Priority {label:<25} {cnt:>4}")

        # With email — server-side count
        email_res = (
            client.table("prospects")
            .select("*", count="exact")
            .not_.is_("email", "null")
            .execute()
        )
        print(f"\n  Prospects with email        : {email_res.count} / {total}")

    except Exception as exc:
        print(f"  ✗  Verification error: {exc}")


# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    bar = "═" * 62
    print(bar)
    print("  J. Rodney Dennis — Art Market Outreach System")
    print("  Phase 2, Step 1: Database Setup & Import")
    print(bar)

    setup_schema()
    import_csv()
    verify()

    print(f"\n{bar}")
    print("  All done.")
    print(bar)
