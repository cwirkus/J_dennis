import csv
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from app.config import settings

COLUMNS = [
    "name", "organization", "category", "country", "email", "phone",
    "website", "priority", "status", "notes", "date_contacted",
    "last_activity", "source",
]


def _path() -> Path:
    return Path(settings.data_path)


def ensure_csv_exists() -> None:
    p = _path()
    p.parent.mkdir(parents=True, exist_ok=True)
    if not p.exists():
        with open(p, "w", newline="") as f:
            csv.DictWriter(f, fieldnames=COLUMNS).writeheader()


def get_all_prospects() -> list[dict]:
    ensure_csv_exists()
    with open(_path(), newline="") as f:
        return list(csv.DictReader(f))


def find_by_email(email: str) -> dict | None:
    for row in get_all_prospects():
        if row.get("email", "").lower() == email.lower():
            return row
    return None


def find_by_status(status: str) -> list[dict]:
    return [r for r in get_all_prospects() if r.get("status") == status]


def append_prospect(prospect: dict) -> bool:
    """Returns True if added, False if skipped (duplicate email)."""
    email = prospect.get("email", "")
    if email and find_by_email(email):
        return False
    row = {col: prospect.get(col, "") for col in COLUMNS}
    with open(_path(), "a", newline="") as f:
        csv.DictWriter(f, fieldnames=COLUMNS).writerow(row)
    return True


