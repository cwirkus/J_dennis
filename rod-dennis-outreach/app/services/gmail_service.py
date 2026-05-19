import smtplib
import ssl
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from app.config import settings

logger = logging.getLogger(__name__)


def send_email(to: str, subject: str, body: str, from_email: str = None) -> str | None:
    sender = from_email or settings.smtp_username
    try:
        msg = MIMEMultipart()
        msg["From"] = sender
        msg["To"] = to
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain"))
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(settings.smtp_host, 465, context=context) as server:
            server.login(settings.smtp_username, settings.smtp_password)
            server.sendmail(sender, to, msg.as_string())
            logger.info(f"[gmail_service] email sent to={to} subject={subject}")
            return "sent"
    except Exception as e:
        logger.error(f"[gmail_service] send_email failed: {e}")
        return None
