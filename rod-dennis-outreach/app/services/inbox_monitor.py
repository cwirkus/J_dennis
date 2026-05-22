import asyncio
import email
import imaplib
import smtplib
from datetime import datetime, timedelta, timezone
from email.header import decode_header
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import parseaddr

from app.config import settings
from app.database import get_db
from app.services import chat_service


def _decode_header_value(value: str) -> str:
    if not value:
        return ""
    parts = decode_header(value)
    decoded = []
    for part, charset in parts:
        if isinstance(part, bytes):
            decoded.append(part.decode(charset or "utf-8", errors="replace"))
        else:
            decoded.append(part)
    return "".join(decoded)


def _extract_body(msg: email.message.Message) -> str:
    if msg.is_multipart():
        for part in msg.walk():
            ctype = part.get_content_type()
            disp = str(part.get("Content-Disposition", ""))
            if ctype == "text/plain" and "attachment" not in disp:
                charset = part.get_content_charset() or "utf-8"
                return part.get_payload(decode=True).decode(charset, errors="replace")
        for part in msg.walk():
            if part.get_content_type() == "text/html":
                import re
                charset = part.get_content_charset() or "utf-8"
                html = part.get_payload(decode=True).decode(charset, errors="replace")
                return re.sub(r"<[^>]+>", "", html).strip()
    else:
        charset = msg.get_content_charset() or "utf-8"
        return msg.get_payload(decode=True).decode(charset, errors="replace")
    return ""


def _find_prospect_by_email(sender_email: str) -> dict | None:
    rows = get_db().table("prospects").select("*").eq("email", sender_email).execute().data or []
    return rows[0] if rows else None


def _find_sent_draft(prospect_id: str) -> dict | None:
    rows = (
        get_db().table("outreach_drafts")
        .select("subject,body")
        .eq("prospect_id", prospect_id)
        .eq("status", "sent")
        .order("sent_at", desc=True)
        .limit(1)
        .execute()
        .data or []
    )
    return rows[0] if rows else None


def _mark_drafts_replied(prospect_id: str) -> None:
    get_db().table("outreach_drafts").update({"replied": True}).eq("prospect_id", prospect_id).eq("status", "sent").execute()


def _check_inbox_sync() -> dict:
    host = settings.imap_host
    port = settings.imap_port
    username = settings.smtp_username
    password = settings.smtp_password

    if not host or not username or not password:
        return {"error": "IMAP not configured", "new_replies": 0, "matched": 0}

    new_replies = 0
    matched = 0

    with imaplib.IMAP4_SSL(host, port) as imap:
        imap.login(username, password)
        imap.select("INBOX")

        since = (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%d-%b-%Y")
        _, data = imap.search(None, f'UNSEEN SINCE {since}')
        msg_ids = data[0].split()

        for mid in msg_ids:
            _, raw_data = imap.fetch(mid, "(RFC822)")
            if not raw_data or raw_data[0] is None:
                continue

            msg = email.message_from_bytes(raw_data[0][1])
            from_raw = msg.get("From", "")
            sender_name, sender_email = parseaddr(from_raw)
            sender_name = _decode_header_value(sender_name) or sender_name
            sender_email = sender_email.lower().strip()
            subject = _decode_header_value(msg.get("Subject", ""))
            body = _extract_body(msg).strip()

            if not sender_email:
                imap.store(mid, "+FLAGS", "\\Seen")
                continue

            prospect = _find_prospect_by_email(sender_email)
            new_replies += 1
            db = get_db()

            if prospect:
                matched += 1
                now = datetime.now(timezone.utc).isoformat()

                db.table("prospects").update({
                    "status": "Response",
                    "last_activity": now,
                }).eq("email", sender_email).execute()

                _mark_drafts_replied(prospect["id"])

                sent_draft = _find_sent_draft(prospect["id"])
                original_subject = sent_draft.get("subject", "") if sent_draft else ""
                original_body = sent_draft.get("body", "") if sent_draft else ""

                result = db.table("inbound_messages").insert({
                    "sender_name": prospect.get("name") or sender_name,
                    "sender_email": sender_email,
                    "channel": "email",
                    "message": body,
                    "status": "pending",
                    "high_priority": chat_service.is_high_priority(sender_email, sender_name, body),
                    "prospect_org": prospect.get("organization", ""),
                    "original_subject": original_subject,
                    "original_body": original_body,
                }).execute()
                saved = result.data[0] if result.data else {}

                if saved.get("id"):
                    draft_text = asyncio.get_event_loop().run_until_complete(
                        chat_service.draft_response(
                            saved.get("sender_name", sender_name), sender_email, "email", body
                        )
                    )
                    db.table("inbound_messages").update({"draft_response": draft_text}).eq("id", saved["id"]).execute()
            else:
                db.table("inbound_messages").insert({
                    "sender_name": sender_name,
                    "sender_email": sender_email,
                    "channel": "email",
                    "message": body,
                    "status": "pending",
                    "high_priority": False,
                    "prospect_org": None,
                    "original_subject": subject,
                    "original_body": None,
                }).execute()

            imap.store(mid, "+FLAGS", "\\Seen")

    return {"new_replies": new_replies, "matched": matched}


async def check_inbox() -> dict:
    return await asyncio.to_thread(_check_inbox_sync)


def send_reply(to_email: str, subject: str, body: str) -> bool:
    host = settings.smtp_host or settings.imap_host
    port = settings.smtp_port
    username = settings.smtp_username
    password = settings.smtp_password
    from_addr = settings.rod_email

    if not host or not username or not password:
        return False

    try:
        msg = MIMEMultipart("alternative")
        msg["From"] = from_addr
        msg["To"] = to_email
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain"))

        if port == 465:
            with smtplib.SMTP_SSL(host, port) as smtp:
                smtp.login(username, password)
                smtp.sendmail(from_addr, to_email, msg.as_string())
        else:
            with smtplib.SMTP(host, port) as smtp:
                smtp.ehlo()
                smtp.starttls()
                smtp.login(username, password)
                smtp.sendmail(from_addr, to_email, msg.as_string())
        return True
    except Exception as exc:
        print(f"[inbox_monitor] SMTP send failed: {exc}")
        return False
