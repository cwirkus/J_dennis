import httpx
from app.config import settings


def find_email(domain: str, full_name: str | None = None) -> str | None:
    try:
        params: dict = {"domain": domain, "api_key": settings.hunter_api_key}
        if full_name:
            params["full_name"] = full_name
        r = httpx.get("https://api.hunter.io/v2/domain-search", params=params, timeout=10)
        r.raise_for_status()
        data = r.json().get("data", {})
        emails = data.get("emails", [])
        if emails:
            return emails[0].get("value")
        return None
    except Exception:
        return None


def verify_email(email: str) -> bool:
    try:
        r = httpx.get(
            "https://api.hunter.io/v2/email-verifier",
            params={"email": email, "api_key": settings.hunter_api_key},
            timeout=10,
        )
        r.raise_for_status()
        result = r.json().get("data", {}).get("result", "")
        return result == "deliverable"
    except Exception:
        return False
