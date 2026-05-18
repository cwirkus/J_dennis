import json
import os
import time

import anthropic
from dotenv import load_dotenv

load_dotenv()

_MODEL = "claude-sonnet-4-6"

_SYSTEM = (
    "You are researching art world contacts for J. Rodney Dennis, a classical realist painter. "
    "His work: Old Master technique applied to African American figurative narrative subjects. "
    "2024 ARC Salon Chairman's Choice Award. Wall Street Journal featured. "
    "Florence Academy of Art trained. Paintings start at $25,000. "
    "Research the provided contact and identify the strongest connection between their collecting "
    "focus and Rod's work. Be specific and concise. "
    "Return only a JSON object with these exact keys: "
    "contact_name, role, recent_activity, acquisition_focus, best_angle, suggested_tone."
)

_DEFAULT = {
    "contact_name": "",
    "role": "",
    "recent_activity": "",
    "acquisition_focus": "",
    "best_angle": "",
    "suggested_tone": "formal",
}


def _strip_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        parts = text.split("```")
        if len(parts) >= 2:
            text = parts[1]
            if text.startswith("json"):
                text = text[4:]
    return text.strip()


def research_prospect(prospect: dict) -> dict:
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    user_msg = (
        f"Name: {prospect.get('name', 'Unknown')}\n"
        f"Organization: {prospect.get('organization', 'Unknown')}\n"
        f"Category: {prospect.get('category', '')}\n"
        f"Country: {prospect.get('country', '')}\n"
        f"Notes: {prospect.get('notes', '')}\n\n"
        "Research this contact and return the JSON object."
    )

    for attempt in range(2):
        try:
            response = client.messages.create(
                model=_MODEL,
                max_tokens=512,
                system=_SYSTEM,
                messages=[{"role": "user", "content": user_msg}],
            )
            text = _strip_fences(response.content[0].text)
            return json.loads(text)
        except json.JSONDecodeError:
            if attempt == 0:
                time.sleep(1)
                continue
            return _DEFAULT.copy()
        except Exception as exc:
            print(f"  [research error] {exc}")
            return _DEFAULT.copy()

    return _DEFAULT.copy()
