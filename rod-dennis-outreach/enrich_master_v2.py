#!/usr/bin/env python3
"""
Second enrichment pass — 5 strategies for the 334 still-missing emails.
Input:  data/JRD_COMPLETE_MASTER_ENRICHED.csv
Output: data/JRD_COMPLETE_MASTER_ENRICHED_V2.csv
"""

import csv
import re
import sys
import time
import requests
from pathlib import Path

HUNTER_KEY = "59f16437558b54a8ca0043fe424f12485c5b6343"
BASE = "https://api.hunter.io/v2"
IN_CSV  = Path("data/JRD_COMPLETE_MASTER_ENRICHED.csv")
OUT_CSV = Path("data/JRD_COMPLETE_MASTER_ENRICHED_V2.csv")
DELAY = 0.5

COLUMNS = [
    "Name", "Organization", "Category", "Country", "Email", "Phone",
    "Website", "Priority", "Status", "Notes", "Date Contacted",
    "Date of Last Activity", "Hunter_Source",
]

VALID_RESULTS = {"deliverable", "accept_all", "valid"}

TITLE_RE = re.compile(
    r'\b(Dr\.?|Ph\.?D\.?|MBE\.?|OBE\.?|Prof\.?|Jr\.?|Sr\.?|II|III|Esq\.?)\b',
    re.IGNORECASE,
)

ORG_STOP = {
    "gallery", "museum", "foundation", "center", "centre", "institute",
    "art", "fine", "contemporary", "collection", "the", "of", "and", "for",
    "arts", "cultural", "culture", "international", "national", "american",
}


# ---------------------------------------------------------------------------
# HTTP helper
# ---------------------------------------------------------------------------

def hunter_get(endpoint: str, params: dict, retries: int = 2) -> dict | None:
    p = dict(params)
    p["api_key"] = HUNTER_KEY
    for attempt in range(retries + 1):
        try:
            r = requests.get(f"{BASE}/{endpoint}", params=p, timeout=15)
            if r.status_code == 429:
                print("  [rate-limit] sleeping 10s…")
                time.sleep(10)
                continue
            if r.status_code in (400, 401, 402, 403):
                detail = ""
                try:
                    detail = r.json().get("errors", r.text)
                except Exception:
                    detail = r.text
                print(f"  [hunter {r.status_code}] {detail}")
                return None
            if r.status_code == 200:
                return r.json()
            return None
        except requests.RequestException as exc:
            print(f"  [error] {endpoint}: {exc}")
            if attempt < retries:
                time.sleep(1)
    return None


# ---------------------------------------------------------------------------
# Shared primitives
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


def do_email_finder(domain: str, first: str, last: str) -> str | None:
    if not domain or not last:
        return None
    data = hunter_get("email-finder", {"domain": domain, "first_name": first, "last_name": last})
    time.sleep(DELAY)
    if data:
        return data.get("data", {}).get("email") or None
    return None


def do_domain_search(domain: str) -> str | None:
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


def try_email(email: str | None) -> str | None:
    """Verify email and return it if valid, else None."""
    if not email:
        return None
    return email if verify_email(email) else None


# ---------------------------------------------------------------------------
# Strategy helpers
# ---------------------------------------------------------------------------

def clean_name(name: str) -> str:
    cleaned = TITLE_RE.sub("", name)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def alt_domains(domain: str) -> list[str]:
    """Swap TLD extensions; no-www/www variants are treated the same by Hunter."""
    variants = []
    if domain.endswith(".org"):
        variants.append(domain[:-4] + ".com")
    elif domain.endswith(".com"):
        variants.append(domain[:-4] + ".org")
    elif domain.endswith(".net"):
        variants.append(domain[:-4] + ".com")
        variants.append(domain[:-4] + ".org")
    elif domain.endswith(".edu"):
        variants.append(domain[:-4] + ".org")
        variants.append(domain[:-4] + ".com")
    else:
        # Try .com and .org as generic fallbacks
        base = domain.rsplit(".", 1)[0]
        variants.extend([base + ".com", base + ".org"])
    # Deduplicate and exclude original
    return [v for v in dict.fromkeys(variants) if v != domain]


