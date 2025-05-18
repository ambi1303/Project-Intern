from typing import Any, Dict, Optional
from fastapi_mail import FastMail, MessageSchema, ConnectionConfig
from pydantic import EmailStr
from app.core.config import settings

# Email configuration
conf = ConnectionConfig(
    MAIL_USERNAME=settings.SMTP_USER,
    MAIL_PASSWORD=settings.SMTP_PASSWORD,
    MAIL_FROM=settings.EMAILS_FROM_EMAIL,
    MAIL_PORT=settings.SMTP_PORT,
    MAIL_SERVER=settings.SMTP_HOST,
    MAIL_FROM_NAME=settings.PROJECT_NAME,
    MAIL_TLS=True,
    MAIL_SSL=False,
    USE_CREDENTIALS=True,
    TEMPLATE_FOLDER='./app/email-templates'
)

async def send_email_alert(
    email_to: str,
    subject: str,
    body: str,
    template_name: Optional[str] = None,
    template_data: Optional[Dict[str, Any]] = None
) -> None:
    """
    Send an email alert.
    In production, this would use a real email service.
    For development, we'll just print the email details.
    """
    if settings.ENVIRONMENT == "development":
        print(f"\n=== Email Alert ===")
        print(f"To: {email_to}")
        print(f"Subject: {subject}")
        print(f"Body: {body}")
        if template_name:
            print(f"Template: {template_name}")
        if template_data:
            print(f"Template Data: {template_data}")
        print("==================\n")
        return

    # In production, use FastMail to send real emails
    message = MessageSchema(
        subject=subject,
        recipients=[email_to],
        body=body,
        subtype="html"
    )

    fm = FastMail(conf)
    await fm.send_message(message) 