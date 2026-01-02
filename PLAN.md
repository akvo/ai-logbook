# AI Logbook Implementation Plan

## Project Overview

An AI-powered farmer record-keeping system for Myanmar GAP (Good Agricultural Practices). Farmers send reports via WhatsApp (voice/text), an LLM extracts structured JSON records, and FastAPI stores them in PostgreSQL.

---

## Current State

| Component | Status |
|-----------|--------|
| FastAPI app skeleton | ✅ Done |
| Docker Compose (backend + postgres) | ✅ Done |
| Database connection (SQLAlchemy) | ✅ Done |
| Alembic migrations setup | ✅ Done |
| LLM extraction prompt | ✅ Done |
| Dependencies (twilio, openai, etc.) | ✅ Done |
| Database models | ❌ Not started |
| API endpoints | ❌ Not started |
| WhatsApp webhook | ❌ Not started |
| LLM service integration | ❌ Not started |
| Tests | ❌ Not started |

---

## Implementation Plan

### Phase 1: Core Data Layer

#### 1.1 Pydantic Schemas (`backend/models/schemas.py`)

Define request/response models matching the prompt template:

- `RecordType` - Enum of 12 record types
- `SourceSchema` - channel, input_mode, language, message_id
- `QualitySchema` - confidence, missing_fields, needs_followup, notes
- `FarmerSchema` - id, name
- `BaseRecordSchema` - record_type, farmer, occurred_at, source, data, quality
- Data schemas for each record type (chemical_spray, fertilizer_application, etc.)

#### 1.2 SQLAlchemy Models (`backend/models/models.py`)

```
Farmer
├── id (UUID, PK)
├── external_id (String, unique) - WhatsApp number or farmer code
├── name (String)
├── phone_number (String)
├── created_at (DateTime)
└── updated_at (DateTime)

Record
├── id (UUID, PK)
├── farmer_id (FK → Farmer)
├── record_type (Enum)
├── occurred_at (Date, nullable)
├── data (JSONB) - flexible storage for record-type-specific fields
├── source_channel (String)
├── source_input_mode (String)
├── source_language (String)
├── source_message_id (String, nullable)
├── confidence (Float)
├── missing_fields (ARRAY[String])
├── needs_followup (Boolean)
├── quality_notes (Text)
├── created_at (DateTime)
└── raw_transcript (Text) - original message for audit

Message
├── id (UUID, PK)
├── farmer_id (FK → Farmer)
├── twilio_message_sid (String, unique)
├── direction (Enum: inbound/outbound)
├── content (Text)
├── media_url (String, nullable) - for voice messages
├── processed (Boolean)
├── created_at (DateTime)
└── records (relationship → Record[])
```

#### 1.3 Database Migration

- Create initial migration with all tables
- Run: `alembic revision --autogenerate -m "initial schema"`

---

### Phase 2: LLM Extraction Service

#### 2.1 OpenAI Service (`backend/service/llm.py`)

```python
class OpenAIService:
    - __init__(api_key, model="gpt-4o")

    # Transcription (Whisper)
    - transcribe_audio(audio_url, audio_file, language) → TranscriptionResponse

    # Extraction (GPT)
    - load_prompt() → str
    - extract(transcript, farmer_id, farmer_name, input_mode, current_date) → list[dict]
    - _build_messages(transcript, metadata) → list
    - _parse_response(response) → list[dict]
    - _validate_output(records) → list[dict]
```

Key considerations:
- Load `prompt.txt` as system message
- Build user message with: current_date, farmer_id, farmer_name, input_mode, transcript
- Parse JSON response (handle array or single object)
- Validate against expected schema
- Handle API errors gracefully
- Use async client for both transcription and chat completion

#### 2.2 Configuration (`backend/core/config.py`)

Environment variables (from docker-compose):
```python
class Settings(BaseSettings):
    database_url: str
    secret_key: str
    openai_api_key: str
    twilio_account_sid: str
    twilio_auth_token: str
    twilio_whatsapp_number: str
    webdomain: str = "localhost"
```

