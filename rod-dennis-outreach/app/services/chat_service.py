import httpx

from app.config import settings

RESPONSE_SYSTEM_PROMPT = """You are drafting responses on behalf of J. Rodney Dennis, a classical realist painter.

His credentials: 2024 ARC Salon Chairman's Choice Award, Wall Street Journal feature, Florence Academy of Art trained, represented by Portland Art Gallery Maine. Paintings start at $25,000. No prints.

His response voice: Warm, professional, never eager. He responds like someone whose time is valuable but who genuinely appreciates serious interest in his work.

Rules:
- Keep responses under 3 paragraphs
- Always acknowledge their outreach graciously
- If they are asking about purchasing: invite them to discuss availability, do not confirm prices in writing
- If they are a gallery: express genuine interest and suggest a next step — a studio visit, a call, sending portfolio materials
- If they are press or media: be available and suggest a call or interview
- If they are a foundation or institution: acknowledge the mission alignment and suggest a conversation
- If they are another artist: warm and collegial, offer to connect
- Never confirm prices in writing in initial responses
- Always end with a clear next step
- Sign off: J. Rodney Dennis | www.jrodneydennis.com | info@jrodneydennis.com"""

_HIGH_PRIORITY_DOMAINS = {
    "goodman-gallery.com", "marianeibrahim.com", "jackshainman.com",
    "swanngalleries.com", "christies.com", "sothebys.com", "bonhams.com",
    "tate.org.uk", "moma.org", "metmuseum.org", "smithsonian.edu",
    "artbasel.com", "frieze.com", "galeriemyrtis.net", "studiomuseum.org",
}

# Checked as substrings — stems intentional (acqui covers acquire/acquiring/acquisition)
_HIGH_PRIORITY_KEYWORDS = [
    "acqui", "purchas", "commission", "represent", "gallery", "curator",
    "collection", "foundation", "museum", "biennale", "exhibition",
    "consignment", "director", "collector", "advisor", "interview",
    "press", "media", "journalist",
]


async def draft_response(
    sender_name: str,
    sender_email: str,
    channel: str,
    message: str,
) -> str:
    try:
        async with httpx.AsyncClient(timeout=45) as client:
            response = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": settings.anthropic_api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": "claude-sonnet-4-6",
                    "max_tokens": 400,
                    "system": RESPONSE_SYSTEM_PROMPT,
                    "messages": [
                        {
                            "role": "user",
                            "content": (
                                "Draft a response to this inquiry.\n"
                                f"From: {sender_name} ({sender_email})\n"
                                f"Channel: {channel}\n"
                                f"Message: {message}\n\n"
                                "Return only the response text. No subject line. No preamble."
                            ),
                        }
                    ],
                },
            )
            response.raise_for_status()
        return response.json()["content"][0]["text"]
    except Exception:
        return "Thank you for reaching out. I will be in touch shortly. — J. Rodney Dennis"


def is_high_priority(sender_email: str, sender_name: str, message: str) -> bool:
    domain = sender_email.lower().split("@")[-1] if "@" in sender_email else ""
    if domain in _HIGH_PRIORITY_DOMAINS:
        return True

    combined = (message + " " + sender_name).lower()
    return any(kw in combined for kw in _HIGH_PRIORITY_KEYWORDS)
