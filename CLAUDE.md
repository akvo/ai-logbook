# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AI Logbook is an agricultural record-keeping system for Myanmar GAP (Good Agricultural Practices). Farmers send reports via WhatsApp (voice or text), which are transcribed, extracted into structured records using OpenAI, and stored in PostgreSQL.

## Development Commands

```bash
# Start all services (database + backend)
docker compose up

# Reset records and messages (keeps farmers)
./database/script/reset_records.sh

# Run database migrations
docker compose exec backend alembic upgrade head

# Create new migration
docker compose exec backend alembic revision --autogenerate -m "description"
```

## Architecture

### Data Flow
```
WhatsApp Message → Twilio Webhook → Transcribe (Whisper) → Extract (GPT-4o) → Store in DB → Generate Reply (GPT-4o) → Send via Twilio
```

### Key Components

**Webhook Handler** (`routers/webhook.py`):
- Receives Twilio WhatsApp messages
- Checks for pending unconfirmed records before creating new ones
- Updates existing records when farmer replies to follow-up questions
- Uses `get_pending_record()` to find unconfirmed records for a farmer

**LLM Service** (`service/llm.py`):
- `transcribe_audio()` - Whisper API for voice messages
- `extract()` - GPT-4o extraction with existing record context for follow-ups
- `generate_reply()` - Natural language follow-up questions and confirmations

**Validation** (`service/validation.py`):
- `RECORD_FIELDS` - All expected fields per record type
- `should_need_followup()` - Returns (bool, list of null fields)
- `can_be_confirmed()` - True only when ALL fields are filled

**Extraction Prompt** (`service/prompt.txt`):
- Defines 12 record types with field templates
- Includes follow-up response handling instructions

### Record Lifecycle
1. Farmer sends message → Record created with `confirmed=False`, `needs_followup=True`
2. Bot asks for missing fields
3. Farmer replies → Same record updated (merged data)
4. Repeat until all fields filled → `confirmed=True`
5. Bot shows summary, asks for corrections

### Database Models
- `Farmer` - external_id (phone), name
- `Record` - record_type, data (JSONB), missing_fields, needs_followup, confirmed
- `Message` - Twilio message tracking

## API Endpoints

- `GET /api/records?needs_followup=true&confirmed=false` - Filter records
- `POST /api/webhook/whatsapp` - Twilio webhook
- `POST /api/extract` - Manual extraction testing
- Interactive docs: http://localhost:8000/api/docs

## Environment Variables

Required in `.env`:
- `OPENAI_API_KEY` - For transcription and extraction
- `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_WHATSAPP_NUMBER` - WhatsApp integration
- `SECRET_KEY` - Application secret
