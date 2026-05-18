import httpx
from app.config import settings

_token: str | None = None


def authenticate() -> str | None:
    global _token
    try:
        r = httpx.post(
            "https://api.artsy.net/api/tokens/xapp_token",
            data={"client_id": settings.artsy_client_id, "client_secret": settings.artsy_client_secret},
            timeout=10,
        )
        r.raise_for_status()
        _token = r.json().get("token")
        return _token
    except Exception:
        return None


def _get_token() -> str | None:
    return _token or authenticate()


def search_galleries(query: str = "realism", size: int = 50) -> list[dict]:
    token = _get_token()
    if not token:
        return []
    try:
        r = httpx.get(
            "https://api.artsy.net/api/partners",
            params={"type": "Gallery", "q": query, "size": size},
            headers={"X-Xapp-Token": token},
            timeout=15,
        )
        r.raise_for_status()
        partners = r.json().get("_embedded", {}).get("partners", [])
        results = []
        for p in partners:
            results.append({
                "name": p.get("name", ""),
                "location": p.get("location", {}).get("city", "") if isinstance(p.get("location"), dict) else "",
                "website": p.get("website", ""),
                "email": p.get("email", ""),
            })
        return results
    except Exception:
        return []
