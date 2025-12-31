import logging
from dataclasses import dataclass
from typing import Optional

import httpx
from twilio.rest import Client
from twilio.request_validator import RequestValidator

from core.config import settings

logger = logging.getLogger(__name__)


@dataclass
class IncomingMessage:
    """Parsed incoming WhatsApp message."""
    message_sid: str
    from_number: str
    to_number: str
    body: Optional[str]
    num_media: int
    media_url: Optional[str]
    media_content_type: Optional[str]
    profile_name: Optional[str]

    @property
    def is_voice(self) -> bool:
        """Check if message contains audio."""
        if not self.media_content_type:
            return False
        return self.media_content_type.startswith("audio/")

    @property
    def is_text(self) -> bool:
        """Check if message is text only."""
        return self.num_media == 0 and bool(self.body)


class TwilioService:
    def __init__(self):
        self.client: Optional[Client] = None
        self.validator: Optional[RequestValidator] = None
        self.whatsapp_number: Optional[str] = None

    def configure(
        self,
        account_sid: str,
        auth_token: str,
        whatsapp_number: str,
    ) -> None:
        self.client = Client(account_sid, auth_token)
        self.validator = RequestValidator(auth_token)
        self.whatsapp_number = whatsapp_number

    def is_configured(self) -> bool:
        return self.client is not None

    def validate_signature(
        self,
        url: str,
        params: dict,
        signature: str,
    ) -> bool:
        """Validate Twilio request signature."""
        if not self.validator:
            logger.error("Twilio validator not configured")
            return False
        return self.validator.validate(url, params, signature)

    def parse_incoming_message(self, form_data: dict) -> IncomingMessage:
        """Parse incoming webhook form data into IncomingMessage."""
        num_media = int(form_data.get("NumMedia", 0))

        media_url = None
        media_content_type = None
        if num_media > 0:
            media_url = form_data.get("MediaUrl0")
            media_content_type = form_data.get("MediaContentType0")

        return IncomingMessage(
            message_sid=form_data.get("MessageSid", ""),
            from_number=form_data.get("From", ""),
            to_number=form_data.get("To", ""),
            body=form_data.get("Body"),
            num_media=num_media,
            media_url=media_url,
            media_content_type=media_content_type,
            profile_name=form_data.get("ProfileName"),
        )

    async def download_media(self, media_url: str) -> Optional[bytes]:
        """Download media file from Twilio."""
        if not self.client:
            logger.error("Twilio client not configured")
            return None

        try:
            # Twilio media URLs require authentication
            async with httpx.AsyncClient() as http_client:
                response = await http_client.get(
                    media_url,
                    auth=(
                        settings.twilio_account_sid,
                        settings.twilio_auth_token,
                    ),
                    follow_redirects=True,
                )
                response.raise_for_status()
                return response.content
        except Exception as e:
            logger.error(f"Failed to download media: {e}")
            return None

    def send_reply(self, to: str, body: str) -> bool:
        """Send WhatsApp reply message."""
        if not self.client or not self.whatsapp_number:
            logger.error("Twilio client not configured")
            return False

        try:
            message = self.client.messages.create(
                from_=self.whatsapp_number,
                to=to,
                body=body,
            )
            logger.info(f"Sent reply: {message.sid}")
            return True
        except Exception as e:
            logger.error(f"Failed to send reply: {e}")
            return False


# Singleton instance
twilio_service = TwilioService()


def get_twilio_service() -> TwilioService:
    """Get configured Twilio service instance."""
    if not twilio_service.is_configured():
        twilio_service.configure(
            account_sid=settings.twilio_account_sid,
            auth_token=settings.twilio_auth_token,
            whatsapp_number=settings.twilio_whatsapp_number,
        )
    return twilio_service