Hardcoded OpenAI config (in `backend/core/config.py` or `main.py`):
```python
# OpenAI Models
OPENAI_TRANSCRIPTION_MODEL = "whisper-1"
OPENAI_EXTRACTION_MODEL = "gpt-4o"
OPENAI_EXTRACTION_PROMPT_FILE = "service/prompt.txt"
```

#### 2.3 Processing Flow

```
Voice Message → Whisper (transcription) → GPT (extraction with prompt.txt) → Database
Text Message  → GPT (extraction with prompt.txt) → Database
```

The extraction prompt (`prompt.txt`) instructs GPT to:
1. Parse the transcript (from Whisper or direct text)
2. Extract structured JSON matching the record schema
3. Return data ready for database insertion

---

### Phase 3: API Endpoints

#### 3.1 Router Structure

```
backend/
├── routers/
│   ├── __init__.py
│   ├── farmers.py      # CRUD for farmers
│   ├── records.py      # CRUD for records
│   ├── webhook.py      # WhatsApp webhook handler
│   └── health.py       # Health check (move from main.py)
```

#### 3.2 Farmer Endpoints (`/api/farmers`)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/farmers` | List all farmers (paginated) |
| GET | `/api/farmers/{id}` | Get farmer by ID |
| POST | `/api/farmers` | Create new farmer |
| PUT | `/api/farmers/{id}` | Update farmer |
| DELETE | `/api/farmers/{id}` | Delete farmer |
| GET | `/api/farmers/{id}/records` | Get farmer's records |

#### 3.3 Record Endpoints (`/api/records`)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/records` | List records (filterable by type, date, farmer) |
| GET | `/api/records/{id}` | Get record by ID |
| POST | `/api/records` | Create record manually |
| PUT | `/api/records/{id}` | Update record |
| DELETE | `/api/records/{id}` | Delete record |
| GET | `/api/records/followup` | Get records needing followup |

#### 3.4 Extraction Endpoint (`/api/extract`)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/extract` | Manual extraction (for testing) |

Request body:
```json
{
  "farmer_id": "F001",
  "farmer_name": "U Kyaw",
  "input_mode": "text",
  "transcript": "Yesterday I sprayed pesticide..."
}
```

---

### Phase 4: WhatsApp Integration

#### 4.1 Twilio Webhook (`/api/webhook/whatsapp`)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/webhook/whatsapp` | Receive incoming WhatsApp messages |

Flow:
1. Validate Twilio signature
2. Parse incoming message (text or voice)
3. If voice: download and transcribe (Twilio or Whisper)
4. Look up or create farmer by phone number
5. Call LLM extraction service
6. Store extracted records
7. Send confirmation reply via Twilio

#### 4.2 Twilio Service (`backend/service/twilio_service.py`)

```python
class TwilioService:
    - __init__(account_sid, auth_token, whatsapp_number)
    - validate_signature(request) → bool
    - parse_incoming_message(form_data) → IncomingMessage
    - send_reply(to, body) → None
    - download_media(media_url) → bytes
```

#### 4.3 Voice Transcription (in `backend/service/llm.py`)

Use OpenAI Whisper API for voice-to-text (no ffmpeg needed - Whisper handles ogg/opus natively):

```python
async def transcribe_audio(
    self,
    audio_url: Optional[str] = None,
    audio_file: Optional[bytes] = None,
    language: Optional[str] = None,
    response_format: str = "json",
) -> Optional[TranscriptionResponse]:
```

Returns `TranscriptionResponse`:
```python
@dataclass
class TranscriptionResponse:
    text: str
    language: Optional[str] = None
    duration: Optional[float] = None
    words: Optional[list] = None
    segments: Optional[list] = None
```

