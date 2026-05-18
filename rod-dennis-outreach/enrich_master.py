#!/usr/bin/env python3
"""
Hunter.io enrichment for JRD_COMPLETE_MASTER.csv
Outputs JRD_COMPLETE_MASTER_ENRICHED.csv with emails filled in
and a Hunter_Source column recording how each was found.
"""

import csv
import sys
import time
import requests
from pathlib import Path

HUNTER_KEY = "59f16437558b54a8ca0043fe424f12485c5b6343"
BASE = "https://api.hunter.io/v2"
IN_CSV = Path("data/JRD_COMPLETE_MASTER.csv")
OUT_CSV = Path("data/JRD_COMPLETE_MASTER_ENRICHED.csv")
DELAY = 0.5  # seconds between API calls

COLUMNS = [
    "Name", "Organization", "Category", "Country", "Email", "Phone",
    "Website", "Priority", "Status", "Notes", "Date Contacted", "Date of Last Activity",
]
OUT_COLUMNS = COLUMNS + ["Hunter_Source"]

# Hunter verifier returns "deliverable" / "accept_all" / older "valid"
VALID_RESULTS = {"deliverable", "accept_all", "valid"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def extract_domain(website: str) -> str | None:
    if not website or not website.strip():
        return None
    url = website.strip().lower()
    for prefix in ("https://", "http://"):
        if url.startswith(prefix):
            url = url[len(prefix):]
    if url.startswith("www."):
        url = url[4:]
    domain = url.split("/")[0].split("?")[0]
    return domain if domain else None


def split_name(name: str) -> tuple[str, str]:
    parts = name.strip().split()
    if not parts:
        return "", ""
    if len(parts) == 1:
        return parts[0], ""
    return parts[0], " ".join(parts[1:])


def hunter_get(endpoint: str, params: dict, retries: int = 2) -> dict | None:
    params = dict(params)
    params["api_key"] = HUNTER_KEY
    for attempt in range(retries + 1):
        try:
            r = requests.get(f"{BASE}/{endpoint}", params=params, timeout=15)
            if r.status_code == 429:
                print("  [rate-limit] sleeping 10s…")
                time.sleep(10)
                continue
            if r.status_code in (400, 401, 402, 403):
                print(f"  [hunter {r.status_code}] {r.json().get('errors', r.text)}")
                return None
            if r.status_code == 200:
                return r.json()
            return None
        except requests.RequestException as exc:
            print(f"  [error] {endpoint}: {exc}")
            if attempt < retries:
                time.sleep(1)
    return None


def find_via_email_finder(domain: str, first: str, last: str) -> str | None:
    if not last:
        return None
    data = hunter_get("email-finder", {"domain": domain, "first_name": first, "last_name": last})
    time.sleep(DELAY)
    if data:
        return data.get("data", {}).get("email") or None
    return None


def find_via_domain_search(domain: str) -> str | None:
    data = hunter_get("domain-search", {"domain": domain})
    time.sleep(DELAY)
    if data:
        emails = data.get("data", {}).get("emails", [])
        if emails:
            emails.sort(key=lambda x: x.get("confidence", 0), reverse=True)
            return emails[0].get("value") or None
    return None


def verify_email(email: str) -> bool:
    data = hunter_get("email-verifier", {"email": email})
    time.sleep(DELAY)
    if data:
        result = data.get("data", {}).get("result", "")
        status = data.get("data", {}).get("status", "")
        return result in VALID_RESULTS or status in VALID_RESULTS
    return False


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    # Credits check
    print("=" * 60)
    print("HUNTER.IO ACCOUNT")
    print("=" * 60)
    acct = hunter_get("account", {})
    if not acct:
        print("ERROR: could not reach Hunter.io API — check key.")
        sys.exit(1)
    req = acct["data"]["requests"]
    searches_start = req["searches"]["used"]
    verif_start = req["verifications"]["used"]
    print(f"  Plan       : {acct['data']['plan_name']}")
    print(f"  Searches   : {searches_start} used / {req['searches']['available']} available")
    print(f"  Verifications: {verif_start} used / {req['verifications']['available']} available")
    print()

    # Load CSV
    with open(IN_CSV, newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))

    to_enrich = [r for r in rows if not r.get("Email", "").strip()]
    print(f"Total rows         : {len(rows)}")
    print(f"Already have email : {len(rows) - len(to_enrich)}")
    print(f"Need enrichment    : {len(to_enrich)}")
    print()

    # Rough credit warning
    searches_avail = req["searches"]["available"]
    if len(to_enrich) > searches_avail:
        print(
            f"WARNING: {len(to_enrich)} contacts but only {searches_avail} searches available. "
            "Domain Search fallbacks will be skipped once budget is exhausted.\n"
        )
                     
    # Track credit budget so we don't blow out Domain Search fallbacks
    searches_used_this_run = 0
    searches_budget = searches_avail

    stats = {
        "pre_existing": 0,
        "email_finder_verified": 0,
        "domain_search_verified": 0,
        "not_found": 0,
        "no_domain": 0,
        "errors": 0,
    }
    out_rows: list[dict] = []

    for i, row in enumerate(rows):
        out_row = {col: row.get(col, "") for col in COLUMNS}

        # Already has email
        if row.get("Email", "").strip():
            out_row["Hunter_Source"] = "pre_existing"
            stats["pre_existing"] += 1
            out_rows.append(out_row)
            continue

        # No domain to try
        domain = extract_domain(row.get("Website", ""))
        if not domain:
            out_row["Hunter_Source"] = "no_domain"
            stats["no_domain"] += 1
            out_rows.append(out_row)
            continue

        name = row.get("Name", "")
        first, last = split_name(name)
        label = f"[{i + 1}/{len(rows)}] {name[:30]:<30} | {domain}"

        found_email: str | None = None
        source = "not_found"

        # ── Email Finder ──────────────────────────────────────────────────
        if searches_used_this_run < searches_budget:
            try:
                found_email = find_via_email_finder(domain, first, last)
                searches_used_this_run += 1
            except Exception as exc:
                print(f"{label}\n  [error] email-finder: {exc}")
                stats["errors"] += 1

            if found_email:
                try:
                    ok = verify_email(found_email)
                except Exception as exc:
                    print(f"  [error] verifier: {exc}")
                    ok = False

                if ok:
                    source = "email_finder_verified"
                    print(f"{label}  → EF ✓  {found_email}")
                else:
                    # Unverified — discard and fall through to Domain Search
                    found_email = None

        # ── Domain Search fallback ────────────────────────────────────────
        if not found_email and searches_used_this_run < searches_budget:
            try:
                found_email = find_via_domain_search(domain)
                searches_used_this_run += 1
            except Exception as exc:
                print(f"  [error] domain-search: {exc}")
                stats["errors"] += 1

            if found_email:
                try:
                    ok = verify_email(found_email)
                except Exception as exc:
                    print(f"  [error] verifier: {exc}")
                    ok = False

                if ok:
                    source = "domain_search_verified"
                    print(f"{label}  → DS ✓  {found_email}")
                else:
                    found_email = None

        if not found_email:
            print(f"{label}  → not found")

        if found_email:
            out_row["Email"] = found_email
        out_row["Hunter_Source"] = source
        stats[source] += 1
        out_rows.append(out_row)

    # Write output CSV
    with open(OUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=OUT_COLUMNS)
        writer.writeheader()
        writer.writerows(out_rows)

    # Final credit check
    acct2 = hunter_get("account", {})
    s_used_run = v_used_run = "?"
    if acct2:
        req2 = acct2["data"]["requests"]
        s_used_run = req2["searches"]["used"] - searches_start
        v_used_run = req2["verifications"]["used"] - verif_start

    total_new = stats["email_finder_verified"] + stats["domain_search_verified"]
    enrichable = len(to_enrich) - stats["no_domain"]

    print()
    print("=" * 60)
    print("ENRICHMENT SUMMARY")
    print("=" * 60)
    print(f"  Output file          : {OUT_CSV}")
    print(f"  Total rows           : {len(rows)}")
    print(f"  Pre-existing emails  : {stats['pre_existing']}")
    print(f"  Found via Email Finder (verified): {stats['email_finder_verified']}")
    print(f"  Found via Domain Search (verified): {stats['domain_search_verified']}")
    print(f"  Not found            : {stats['not_found']}")
    print(f"  No domain to try     : {stats['no_domain']}")
    print(f"  Errors               : {stats['errors']}")
    print(f"  Hit rate             : {total_new}/{enrichable} "
          f"({100 * total_new // max(1, enrichable)}%)")
    print()
    print(f"  Searches used this run      : {s_used_run}")
    print(f"  Verifications used this run : {v_used_run}")


if __name__ == "__main__":
    main()
