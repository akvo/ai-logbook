"""Validation logic for record data completeness."""

from typing import List, Optional
from models.models import RecordType


# All expected fields per record type - ALL must be filled for confirmed=True
RECORD_FIELDS: dict[RecordType, List[str]] = {
    RecordType.CHEMICAL_SPRAY: [
        "crop_variety",
        "plot_or_row",
        "growth_stage",
        "chemical_name",
        "dosage",
        "application_rate",
        "spraying_apparatus_and_method",
        "harvesting_period_days",
        "weather_condition",
        "sprayed_by",
    ],
    RecordType.FERTILIZER_APPLICATION: [
        "crop_variety",
        "plot_or_row",
        "fertilizer_name",
        "input_dealer",
        "rate",
        "farmer_perspective",
        "applied_by",
    ],
    RecordType.IRRIGATION: [
        "crop",
        "variety",
        "plot_or_row",
        "water_amount",
        "rainfall",
        "farmer_perspective",
    ],
    RecordType.SEED_PURCHASE_AND_SOWING: [
        "crop_name",
        "variety",
        "shop_name_and_address",
        "amount_or_number",
        "place_of_sowing",
    ],
    RecordType.HARVEST_AND_PACKAGING: [
        "crop_variety",
        "planting_date",
        "plot_number",
        "harvesting_date",
        "packaging_date",
        "trade_mark",
        "number_of_packs",
        "destination",
        "product_registration_number",
        "farmer_perspective",
    ],
    RecordType.CHEMICAL_PURCHASE: [
        "date_of_buying",
        "chemical_name",
        "quantity",
        "place_of_buying",
        "product_registration_number",
        "production_date",
        "expiry_date",
    ],
    RecordType.CHEMICAL_DISPOSAL: [
        "chemical_name",
        "disposal_date",
        "disposal_method",
    ],
    RecordType.POST_HARVEST_CHEMICAL_USAGE: [
        "chemical_name",
        "container_size",
        "solution_rate",
        "application_method",
        "chemical_quantity",
        "solution_amount_added",
        "application_time",
        "chemical_type",
        "farmer_perspective",
        "signature",
    ],
    RecordType.HAZARD_EVALUATION: [
        "crop_name",
        "cause_of_hazard",
        "evaluation",
        "remedies",
        "signature",
    ],
    RecordType.SPRAYING_TOOL_SANITATION: [
        "cleaning_place",
        "frequency",
        "duty_and_responsibility",
        "cleaning_method",
    ],
    RecordType.TRAINING_UPDATE: [
        "name",
        "chemical_usage",
        "fertilizer_usage",
        "irrigation",
        "harvesting",
        "grading_packaging",
        "sanitation",
        "personal_hygiene",
        "repair_and_maintenance",
        "personal_evaluation",
    ],
    RecordType.CORRECTION_REPORT: [
        "date_reported",
        "problem",
        "source_and_reason",
        "action_taken",
        "signature",
        "date_resolved",
    ],
    RecordType.UNKNOWN: [],
}


def get_null_fields(
    record_type: RecordType,
    occurred_at: Optional[str],
    data: dict,
) -> List[str]:
    """
    Get all fields that are null/empty in a record.

    Args:
        record_type: The type of record
        occurred_at: The occurred_at date (may be null)
        data: The extracted data dictionary

    Returns:
        List of field names that are null or empty
    """
    null_fields = []
    expected_fields = RECORD_FIELDS.get(record_type, [])

    # Check occurred_at
    if occurred_at is None or occurred_at == "":
        null_fields.append("occurred_at")

    # Check all expected data fields
    for field in expected_fields:
        value = data.get(field)
        if value is None or value == "" or value == []:
            null_fields.append(field)

    return null_fields


def should_need_followup(
    record_type: RecordType,
    occurred_at: Optional[str],
    data: dict,
) -> tuple[bool, List[str]]:
    """
    Determine if a record needs follow-up based on null fields.

    Args:
        record_type: The type of record
        occurred_at: The occurred_at date
        data: The extracted data dictionary

    Returns:
        Tuple of (needs_followup, list of null fields)
    """
    null_fields = get_null_fields(record_type, occurred_at, data)
    return len(null_fields) > 0, null_fields


def can_be_confirmed(
    record_type: RecordType,
    occurred_at: Optional[str],
    data: dict,
) -> bool:
    """
    Check if a record can be confirmed (ALL fields are filled).

    Args:
        record_type: The type of record
        occurred_at: The occurred_at date
        data: The extracted data dictionary

    Returns:
        True if ALL fields are filled, False otherwise
    """
    needs_followup, _ = should_need_followup(record_type, occurred_at, data)
    return not needs_followup