Flow for voice messages:
1. Twilio webhook receives message with `MediaUrl0`
2. Download audio via httpx (with Twilio auth)
3. Wrap bytes in BytesIO with filename
4. Call `client.audio.transcriptions.create(model="whisper-1", file=audio_buffer)`
5. Return transcript text → continue with LLM extraction

---

### Phase 5: Business Logic

#### 5.1 Processing Pipeline (`backend/service/pipeline.py`)

```python
class MessageProcessor:
    - process_message(message: IncomingMessage) → list[Record]
    - _get_or_create_farmer(phone, name) → Farmer
    - _determine_input_mode(message) → str
    - _get_transcript(message) → str
    - _store_records(farmer, records, raw_transcript) → list[Record]
    - _generate_confirmation(records) → str
```

#### 5.2 Confirmation Messages

Generate human-readable confirmation in farmer's language:
- "Recorded: 1 chemical spray, 1 fertilizer application on 2024-01-15"
- "Missing info needed: Please provide the chemical name used"

---

### Phase 6: Testing

#### 6.1 Test Structure

```
backend/tests/
├── conftest.py           # Fixtures (test DB, clients)
├── test_models.py        # Model unit tests
├── test_llm_service.py   # LLM extraction tests
├── test_farmers_api.py   # Farmer endpoint tests
├── test_records_api.py   # Record endpoint tests
├── test_webhook.py       # Webhook integration tests
└── test_pipeline.py      # End-to-end pipeline tests
```

#### 6.2 Test Fixtures

- Sample transcripts for each record type
- Expected JSON outputs
- Mock LLM responses
- Test database with seed data

---

### Phase 7: Production Readiness

#### 7.1 Error Handling

- Global exception handler
- Structured error responses
- Retry logic for LLM calls
- Dead letter queue for failed messages

#### 7.2 Logging

- Structured JSON logging
- Request/response logging
- LLM call logging (prompt, response, tokens)
- Webhook event logging

#### 7.3 Security

- Twilio signature validation
- Rate limiting
- Input sanitization
- API authentication (optional, for admin endpoints)

#### 7.4 Monitoring

- Health check endpoint (already exists)
- Metrics endpoint (record counts, success rates)
- Error alerting

---

## File Structure (Final)

```
backend/
├── main.py
├── db.py
├── requirements.txt
├── alembic.ini
├── alembic/
│   └── versions/
│       └── 001_initial_schema.py
├── core/
│   ├── __init__.py
│   └── config.py
├── models/
│   ├── __init__.py
│   ├── models.py          # SQLAlchemy models
│   └── schemas.py         # Pydantic schemas
├── routers/
│   ├── __init__.py
│   ├── farmers.py
│   ├── records.py
│   ├── webhook.py
│   └── extract.py
├── service/
│   ├── __init__.py
│   ├── prompt.txt
│   ├── llm.py             # LLM extraction + Whisper transcription
│   ├── twilio_service.py
│   └── pipeline.py
└── tests/
    ├── conftest.py
    ├── test_models.py
    ├── test_llm_service.py
    ├── test_farmers_api.py
    ├── test_records_api.py
    └── test_webhook.py
```

---

## Dependencies to Add

```txt
# Add to requirements.txt
pydantic-settings    # Environment variable management
python-dotenv        # .env file support
httpx                # Async HTTP client (for audio download)
```

---

## Environment Variables

See `.env.example` - copy to `.env` and fill in your values.

---

## Implementation Order

1. **Phase 1.2** - SQLAlchemy models (foundation)
2. **Phase 1.1** - Pydantic schemas
3. **Phase 1.3** - Initial migration
4. **Phase 2.2** - Config/settings
5. **Phase 2.1** - LLM service
6. **Phase 3.2** - Farmer CRUD
7. **Phase 3.3** - Record CRUD
8. **Phase 3.4** - Manual extraction endpoint
9. **Phase 4** - WhatsApp webhook
10. **Phase 5** - Processing pipeline
11. **Phase 6** - Tests
12. **Phase 7** - Production hardening
