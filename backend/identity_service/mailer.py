from email.message import EmailMessage
import smtplib
import ssl
from pathlib import Path

from identity_service.settings import IdentitySettings


def send_security_code(settings: IdentitySettings, email: str, purpose: str, code: str) -> None:
    if not settings.email_ready:
        raise RuntimeError("Identity email delivery is not configured")
    password = Path(settings.smtp_password_file).read_text(encoding="utf-8").strip() if settings.smtp_password_file else ""
    message = EmailMessage()
    message["Subject"] = f"DataShield {purpose} verification"
    message["From"] = settings.email_from
    message["To"] = email
    message.set_content(
        f"Your DataShield verification code is: {code}\n\n"
        f"It expires in {settings.email_code_minutes} minutes. If you did not request this, ignore this email."
    )
    context = ssl.create_default_context()
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as client:
        client.ehlo()
        if settings.smtp_starttls:
            client.starttls(context=context)
            client.ehlo()
        if settings.smtp_user:
            client.login(settings.smtp_user, password)
        client.send_message(message)
