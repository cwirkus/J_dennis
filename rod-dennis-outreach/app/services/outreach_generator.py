import json
import os

import anthropic
from dotenv import load_dotenv

load_dotenv()

_MODEL = "claude-sonnet-4-6"

ROD_VOICE_SYSTEM_PROMPT = """You are writing outreach emails on behalf of J. Rodney Dennis, a classical realist painter.

Rod's voice and positioning:
- Professional, warm, and direct. Never salesy. Never desperate.
- He leads with the cultural significance of his work, not just technique.
- His work sits at the intersection of two rare things: Old Master classical realism AND African American figurative narrative.
- Key credentials to reference when relevant: 2024 ARC Salon Chairman's Choice Award, Wall Street Journal feature, Florence Academy of Art training, Art in Embassies (State Department).
- Paintings start at $25,000. He does not mention price in initial outreach.
- He is represented by Portland Art Gallery in Maine.
- He was mentored by Curlee Raven Holton, Director of the David C. Driskell Center.

Rules for every email:
- Maximum 4 short paragraphs. Concise. Easy to read.
- Open with something specific about the recipient — a recent exhibition, an acquisition, a stated focus.
- Never open with 'I am writing to' or 'My name is'.
- Never use exclamation marks.
- Close with a simple low-pressure ask — a studio visit, a viewing, a conversation.
- Formal but human. Like a letter from one professional to another.
- Always sign: J. Rodney Dennis | www.jrodneydennis.com | info@jrodneydennis.com"""


def _strip_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        parts = text.split("```")
        if len(parts) >= 2:
            text = parts[1]
            if text.startswith("json"):
                text = text[4:]
    return text.strip()


def generate_outreach(prospect: dict, research: dict) -> dict:
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    user_msg = (
        "Write an outreach email to this prospect.\n\n"
        f"Prospect: {prospect.get('name', '')} at {prospect.get('organization', '')}, {prospect.get('country', '')}\n"
        f"Contact name: {research.get('contact_name', prospect.get('name', ''))}\n"
        f"Role: {research.get('role', '')}\n"
        f"Recent activity: {research.get('recent_activity', '')}\n"
        f"Acquisition focus: {research.get('acquisition_focus', '')}\n"
        f"Best angle: {research.get('best_angle', '')}\n"
        f"Suggested tone: {research.get('suggested_tone', 'formal')}\n\n"
        "Return JSON only with keys: subject (str), body (str)"
    )

    try:
        response = client.messages.create(
            model=_MODEL,
            max_tokens=1024,
            system=ROD_VOICE_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_msg}],
        )
        text = _strip_fences(response.content[0].text)
        return json.loads(text)
    except Exception as exc:
        print(f"  [outreach error] {exc}")
        return {"subject": "", "body": ""}
