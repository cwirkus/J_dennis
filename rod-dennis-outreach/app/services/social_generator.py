import httpx

from app.config import settings

LINKEDIN_SYSTEM_PROMPT = """You write LinkedIn posts for J. Rodney Dennis, a classical realist painter. His voice on LinkedIn: Thoughtful. Authoritative. He is positioning himself as a thought leader at the intersection of Old Master classical realism and African American figurative art. He speaks to collectors, gallery directors, art advisors, and cultural institutions.

Post structure:
- Strong opening line that does not start with "I"
- 3-4 short paragraphs
- End with a question or observation that invites engagement
- No hashtags in body text. Up to 5 relevant hashtags at the end on their own line
- 150-300 words

Do not mention prices. Do not be salesy. Write like a serious artist with a perspective, not a marketer. Never use exclamation marks."""

TWITTER_SYSTEM_PROMPT = """You write Twitter/X posts for J. Rodney Dennis, a classical realist painter. His voice on Twitter: Sharp. Concise. Occasionally provocative. He is staking a claim that African Americans belong in the classical tradition.

Rules:
- Maximum 280 characters — count carefully
- No hashtags unless essential
- Direct statement or a question. No fluff.
- Write like a painter with something to say, not a brand.
- Never use exclamation marks."""

INSTAGRAM_CAPTION_SYSTEM_PROMPT = """You write Instagram captions for J. Rodney Dennis, a classical realist painter. His voice on Instagram: Visual, intimate, grounded. He is sharing the story behind the work — the process, the subject, the cultural argument.

Rules:
- 2-3 short paragraphs
- First line must hook immediately — it is what shows before "more"
- Personal but not confessional
- End with a question that invites comments
- 3-5 hashtags at the end: always include #classicalrealism #africanamericanart #figurativepainting plus 2 relevant to the specific post
- 100-200 words
- Never use exclamation marks."""


async def _call_claude(system: str, user_content: str, max_tokens: int) -> str:
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
                "max_tokens": max_tokens,
                "system": system,
                "messages": [{"role": "user", "content": user_content}],
            },
        )
        response.raise_for_status()
    return response.json()["content"][0]["text"]


async def generate_linkedin_post(trigger_event: str, context: str = "") -> str:
    try:
        return await _call_claude(
            LINKEDIN_SYSTEM_PROMPT,
            f"Write a LinkedIn post.\nTrigger: {trigger_event}\nContext: {context}",
            600,
        )
    except Exception:
        return ""


async def generate_twitter_post(trigger_event: str, linkedin_post: str = "") -> str:
    try:
        user_content = f"Write a Twitter post.\nTrigger: {trigger_event}"
        if linkedin_post:
            user_content += f"\nLinkedIn version for reference:\n{linkedin_post}"

        text = await _call_claude(TWITTER_SYSTEM_PROMPT, user_content, 100)

        if len(text) > 280:
            text = await _call_claude(
                TWITTER_SYSTEM_PROMPT,
                f"Rewrite this Twitter post to be UNDER 280 characters. Current length: {len(text)}.\nOriginal: {text}\nTrigger: {trigger_event}",
                80,
            )

        return text[:280]
    except Exception:
        return ""


async def generate_instagram_caption(trigger_event: str, context: str = "") -> str:
    try:
        return await _call_claude(
            INSTAGRAM_CAPTION_SYSTEM_PROMPT,
            f"Write an Instagram caption.\nTrigger: {trigger_event}\nContext: {context}",
            400,
        )
    except Exception:
        return ""


async def generate_social_content(
    trigger_event: str,
    context: str = "",
    platforms: list = ["linkedin", "twitter", "instagram"],
) -> dict:
    result = {}

    linkedin_text = ""
    if "linkedin" in platforms:
        linkedin_text = await generate_linkedin_post(trigger_event, context)
        if linkedin_text:
            result["linkedin"] = linkedin_text

    if "twitter" in platforms:
        twitter_text = await generate_twitter_post(trigger_event, linkedin_post=linkedin_text)
        if twitter_text:
            result["twitter"] = twitter_text

    if "instagram" in platforms:
        instagram_text = await generate_instagram_caption(trigger_event, context)
        if instagram_text:
            result["instagram"] = instagram_text

    return result
