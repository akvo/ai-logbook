import json
import logging
from io import BytesIO
from pathlib import Path
from datetime import date
from typing import Optional, List, Any

import httpx
from openai import AsyncOpenAI, OpenAIError

from core.config import (
    settings,
    OPENAI_TRANSCRIPTION_MODEL,
    OPENAI_EXTRACTION_MODEL,
    OPENAI_EXTRACTION_PROMPT_FILE,
)
from models.schemas import TranscriptionResponse

logger = logging.getLogger(__name__)


class OpenAIService:
    def __init__(self):
        self.client: Optional[AsyncOpenAI] = None
        self._prompt: Optional[str] = None

    def configure(self, api_key: str) -> None:
        self.client = AsyncOpenAI(api_key=api_key)

    def is_configured(self) -> bool:
        return self.client is not None

    def _load_prompt(self) -> str:
        if self._prompt is None:
            prompt_path = Path(__file__).parent / "prompt.txt"
            if not prompt_path.exists():
                # Try alternative path
                prompt_path = Path(OPENAI_EXTRACTION_PROMPT_FILE)
            self._prompt = prompt_path.read_text(encoding="utf-8")
        return self._prompt

    async def transcribe_audio(
        self,
        audio_url: Optional[str] = None,
        audio_file: Optional[bytes] = None,
        language: Optional[str] = None,
    ) -> Optional[TranscriptionResponse]:
        """
        Transcribe audio using OpenAI Whisper.

        Args:
            audio_url: URL to download audio from
            audio_file: Raw audio bytes
            language: Language hint (e.g., 'en', 'id', 'my')

        Returns:
            TranscriptionResponse or None if error
        """
        if not self.is_configured():
            logger.error("OpenAI client not configured")
            return None

        if not audio_url and not audio_file:
            logger.error("Either audio_url or audio_file required")
            return None

        # Download audio if URL provided
        if audio_url:
            try:
                async with httpx.AsyncClient() as http_client:
                    response = await http_client.get(audio_url)
                    response.raise_for_status()
                    audio_file = response.content
            except Exception as e:
                logger.error(f"Failed to download audio: {e}")
                return None

        # Transcribe using Whisper
        try:
            audio_buffer = BytesIO(audio_file)
            audio_buffer.name = "audio.ogg"

            kwargs = {
                "model": OPENAI_TRANSCRIPTION_MODEL,
                "file": audio_buffer,
                "response_format": "verbose_json",
            }
            if language:
                kwargs["language"] = language

            transcript = await self.client.audio.transcriptions.create(**kwargs)

            text_len = len(transcript.text) if hasattr(transcript, "text") else 0
            logger.info(f"Audio transcribed ({text_len} chars)")

            return TranscriptionResponse(
                text=transcript.text,
                language=getattr(transcript, "language", language),
                duration=getattr(transcript, "duration", None),
            )

        except OpenAIError as e:
            logger.error(f"OpenAI transcription error: {e}")
            return None
        except Exception as e:
            logger.error(f"Transcription failed: {e}")
            return None

    async def extract(
        self,
        transcript: str,
        farmer_id: str,
        farmer_name: str,
        input_mode: str = "text",
        current_date: Optional[date] = None,
        existing_record: Optional[dict] = None,
    ) -> List[dict]:
        """
        Extract structured records from transcript using GPT.

        Args:
            transcript: The farmer's message (text or transcribed voice)
            farmer_id: Farmer's ID
            farmer_name: Farmer's name
            input_mode: 'voice' or 'text'
            current_date: Current date for relative date inference
            existing_record: Existing record data to update (for follow-up responses)

        Returns:
            List of extracted record dictionaries
        """
        if not self.is_configured():
            logger.error("OpenAI client not configured")
            return []

        if current_date is None:
            current_date = date.today()

        system_prompt = self._load_prompt()

        # If there's an existing record, add context for updating
        existing_context = ""
        if existing_record:
            existing_context = f"""
- IMPORTANT: This is a follow-up response to complete an existing record.
- existing_record_type: "{existing_record.get('record_type', 'unknown')}"
- existing_data: {json.dumps(existing_record.get('data', {}), ensure_ascii=False)}
- missing_fields: {existing_record.get('missing_fields', [])}
- The farmer is providing additional information to fill in the missing fields.
- Merge the new information with existing data. Keep existing values unless explicitly corrected.
"""

        user_message = f"""Input:
- current_date: "{current_date.isoformat()}"
- farmer_id: "{farmer_id}"
- farmer_name: "{farmer_name}"
- input_mode: "{input_mode}"
- transcript: "{transcript}"
{existing_context}"""

        try:
            response = await self.client.chat.completions.create(
                model=OPENAI_EXTRACTION_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
                temperature=0.1,
                response_format={"type": "json_object"},
            )

            content = response.choices[0].message.content
            logger.info(f"Extraction completed, response length: {len(content)}")

            return self._parse_response(content)

        except OpenAIError as e:
            logger.error(f"OpenAI extraction error: {e}")
            return []
        except Exception as e:
            logger.error(f"Extraction failed: {e}")
            return []

    def _parse_response(self, content: str) -> List[dict]:
        """Parse GPT response into list of records."""
        try:
            data = json.loads(content)

            # Handle both single object and array responses
            if isinstance(data, list):
                return data
            elif isinstance(data, dict):
                # Check if it's a wrapper object with records array
                if "records" in data:
                    return data["records"]
                # Single record
                return [data]
            else:
                logger.warning(f"Unexpected response type: {type(data)}")
                return []

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {e}")
            return []

    def validate_record(self, record: dict) -> bool:
        """Validate extracted record has required fields."""
        required = ["record_type", "farmer", "data", "quality"]
        return all(key in record for key in required)

    async def generate_reply(
        self,
        record_type: str,
        existing_data: dict,
        missing_fields: List[str],
        language: str,
        farmer_name: str,
        is_confirmed: bool = False,
    ) -> str:
        """
        Generate a natural follow-up message or confirmation using GPT.

        Args:
            record_type: Type of record (e.g., "chemical_spray")
            existing_data: Data already collected from farmer
            missing_fields: List of fields still needed
            language: Language code (e.g., "id", "en", "my")
            farmer_name: Farmer's name for personalization
            is_confirmed: If True, generate confirmation message instead of follow-up

        Returns:
            Natural language message for the farmer
        """
        if not self.is_configured():
            logger.error("OpenAI client not configured")
            return "Thank you for your message."

        if is_confirmed:
            # Generate confirmation message with summary
            system_prompt = """You are a friendly agricultural assistant helping farmers keep records via WhatsApp.
Generate a confirmation message in the specified language that:
1. Thanks the farmer
2. Summarizes the recorded data in a clear, readable list format
3. Asks if they want to correct anything (reply 'OK' to confirm or send corrections)

IMPORTANT formatting rules:
- Do NOT use asterisks (*) or any markdown formatting
- Use plain text only
- Use line breaks and dashes (-) for lists
- Keep it simple and readable

Be warm, concise, and use simple language that farmers can easily understand.
Output ONLY the message text."""

            user_message = f"""Language: {language}
Farmer name: {farmer_name}
Record type: {record_type.replace('_', ' ')}
Recorded data: {json.dumps(existing_data, ensure_ascii=False, indent=2)}

Generate a confirmation message without any asterisks or markdown."""

        else:
            # Generate follow-up question for missing fields
            system_prompt = """You are a friendly agricultural assistant helping farmers keep records via WhatsApp.
Generate a natural follow-up question in the specified language that:
1. Briefly acknowledges what was already recorded
2. Asks for the missing information in a conversational way
3. Be specific about what information is needed

IMPORTANT formatting rules:
- Do NOT use asterisks (*) or any markdown formatting
- Use plain text only
- Keep it simple and readable

Be warm, concise, and use simple language that farmers can easily understand.
Ask for 2-3 missing fields at most per message to avoid overwhelming the farmer.
Output ONLY the message text."""

            user_message = f"""Language: {language}
Farmer name: {farmer_name}
Record type: {record_type.replace('_', ' ')}
Already recorded: {json.dumps(existing_data, ensure_ascii=False)}
Missing fields needed: {', '.join(missing_fields)}

Generate a follow-up question without any asterisks or markdown."""

        try:
            response = await self.client.chat.completions.create(
                model=OPENAI_EXTRACTION_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
                temperature=0.7,
                max_tokens=500,
            )

            reply = response.choices[0].message.content.strip()
            logger.info(f"Generated reply: {reply[:100]}...")
            return reply

        except OpenAIError as e:
            logger.error(f"OpenAI reply generation error: {e}")
            return "Thank you for your message. We'll process it shortly."
        except Exception as e:
            logger.error(f"Reply generation failed: {e}")
            return "Thank you for your message. We'll process it shortly."


# Singleton instance
openai_service = OpenAIService()


def get_openai_service() -> OpenAIService:
    """Get configured OpenAI service instance."""
    if not openai_service.is_configured():
        openai_service.configure(settings.openai_api_key)
    return openai_service
