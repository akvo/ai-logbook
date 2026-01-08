import logging
from datetime import date

from fastapi import APIRouter, Request, Depends, Response
from sqlalchemy.orm import Session

from db import get_db
from models.models import Farmer, Record, Message, MessageDirection, RecordType
from service.llm import get_openai_service
from service.twilio_service import get_twilio_service, IncomingMessage
from service.validation import should_need_followup, can_be_confirmed

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/webhook", tags=["webhook"])


def get_pending_record(db: Session, farmer: Farmer) -> Record | None:
    """Get the most recent unconfirmed record for a farmer."""
    return (
        db.query(Record)
        .filter(
            Record.farmer_id == farmer.id,
            Record.confirmed == False,  # noqa: E712
            Record.needs_followup == True,  # noqa: E712
        )
        .order_by(Record.created_at.desc())
        .first()
    )


def get_or_create_farmer(
    db: Session,
    phone_number: str,
    name: str,
) -> Farmer:
    """Get existing farmer or create new one by phone number."""
    farmer = db.query(Farmer).filter(Farmer.external_id == phone_number).first()

    if not farmer:
        farmer = Farmer(
            external_id=phone_number,
            name=name,
            phone_number=phone_number,
        )
        db.add(farmer)
        db.commit()
        db.refresh(farmer)
        logger.info(f"Created new farmer: {farmer.external_id}")

    return farmer


def store_message(
    db: Session,
    farmer: Farmer,
    incoming: IncomingMessage,
) -> Message:
    """Store incoming message in database."""
    message = Message(
        farmer_id=farmer.id,
        twilio_message_sid=incoming.message_sid,
        direction=MessageDirection.INBOUND,
        content=incoming.body,
        media_url=incoming.media_url,
        processed=False,
    )
    db.add(message)
    db.commit()
    db.refresh(message)
    return message


def update_record(
    db: Session,
    record: Record,
    extracted_data: dict,
    raw_transcript: str,
) -> Record:
    """Update an existing record with new extracted data."""
    raw = extracted_data

    # Parse occurred_at
    occurred_at_str = raw.get("occurred_at")
    if occurred_at_str:
        try:
            record.occurred_at = date.fromisoformat(occurred_at_str)
        except (ValueError, TypeError):
            pass

    # Merge new data with existing data
    new_data = raw.get("data", {})
    merged_data = dict(record.data)  # Copy existing
    for key, value in new_data.items():
        if value is not None and value != "":
            merged_data[key] = value
    record.data = merged_data

    # Update quality info
    quality = raw.get("quality", {})
    if quality.get("confidence"):
        record.confidence = quality["confidence"]
    if quality.get("notes"):
        record.quality_notes = quality["notes"]

    # Append to raw transcript
    record.raw_transcript = f"{record.raw_transcript}\n---\n{raw_transcript}"

    # Re-validate with merged data
    occurred_at_str = record.occurred_at.isoformat() if record.occurred_at else None
    needs_followup, validation_missing = should_need_followup(
        record_type=record.record_type,
        occurred_at=occurred_at_str,
        data=record.data,
    )

    record.missing_fields = validation_missing
    record.needs_followup = needs_followup
    record.confirmed = can_be_confirmed(record.record_type, occurred_at_str, record.data)

    db.commit()
    db.refresh(record)
    return record


