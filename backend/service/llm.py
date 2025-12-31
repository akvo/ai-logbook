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
    ) -> List[dict]:
        """
        Extract structured records from transcript using GPT.

        Args:
            transcript: The farmer's message (text or transcribed voice)
            farmer_id: Farmer's ID
            farmer_name: Farmer's name
            input_mode: 'voice' or 'text'
            current_date: Current date for relative date inference

        Returns:
            List of extracted record dictionaries
        """
        if not self.is_configured():
            logger.error("OpenAI client not configured")
            return []

        if current_date is None:
            current_date = date.today()

        system_prompt = self._load_prompt()

        user_message = f"""Input:
- current_date: "{current_date.isoformat()}"
- farmer_id: "{farmer_id}"
- farmer_name: "{farmer_name}"
- input_mode: "{input_mode}"
- transcript: "{transcript}"
"""

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


# Singleton instance
openai_service = OpenAIService()


def get_openai_service() -> OpenAIService:
    """Get configured OpenAI service instance."""
    if not openai_service.is_configured():
        openai_service.configure(settings.openai_api_key)
    return openai_service
