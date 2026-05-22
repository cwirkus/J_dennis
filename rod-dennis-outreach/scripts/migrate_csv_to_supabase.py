"""
One-time migration: loads data/prospects.csv into the Supabase prospects table.
Safe to re-run — skips rows whose email already exists in Supabase.
"""
import csv
import sys
from pathlib import Path

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database import get_db

CSV_PATH = Path(__file__).parent.parent / "data" / "prospects.csv"

FIELD_MAP = {
    "name": "name",
    "organization": "organization",
    "category": "category",
    "country": "country",
    "email": "email",
    "phone": "phone",
    "website": "website",
    "priority": "priority",
    "status": "status",
    "notes": "notes",
    "source": "source",
}


def main():
    db = get_db()

    existing_emails = {
        r["email"].lower()
        for r in (db.table("prospects").select("email").execute().data or [])
        if r.get("email")
    }
    print(f"Supabase currently has {len(existing_emails)} prospects with emails.")

    with open(CSV_PATH, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    print(f"CSV has {len(rows)} rows.")

    inserted = skipped = errors = 0
    batch = []

    for row in rows:
        email = (row.get("email") or "").strip().lower()
        if email and email in existing_emails:
            skipped += 1
            continue

        record = {}
        for csv_col, db_col in FIELD_MAP.items():
            val = row.get(csv_col, "").strip()
            if db_col == "priority":
                try:
                    record[db_col] = int(val) if val else 2
                except ValueError:
                    record[db_col] = 2
            else:
                record[db_col] = val or None

        if email:
            existing_emails.add(email)

        batch.append(record)

        if len(batch) >= 50:
            try:
                db.table("prospects").insert(batch).execute()
                inserted += len(batch)
                print(f"  Inserted batch of {len(batch)} (total so far: {inserted})")
            except Exception as e:
                errors += len(batch)
                print(f"  Batch error: {e}")
            batch = []

    if batch:
        try:
            db.table("prospects").insert(batch).execute()
            inserted += len(batch)
            print(f"  Inserted final batch of {len(batch)}")
        except Exception as e:
            errors += len(batch)
            print(f"  Final batch error: {e}")

    print(f"\nDone — inserted: {inserted}, skipped (already existed): {skipped}, errors: {errors}")


if __name__ == "__main__":
    main()
