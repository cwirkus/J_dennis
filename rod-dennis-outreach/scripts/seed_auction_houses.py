import sys
import os

# Load .env before importing app modules
from pathlib import Path
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database import get_db

prospects = [
    {
        "name": "Nicolas Lowry",
        "organization": "Swann Auction Galleries",
        "category": "auction house",
        "country": "US",
        "email": "prints@swanngalleries.com",
        "phone": "(212) 254-4710",
        "website": "swanngalleries.com",
        "priority": 1,
        "status": "not_contacted",
        "notes": "Priority — October 2026 African American Art sale. Consignment inquiry. One work here establishes a public price record."
    },
    {
        "name": "Kathleen Doyle",
        "organization": "Doyle New York",
        "category": "auction house",
        "country": "US",
        "email": "info@doyle.com",
        "website": "doyle.com",
        "priority": 1,
        "status": "not_contacted",
        "notes": "American art sales. Figurative realist work fits their collector base."
    },
    {
        "name": "Arvid Knudsen",
        "organization": "Heritage Auctions",
        "category": "auction house",
        "country": "US",
        "email": "americana@ha.com",
        "website": "ha.com",
        "priority": 2,
        "status": "not_contacted",
        "notes": "African American art category. Secondary priority after Swann."
    },
]

db = get_db()

existing = db.table("prospects").select("organization").execute().data or []
existing_orgs = {row["organization"].lower().strip() for row in existing}

for p in prospects:
    org = p["organization"]
    if org.lower().strip() in existing_orgs:
        print(f"SKIP   {org} — already exists")
        continue
    db.table("prospects").insert(p).execute()
    print(f"INSERT {p['name']} / {org}")