def create_record(
    db: Session,
    farmer: Farmer,
    message: Message,
    extracted_data: dict,
    input_mode: str,
    raw_transcript: str,
) -> Record:
    """Create a new record from extracted data."""
    raw = extracted_data

    # Get record type
    record_type_str = raw.get("record_type", "unknown")
    try:
        record_type = RecordType(record_type_str)
    except ValueError:
        record_type = RecordType.UNKNOWN

    # Parse occurred_at
    occurred_at = None
    occurred_at_str = raw.get("occurred_at")
    if occurred_at_str:
        try:
            occurred_at = date.fromisoformat(occurred_at_str)
        except (ValueError, TypeError):
            pass

    # Get source info
    source = raw.get("source", {})
    quality = raw.get("quality", {})
    data = raw.get("data", {})

    # Server-side validation: check for null fields
    needs_followup, validation_missing = should_need_followup(
        record_type=record_type,
        occurred_at=occurred_at_str,
        data=data,
    )

    # Merge LLM's missing_fields with validation missing fields
    llm_missing = quality.get("missing_fields", [])
    all_missing = list(set(llm_missing + validation_missing))

    # Determine if record can be confirmed
    confirmed = can_be_confirmed(record_type, occurred_at_str, data)

    record = Record(
        farmer_id=farmer.id,
        message_id=message.id,
        record_type=record_type,
        occurred_at=occurred_at,
        data=data,
        source_channel=source.get("channel", "whatsapp"),
        source_input_mode=input_mode,
        source_language=source.get("language", "unknown"),
        confidence=quality.get("confidence", 0.0),
        missing_fields=all_missing,
        needs_followup=needs_followup,
        confirmed=confirmed,
        quality_notes=quality.get("notes"),
        raw_transcript=raw_transcript,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


@router.post("/whatsapp")
async def whatsapp_webhook(
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Handle incoming WhatsApp messages from Twilio.

    Flow:
    1. Parse incoming message
    2. Get or create farmer
    3. Check for pending (unconfirmed) record
    4. If voice: transcribe with Whisper
    5. Extract/update records with GPT
    6. Store or update in database
    7. Generate natural reply using GPT
    8. Send reply
    """
    twilio = get_twilio_service()
    openai = get_openai_service()

    # Parse form data
    form_data = await request.form()
    form_dict = dict(form_data)

    # Parse message
    incoming = twilio.parse_incoming_message(form_dict)
    logger.info(
        f"Received message from {incoming.from_number}: "
        f"{'[voice]' if incoming.is_voice else incoming.body[:50] if incoming.body else '[no body]'}"
    )

    # Get or create farmer
    farmer_name = incoming.profile_name or incoming.from_number
    farmer = get_or_create_farmer(db, incoming.from_number, farmer_name)

    # Check for pending unconfirmed record
    pending_record = get_pending_record(db, farmer)

    # Store message
    message = store_message(db, farmer, incoming)

    # Get transcript
    transcript = ""
    input_mode = "text"

    if incoming.is_voice and incoming.media_url:
        # Download and transcribe voice message
        input_mode = "voice"
        audio_bytes = await twilio.download_media(incoming.media_url)

        if audio_bytes:
            result = await openai.transcribe_audio(audio_file=audio_bytes)
            if result:
                transcript = result.text
                logger.info(f"Transcribed: {transcript[:100]}...")
            else:
                logger.error("Transcription failed")
                twilio.send_reply(
                    incoming.from_number,
                    "Sorry, I couldn't process your voice message. Please try again.",
                )
                return Response(status_code=200)
        else:
            logger.error("Failed to download audio")
            twilio.send_reply(
                incoming.from_number,
                "Sorry, I couldn't download your voice message. Please try again.",
            )
            return Response(status_code=200)

    elif incoming.body:
        transcript = incoming.body
    else:
        logger.warning("No content in message")
        return Response(status_code=200)

    # Prepare existing record context for extraction if pending
    existing_record_context = None
    if pending_record:
        existing_record_context = {
            "record_type": pending_record.record_type.value,
            "data": pending_record.data,
            "missing_fields": pending_record.missing_fields,
            "occurred_at": pending_record.occurred_at.isoformat() if pending_record.occurred_at else None,
        }
        logger.info(f"Found pending record {pending_record.id}, will update instead of create")

    # Extract records (with context if updating)
    extracted = await openai.extract(
        transcript=transcript,
        farmer_id=farmer.external_id,
        farmer_name=farmer.name,
        input_mode=input_mode,
        current_date=date.today(),
        existing_record=existing_record_context,
    )

    # Process extracted data
    record = None
    if pending_record and extracted:
        # Update existing record
        record = update_record(
            db=db,
            record=pending_record,
            extracted_data=extracted[0],
            raw_transcript=transcript,
        )
        logger.info(f"Updated existing record {record.id}")
    elif extracted:
        # Create new record
        record = create_record(
            db=db,
            farmer=farmer,
            message=message,
            extracted_data=extracted[0],
            input_mode=input_mode,
            raw_transcript=transcript,
        )
        logger.info(f"Created new record {record.id}")

    # Mark message as processed
    message.processed = True
    db.commit()

    # Generate reply using OpenAI
    if not record:
        reply = "Sorry, I couldn't extract any records from your message. Please try again with more details."
    else:
        source_lang = record.source_language or "en"

        # Build existing data with occurred_at
        existing_data = dict(record.data)
        if record.occurred_at:
            existing_data["occurred_at"] = record.occurred_at.isoformat()

        reply = await openai.generate_reply(
            record_type=record.record_type.value,
            existing_data=existing_data,
            missing_fields=record.missing_fields,
            language=source_lang,
            farmer_name=farmer.name,
            is_confirmed=record.confirmed,
        )

    twilio.send_reply(incoming.from_number, reply)

    action = "updated" if pending_record else "created"
    logger.info(f"Processed message, {action} record")
    return Response(status_code=200)
