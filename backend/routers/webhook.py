import logging
from datetime import date

from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from db import get_db
from models.models import Farmer, Record, Message, MessageDirection, RecordType
from service.llm import get_openai_service
from service.twilio_service import get_twilio_service, IncomingMessage

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/webhook", tags=["webhook"])


def get_or_create_farmer(
    db: Session,
    phone_number: str,
    name: str,
) -> Farmer:
    """Get existing farmer or create new one by phone number."""
    # Use phone number as external_id
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


def store_records(
    db: Session,
    farmer: Farmer,
    message: Message,
    extracted_records: list,
    input_mode: str,
    raw_transcript: str,
) -> list[Record]:
    """Store extracted records in database."""
    records = []

    for raw in extracted_records:
        try:
            # Get record type
            record_type_str = raw.get("record_type", "unknown")
            try:
                record_type = RecordType(record_type_str)
            except ValueError:
                record_type = RecordType.UNKNOWN

            # Parse occurred_at
            occurred_at = None
            if raw.get("occurred_at"):
                try:
                    occurred_at = date.fromisoformat(raw["occurred_at"])
                except (ValueError, TypeError):
                    pass

            # Get source info
            source = raw.get("source", {})
            quality = raw.get("quality", {})

            record = Record(
                farmer_id=farmer.id,
                message_id=message.id,
                record_type=record_type,
                occurred_at=occurred_at,
                data=raw.get("data", {}),
                source_channel=source.get("channel", "whatsapp"),
                source_input_mode=input_mode,
                source_language=source.get("language", "unknown"),
                confidence=quality.get("confidence", 0.0),
                missing_fields=quality.get("missing_fields", []),
                needs_followup=quality.get("needs_followup", False),
                quality_notes=quality.get("notes"),
                raw_transcript=raw_transcript,
            )
            db.add(record)
            records.append(record)

        except Exception as e:
            logger.error(f"Failed to store record: {e}")
            continue

    if records:
        db.commit()
        for r in records:
            db.refresh(r)

    return records


def generate_confirmation(records: list[Record], language: str = "en") -> str:
    """Generate confirmation message for farmer."""
    if not records:
        return "No records could be extracted from your message. Please try again with more details."

    # Group by record type
    type_counts = {}
    for r in records:
        type_name = r.record_type.value.replace("_", " ")
        type_counts[type_name] = type_counts.get(type_name, 0) + 1

    parts = [f"{count}x {name}" for name, count in type_counts.items()]
    record_summary = ", ".join(parts)

    # Check for followups needed
    followup_records = [r for r in records if r.needs_followup]

    if followup_records:
        missing = set()
        for r in followup_records:
            missing.update(r.missing_fields)
        missing_str = ", ".join(missing)
        return f"Recorded: {record_summary}. Missing info needed: {missing_str}"

    return f"Recorded: {record_summary}. Thank you!"


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
    3. If voice: transcribe with Whisper
    4. Extract records with GPT
    5. Store in database
    6. Send confirmation reply
    """
    twilio = get_twilio_service()
    openai = get_openai_service()

    # Parse form data
    form_data = await request.form()
    form_dict = dict(form_data)

    # Validate Twilio signature (optional but recommended)
    # signature = request.headers.get("X-Twilio-Signature", "")
    # url = str(request.url)
    # if not twilio.validate_signature(url, form_dict, signature):
    #     raise HTTPException(status_code=403, detail="Invalid signature")

    # Parse message
    incoming = twilio.parse_incoming_message(form_dict)
    logger.info(
        f"Received message from {incoming.from_number}: "
        f"{'[voice]' if incoming.is_voice else incoming.body[:50] if incoming.body else '[no body]'}"
    )

    # Get or create farmer
    farmer_name = incoming.profile_name or incoming.from_number
    farmer = get_or_create_farmer(db, incoming.from_number, farmer_name)

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
                return PlainTextResponse("OK")
        else:
            logger.error("Failed to download audio")
            twilio.send_reply(
                incoming.from_number,
                "Sorry, I couldn't download your voice message. Please try again.",
            )
            return PlainTextResponse("OK")

    elif incoming.body:
        transcript = incoming.body
    else:
        logger.warning("No content in message")
        return PlainTextResponse("OK")

    # Extract records
    extracted = await openai.extract(
        transcript=transcript,
        farmer_id=farmer.external_id,
        farmer_name=farmer.name,
        input_mode=input_mode,
        current_date=date.today(),
    )

    # Store records
    records = store_records(
        db=db,
        farmer=farmer,
        message=message,
        extracted_records=extracted,
        input_mode=input_mode,
        raw_transcript=transcript,
    )

    # Mark message as processed
    message.processed = True
    db.commit()

    # Send confirmation
    source_lang = "en"
    if extracted:
        source_lang = extracted[0].get("source", {}).get("language", "en")

    confirmation = generate_confirmation(records, source_lang)
    twilio.send_reply(incoming.from_number, confirmation)

    logger.info(f"Processed message, created {len(records)} records")
    return PlainTextResponse("OK")
