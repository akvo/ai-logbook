import os
from functools import lru_cache

from pydantic_settings import BaseSettings


# Hardcoded OpenAI configuration
OPENAI_TRANSCRIPTION_MODEL = "whisper-1"
OPENAI_EXTRACTION_MODEL = "gpt-4o"
OPENAI_EXTRACTION_PROMPT_FILE = "service/prompt.txt"


class Settings(BaseSettings):
    # Database
    database_url: str = "postgresql://akvo:password@db:5432/logbook"

    # Security
    secret_key: str

    # OpenAI
    openai_api_key: str

    # Twilio
    twilio_account_sid: str
    twilio_auth_token: str
    twilio_whatsapp_number: str = "whatsapp:+14155238886"

    # App
    webdomain: str = "localhost"

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