def update_prospect(email: str, updates: dict) -> bool:
    """Returns True if a matching row was found and updated."""
    rows = get_all_prospects()
    found = False
    for row in rows:
        if row.get("email", "").lower() == email.lower():
            row.update({k: v for k, v in updates.items() if k in COLUMNS})
            found = True
            break
    if not found:
        return False
    with open(_path(), "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    return True


def delete_by_email(email: str) -> bool:
    """Returns True if a row was removed."""
    rows = get_all_prospects()
    filtered = [r for r in rows if r.get("email", "").lower() != email.lower()]
    if len(filtered) == len(rows):
        return False
    with open(_path(), "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(filtered)
    return True


# ---------------------------------------------------------------------------
# Outreach drafts
# ---------------------------------------------------------------------------

DRAFT_COLUMNS = [
    "id", "prospect_email", "subject", "body",
    "status", "created_at", "approved_at", "sent_at", "opened", "replied",
]


def _drafts_path() -> Path:
    return Path(settings.drafts_path)


def ensure_drafts_csv_exists() -> None:
    p = _drafts_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    if not p.exists():
        with open(p, "w", newline="") as f:
            csv.DictWriter(f, fieldnames=DRAFT_COLUMNS).writeheader()


def get_all_drafts() -> list[dict]:
    ensure_drafts_csv_exists()
    with open(_drafts_path(), newline="") as f:
        return list(csv.DictReader(f))


def append_draft(draft: dict) -> dict:
    ensure_drafts_csv_exists()
    row = {col: draft.get(col, "") for col in DRAFT_COLUMNS}
    row["id"] = str(uuid.uuid4())
    row["created_at"] = datetime.now(timezone.utc).isoformat()
    with open(_drafts_path(), "a", newline="") as f:
        csv.DictWriter(f, fieldnames=DRAFT_COLUMNS).writerow(row)
    return row


def get_drafts_by_status(status: str) -> list[dict]:
    return [r for r in get_all_drafts() if r.get("status") == status]


def get_draft_by_id(draft_id: str) -> dict | None:
    for row in get_all_drafts():
        if row.get("id") == draft_id:
            return row
    return None


def update_draft(draft_id: str, updates: dict) -> bool:
    rows = get_all_drafts()
    found = False
    for row in rows:
        if row.get("id") == draft_id:
            row.update({k: v for k, v in updates.items() if k in DRAFT_COLUMNS})
            found = True
            break
    if not found:
        return False
    with open(_drafts_path(), "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=DRAFT_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    return True


# ---------------------------------------------------------------------------
# Inbound messages
# ---------------------------------------------------------------------------

INBOUND_COLUMNS = [
    "id", "sender_name", "sender_email", "channel", "message",
    "draft_response", "status", "sent_at", "created_at", "high_priority",
    "prospect_org", "original_subject", "original_body",
]


def _inbox_path() -> Path:
    return Path(settings.inbox_path)


def ensure_inbound_csv_exists() -> None:
    p = _inbox_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    if not p.exists():
        with open(p, "w", newline="") as f:
            csv.DictWriter(f, fieldnames=INBOUND_COLUMNS).writeheader()
        return
    # Migrate: add any missing columns to existing file
    with open(p, newline="") as f:
        reader = csv.DictReader(f)
        existing_cols = list(reader.fieldnames or [])
        rows = list(reader)
    if existing_cols != INBOUND_COLUMNS:
        with open(p, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=INBOUND_COLUMNS)
            writer.writeheader()
            for row in rows:
                writer.writerow({col: row.get(col, "") for col in INBOUND_COLUMNS})


def _get_all_inbound() -> list[dict]:
    ensure_inbound_csv_exists()
    with open(_inbox_path(), newline="") as f:
        return list(csv.DictReader(f))


def append_inbound(message: dict) -> dict:
    ensure_inbound_csv_exists()
    row = {col: message.get(col, "") for col in INBOUND_COLUMNS}
    row["id"] = str(uuid.uuid4())
    row["created_at"] = datetime.now(timezone.utc).isoformat()
    with open(_inbox_path(), "a", newline="") as f:
        csv.DictWriter(f, fieldnames=INBOUND_COLUMNS).writerow(row)
    return row


def get_inbound_by_status(status: str) -> list[dict]:
    return [r for r in _get_all_inbound() if r.get("status") == status]


def get_inbound_by_id(message_id: str) -> dict | None:
    for row in _get_all_inbound():
        if row.get("id") == message_id:
            return row
    return None


def update_inbound(message_id: str, updates: dict) -> bool:
    rows = _get_all_inbound()
    found = False
    for row in rows:
        if row.get("id") == message_id:
            row.update({k: v for k, v in updates.items() if k in INBOUND_COLUMNS})
            found = True
            break
    if not found:
        return False
    with open(_inbox_path(), "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=INBOUND_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    return True


def delete_inbound(message_id: str) -> bool:
    rows = _get_all_inbound()
    filtered = [r for r in rows if r.get("id") != message_id]
    if len(filtered) == len(rows):
        return False
    with open(_inbox_path(), "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=INBOUND_COLUMNS)
        writer.writeheader()
        writer.writerows(filtered)
    return True


# ---------------------------------------------------------------------------
# Discovery log
# ---------------------------------------------------------------------------

DISCOVERY_LOG_COLUMNS = ["id", "source", "prospects_found", "prospects_added", "run_at"]


def _discovery_log_path() -> Path:
    return Path(settings.discovery_log_path)


def ensure_discovery_log_exists() -> None:
    p = _discovery_log_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    if not p.exists():
        with open(p, "w", newline="") as f:
            csv.DictWriter(f, fieldnames=DISCOVERY_LOG_COLUMNS).writeheader()


def append_discovery_log(entry: dict) -> dict:
    ensure_discovery_log_exists()
    row = {col: entry.get(col, "") for col in DISCOVERY_LOG_COLUMNS}
    row["id"] = str(uuid.uuid4())
    row["run_at"] = entry.get("run_at") or datetime.now(timezone.utc).isoformat()
    with open(_discovery_log_path(), "a", newline="") as f:
        csv.DictWriter(f, fieldnames=DISCOVERY_LOG_COLUMNS).writerow(row)
    return row


def get_discovery_log() -> list[dict]:
    ensure_discovery_log_exists()
    with open(_discovery_log_path(), newline="") as f:
        rows = list(csv.DictReader(f))
    return list(reversed(rows))


# ---------------------------------------------------------------------------
# Social drafts
# ---------------------------------------------------------------------------

SOCIAL_DRAFT_COLUMNS = [
    "id", "platform", "content", "trigger_event", "status", "approved_at", "created_at",
]


def _social_drafts_path() -> Path:
    return Path(settings.social_drafts_path)


def ensure_social_drafts_exists() -> None:
    p = _social_drafts_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    if not p.exists():
        with open(p, "w", newline="") as f:
            csv.DictWriter(f, fieldnames=SOCIAL_DRAFT_COLUMNS).writeheader()


def append_social_draft(draft: dict) -> dict:
    ensure_social_drafts_exists()
    row = {col: draft.get(col, "") for col in SOCIAL_DRAFT_COLUMNS}
    row["id"] = str(uuid.uuid4())
    row["created_at"] = datetime.now(timezone.utc).isoformat()
    with open(_social_drafts_path(), "a", newline="") as f:
        csv.DictWriter(f, fieldnames=SOCIAL_DRAFT_COLUMNS).writerow(row)
    return row


def get_social_drafts_by_status(status: str) -> list[dict]:
    ensure_social_drafts_exists()
    with open(_social_drafts_path(), newline="") as f:
        return [r for r in csv.DictReader(f) if r.get("status") == status]


def get_social_draft_by_id(draft_id: str) -> dict | None:
    ensure_social_drafts_exists()
    with open(_social_drafts_path(), newline="") as f:
        for row in csv.DictReader(f):
            if row.get("id") == draft_id:
                return row
    return None


def update_social_draft(draft_id: str, updates: dict) -> bool:
    ensure_social_drafts_exists()
    rows = []
    with open(_social_drafts_path(), newline="") as f:
        rows = list(csv.DictReader(f))
    found = False
    for row in rows:
        if row.get("id") == draft_id:
            row.update({k: v for k, v in updates.items() if k in SOCIAL_DRAFT_COLUMNS})
            found = True
            break
    if not found:
        return False
    with open(_social_drafts_path(), "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=SOCIAL_DRAFT_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    return True


def delete_social_draft(draft_id: str) -> bool:
    ensure_social_drafts_exists()
    with open(_social_drafts_path(), newline="") as f:
        rows = list(csv.DictReader(f))
    filtered = [r for r in rows if r.get("id") != draft_id]
    if len(filtered) == len(rows):
        return False
    with open(_social_drafts_path(), "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=SOCIAL_DRAFT_COLUMNS)
        writer.writeheader()
        writer.writerows(filtered)
    return True
