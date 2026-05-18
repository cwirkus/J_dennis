import base64
import json
import tempfile
from email.mime.text import MIMEText

from googleapiclient.discovery import build

from app.config import settings

SCOPES = ["https://www.googleapis.com/auth/gmail.send"]


def authenticate():
    raw = settings.gmail_credentials_json
    if not raw:
        raise ValueError("GMAIL_CREDENTIALS_JSON is not set")

    info = json.loads(raw)
    cred_type = info.get("type", "")

    if cred_type == "service_account":
        from google.oauth2.service_account import Credentials
        creds = Credentials.from_service_account_info(
            info,
            scopes=SCOPES,
            subject=settings.rod_email,
        )
    else:
        from google.oauth2.credentials import Credentials
        creds = Credentials(
            token=info.get("token"),
            refresh_token=info.get("refresh_token"),
            token_uri=info.get("token_uri", "https://oauth2.googleapis.com/token"),
            client_id=info.get("client_id"),
            client_secret=info.get("client_secret"),
            scopes=SCOPES,
        )

    return build("gmail", "v1", credentials=creds)


def send_email(to: str, subject: str, body: str) -> str | None:
    try:
        service = authenticate()
        msg = MIMEText(body, "plain")
        msg["To"] = to
        msg["From"] = settings.rod_email
        msg["Subject"] = subject
        raw_bytes = base64.urlsafe_b64encode(msg.as_bytes()).decode()
        result = (
            service.users()
            .messages()
            .send(userId="me", body={"raw": raw_bytes})
            .execute()
        )
        return result.get("id")
    except Exception as exc:
        print(f"[gmail_service] send_email failed: {exc}")
        return None