def org_to_domains(org: str) -> list[str]:
    """Derive candidate domains from organization name."""
    words = re.sub(r"[^\w\s]", "", org.lower()).split()
    filtered = [w for w in words if w not in ORG_STOP]
    slug = "".join(filtered)
    if len(slug) < 3:
        return []
    return [f"{slug}.com", f"{slug}.org", f"{slug}.net"]


# ---------------------------------------------------------------------------
# Five strategies
# ---------------------------------------------------------------------------

def strategy1(domain: str, name: str) -> tuple[str | None, str]:
    """Clean name, retry Email Finder."""
    cleaned = clean_name(name)
    first, last = split_name(cleaned)
    email = try_email(do_email_finder(domain, first, last))
    return email, "strategy1_verified"


def strategy2(domain: str) -> tuple[str | None, str]:
    """Alternate domain extensions via Domain Search."""
    for alt in alt_domains(domain):
        email = try_email(do_domain_search(alt))
        if email:
            return email, "strategy2_verified"
    return None, ""


def strategy3(org: str) -> tuple[str | None, str]:
    """Build domain from org name, try Domain Search."""
    for candidate in org_to_domains(org):
        email = try_email(do_domain_search(candidate))
        if email:
            return email, "strategy3_verified"
    return None, ""


def strategy4(domain: str) -> tuple[str | None, str]:
    """Domain Search on original domain (no name matching)."""
    email = try_email(do_domain_search(domain))
    return email, "strategy4_verified"


def strategy5(domain: str, name: str) -> tuple[str | None, str]:
    """Email Finder with first name + single-letter last name (fuzzy trigger)."""
    cleaned = clean_name(name)
    first, _ = split_name(cleaned)
    if not first or not domain:
        return None, ""
    data = hunter_get(
        "email-finder",
        {"domain": domain, "first_name": first, "last_name": first[0]},
    )
    time.sleep(DELAY)
    if data:
        d = data.get("data", {})
        email = d.get("email")
        score = d.get("score", 0)
        if email and score >= 70:
            verified = try_email(email)
            return verified, "strategy5_verified"
    return None, ""


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def credit_report(label: str) -> dict:
    print(f"\n{'=' * 60}")
    print(f"HUNTER.IO CREDITS — {label}")
    print("=" * 60)
    acct = hunter_get("account", {})
    if not acct:
        print("  ERROR: could not reach Hunter.io API")
        return {}
    req = acct["data"]["requests"]
    print(f"  Searches      : {req['searches']['used']} used / {req['searches']['available']} available")
    print(f"  Verifications : {req['verifications']['used']} used / {req['verifications']['available']} available")
    return req


