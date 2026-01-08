from datetime import date

from fastapi import APIRouter, HTTPException

from models.schemas import (
    ExtractionRequest,
    ExtractionResponse,
    ExtractedRecord,
    RecordType,
    SourceInfo,
    QualityInfo,
    InputMode,
    SourceLanguage,
)
from service.llm import get_openai_service

router = APIRouter(prefix="/api/extract", tags=["extraction"])


@router.post("", response_model=ExtractionResponse)
async def extract_records(request: ExtractionRequest):
    """
    Manual extraction endpoint for testing.

    Send a transcript and get structured records back.
    """
    service = get_openai_service()

    if not service.is_configured():
        raise HTTPException(
            status_code=503,
            detail="OpenAI service not configured",
        )

    try:
        raw_records = await service.extract(
            transcript=request.transcript,
            farmer_id=request.farmer_id,
            farmer_name=request.farmer_name,
            input_mode=request.input_mode.value,
            current_date=date.today(),
        )

        if not raw_records:
            return ExtractionResponse(
                success=False,
                records=[],
                error="No records extracted from transcript",
            )

        # Convert raw records to ExtractedRecord schema
        records = []
        for raw in raw_records:
            try:
                # Parse record_type
                record_type_str = raw.get("record_type", "unknown")
                try:
                    record_type = RecordType(record_type_str)
                except ValueError:
                    record_type = RecordType.UNKNOWN

                # Parse source
                source_data = raw.get("source", {})
                input_mode_str = source_data.get("input_mode", "text")
                try:
                    input_mode = InputMode(input_mode_str)
                except ValueError:
                    input_mode = InputMode.TEXT

                language_str = source_data.get("language", "unknown")
                try:
                    language = SourceLanguage(language_str)
                except ValueError:
                    language = SourceLanguage.UNKNOWN

                source = SourceInfo(
                    channel=source_data.get("channel", "whatsapp"),
                    input_mode=input_mode,
                    language=language,
                    message_id=source_data.get("message_id"),
                )

                # Parse quality
                quality_data = raw.get("quality", {})
                quality = QualityInfo(
                    confidence=quality_data.get("confidence", 0.0),
                    missing_fields=quality_data.get("missing_fields", []),
                    needs_followup=quality_data.get("needs_followup", False),
                    notes=quality_data.get("notes"),
                )

                record = ExtractedRecord(
                    record_type=record_type,
                    farmer=raw.get("farmer", {}),
                    occurred_at=raw.get("occurred_at"),
                    source=source,
                    data=raw.get("data", {}),
                    quality=quality,
                )
                records.append(record)

            except Exception as e:
                # Skip malformed records but log the error
                import logging
                logging.error(f"Failed to parse record: {e}")
                continue

        return ExtractionResponse(
            success=True,
            records=records,
        )

    except Exception as e:
        return ExtractionResponse(
            success=False,
            records=[],
            error=str(e),
        )