def main() -> None:
    req_before = credit_report("BEFORE")
    searches_start   = req_before.get("searches",      {}).get("used", 0)
    verif_start      = req_before.get("verifications", {}).get("used", 0)

    # Load
    with open(IN_CSV, newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))

    retry_rows = [r for r in rows if not r.get("Email", "").strip()]
    print(f"\nTotal rows       : {len(rows)}")
    print(f"Retrying (no email): {len(retry_rows)}\n")

    stats = {
        "strategy1_verified": 0,
        "strategy2_verified": 0,
        "strategy3_verified": 0,
        "strategy4_verified": 0,
        "strategy5_verified": 0,
        "still_not_found":   0,
        "skipped":           0,
    }

    # Build output as a dict keyed by row index for in-place update
    out_rows = list(rows)  # copy

    retry_indices = [i for i, r in enumerate(rows) if not r.get("Email", "").strip()]

    for seq, idx in enumerate(retry_indices, 1):
        row = rows[idx]
        out_row = dict(row)

        name = row.get("Name", "").strip()
        org  = row.get("Organization", "").strip()
        website = row.get("Website", "").strip()
        domain = extract_domain(website)

        label = f"[{seq}/{len(retry_indices)}] {name[:28]:<28} | {org[:28]:<28}"
        print(label, end="  ", flush=True)

        found_email: str | None = None
        source = "still_not_found"

        # ── Strategy 4 shortcut: name == org (no real person name) ─────────
        name_is_generic = (name.lower() == org.lower()) or not any(
            c.isalpha() and c == c.upper() and i > 0
            for i, c in enumerate(name)
        )

        if name_is_generic and domain:
            found_email, source = strategy4(domain)
            if found_email:
                print(f"→ S4 ✓  {found_email}")

        # ── Strategy 1 ──────────────────────────────────────────────────────
        if not found_email and domain:
            try:
                found_email, source = strategy1(domain, name)
                if found_email:
                    print(f"→ S1 ✓  {found_email}")
            except Exception as exc:
                print(f"\n  [error] S1: {exc}")

        # ── Strategy 2 ──────────────────────────────────────────────────────
        if not found_email and domain:
            try:
                found_email, source = strategy2(domain)
                if found_email:
                    print(f"→ S2 ✓  {found_email}")
            except Exception as exc:
                print(f"\n  [error] S2: {exc}")

        # ── Strategy 3 ──────────────────────────────────────────────────────
        if not found_email:
            try:
                found_email, source = strategy3(org)
                if found_email:
                    print(f"→ S3 ✓  {found_email}")
            except Exception as exc:
                print(f"\n  [error] S3: {exc}")

        # ── Strategy 5 ──────────────────────────────────────────────────────
        if not found_email and domain:
            try:
                found_email, source = strategy5(domain, name)
                if found_email:
                    print(f"→ S5 ✓  {found_email}")
            except Exception as exc:
                print(f"\n  [error] S5: {exc}")

        if not found_email:
            source = "still_not_found"
            print("→ still not found")

        if found_email:
            out_row["Email"] = found_email
        out_row["Hunter_Source"] = source
        stats[source] = stats.get(source, 0) + 1
        out_rows[idx] = out_row

    # Write output
    with open(OUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(out_rows)

    # Final credits
    req_after = credit_report("AFTER")
    s_used = "?"
    v_used = "?"
    if req_after:
        s_used = req_after.get("searches",      {}).get("used", 0) - searches_start
        v_used = req_after.get("verifications", {}).get("used", 0) - verif_start

    # Summary
    total_with_email = sum(1 for r in out_rows if r.get("Email", "").strip())
    new_found = sum(v for k, v in stats.items() if k.endswith("_verified"))

    print(f"\n{'=' * 60}")
    print("ENRICHMENT V2 SUMMARY")
    print("=" * 60)
    print(f"  Output file              : {OUT_CSV}")
    print(f"  Contacts retried         : {len(retry_indices)}")
    print(f"  Strategy 1 (clean name)  : {stats['strategy1_verified']}")
    print(f"  Strategy 2 (alt domains) : {stats['strategy2_verified']}")
    print(f"  Strategy 3 (org→domain)  : {stats['strategy3_verified']}")
    print(f"  Strategy 4 (domain-only) : {stats['strategy4_verified']}")
    print(f"  Strategy 5 (fuzzy name)  : {stats['strategy5_verified']}")
    print(f"  Still not found          : {stats['still_not_found']}")
    print(f"  New emails added         : {new_found}")
    print(f"  Total emails in file     : {total_with_email} / {len(out_rows)}")
    print(f"  Overall coverage         : {100 * total_with_email // len(out_rows)}%")
    print(f"\n  Searches used this run      : {s_used}")
    print(f"  Verifications used this run : {v_used}")


if __name__ == "__main__":
    main()
