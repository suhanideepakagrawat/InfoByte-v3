"""
medicine.py

Medicine retriever orchestrator.

Sources:
- openFDA Drug Label API
- DailyMed

The module returns factual label information only.

It does not generate:
- Medical opinions
- Personalized dosage recommendations
- Treatment recommendations
- Inferred dosage information

Structured dosage values are extracted only when they are explicitly
present in official label text.
"""

import asyncio
import re
from typing import Any, Dict, List, Optional

from app.retrievers.openfda_drug import (
    handle_openfda_drug,
)

from app.retrievers.dailymed import (
    handle_dailymed,
)


def _clean_text(
    text: Optional[str]
) -> Optional[str]:
    """
    Normalize whitespace.
    """
    if not text:
        return None

    text = re.sub(
        r"\r\n?",
        "\n",
        text,
    )

    text = re.sub(
        r"[ \t]+",
        " ",
        text,
    )

    text = re.sub(
        r"\n{3,}",
        "\n\n",
        text,
    )

    return text.strip()


def _extract_amount_per_dose(
    text: str,
) -> Optional[str]:
    """
    Extract an explicitly stated amount per dose.

    Examples:
    - take 2 tablets
    - 1 capsule every 8 hours
    - take 10 mL every 6 hours
    """
    patterns = [
        r"\btake\s+(\d+(?:\.\d+)?\s+"
        r"(?:tablet|tablets|capsule|capsules|"
        r"caplet|caplets|mL|ml|teaspoon|teaspoons))\b",

        r"\b(\d+(?:\.\d+)?\s+"
        r"(?:tablet|tablets|capsule|capsules|"
        r"caplet|caplets|mL|ml|teaspoon|teaspoons))"
        r"\s+every\b",

        r"\b(\d+(?:\.\d+)?\s*"
        r"(?:mg|mcg|g|mL|ml))"
        r"\s+(?:every|once|twice)\b",
    ]

    for pattern in patterns:
        match = re.search(
            pattern,
            text,
            re.IGNORECASE,
        )

        if match:
            return match.group(1).strip()

    return None


def _extract_dose_interval(
    text: str,
) -> Optional[str]:
    """
    Extract an explicitly stated interval.

    Examples:
    - every 6 hours
    - every 4 to 6 hours
    - every 4-6 hours
    """
    patterns = [
        r"\bevery\s+"
        r"(\d+(?:\.\d+)?\s*(?:to|-)\s*"
        r"\d+(?:\.\d+)?\s*hours?)\b",

        r"\bevery\s+"
        r"(\d+(?:\.\d+)?\s*hours?)\b",

        r"\bevery\s+"
        r"(\d+(?:\.\d+)?\s*days?)\b",
    ]

    for pattern in patterns:
        match = re.search(
            pattern,
            text,
            re.IGNORECASE,
        )

        if match:
            return (
                "Every "
                + match.group(1).strip()
            )

    return None


def _extract_maximum_dose(
    text: str,
) -> Optional[str]:
    """
    Extract an explicitly stated maximum daily dose.

    Examples:
    - do not take more than 6 tablets in 24 hours
    - maximum 4 capsules in 24 hours
    """
    patterns = [
        r"(?:do not take|take no|use no)\s+"
        r"more than\s+"
        r"(\d+(?:\.\d+)?\s+"
        r"(?:tablet|tablets|capsule|capsules|"
        r"caplet|caplets|dose|doses|mL|ml)"
        r"\s+(?:in|within|per)\s+"
        r"(?:24 hours|one day|a day|day))",

        r"(?:maximum|max\.?)\s*[:\-]?\s*"
        r"(\d+(?:\.\d+)?\s+"
        r"(?:tablet|tablets|capsule|capsules|"
        r"caplet|caplets|dose|doses|mL|ml)"
        r"\s+(?:in|within|per)\s+"
        r"(?:24 hours|one day|a day|day))",

        r"(?:not to exceed|do not exceed)\s+"
        r"(\d+(?:\.\d+)?\s*"
        r"(?:mg|mcg|g|mL|ml)"
        r"(?:\s+(?:in|within|per)\s+"
        r"(?:24 hours|one day|a day|day))?)",
    ]

    for pattern in patterns:
        match = re.search(
            pattern,
            text,
            re.IGNORECASE,
        )

        if match:
            return match.group(1).strip()

    return None


def parse_dosage_information(
    dosage_text: Optional[str],
) -> Dict[str, Optional[str]]:
    """
    Convert official dosage text into the frontend dosage contract.

    Important:
    No values are calculated or inferred.
    """
    cleaned_text = _clean_text(
        dosage_text
    )

    if not cleaned_text:
        return {
            "label_instructions": None,
            "amount_per_dose": None,
            "dose_interval": None,
            "maximum_dose": None,
        }

    return {
        "label_instructions": cleaned_text,

        "amount_per_dose":
            _extract_amount_per_dose(
                cleaned_text
            ),

        "dose_interval":
            _extract_dose_interval(
                cleaned_text
            ),

        "maximum_dose":
            _extract_maximum_dose(
                cleaned_text
            ),
    }


def _deduplicate_strings(
    values: List[str],
) -> List[str]:
    """
    Remove duplicate text blocks while preserving order.
    """
    seen = set()
    output = []

    for value in values:
        if not value:
            continue

        normalized = re.sub(
            r"\s+",
            " ",
            value.lower(),
        ).strip()

        if normalized in seen:
            continue

        seen.add(normalized)
        output.append(value)

    return output


def _build_medicine_payload(
    query: str,
    openfda_result: Optional[Dict[str, Any]],
    dailymed_result: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Build the final normalized medicine object.
    """
    if openfda_result:
        medicine_name = (
            openfda_result.get(
                "medicine_name"
            )
            or query
        )

        generic_name = (
            openfda_result.get(
                "generic_name"
            )
        )

        brand_names = (
            openfda_result.get(
                "brand_names"
            )
            or []
        )

        active_ingredients = (
            openfda_result.get(
                "active_ingredients"
            )
            or []
        )

        uses = (
            openfda_result.get(
                "uses"
            )
            or []
        )

        dosage = parse_dosage_information(
            openfda_result.get(
                "dosage_and_administration"
            )
        )

        side_effects = _deduplicate_strings(
            openfda_result.get(
                "side_effects"
            )
            or []
        )

        manufacturer = (
            openfda_result.get(
                "manufacturer"
            )
        )

        route = (
            openfda_result.get(
                "route"
            )
            or []
        )

        product_type = (
            openfda_result.get(
                "product_type"
            )
        )

        warnings = (
            openfda_result.get(
                "warnings"
            )
        )

        precautions = (
            openfda_result.get(
                "precautions"
            )
        )

    else:
        medicine_name = (
            dailymed_result.get(
                "medicine_name"
            )
            if dailymed_result
            else query
        )

        generic_name = None
        brand_names = []
        active_ingredients = []
        uses = []

        dosage = {
            "label_instructions": None,
            "amount_per_dose": None,
            "dose_interval": None,
            "maximum_dose": None,
        }

        side_effects = []

        manufacturer = None
        route = []
        product_type = None
        warnings = None
        precautions = None

    official_label_url = None

    if dailymed_result:
        official_label_url = (
            dailymed_result.get(
                "source_url"
            )
        )

    return {
        "medicine_name": medicine_name,

        "generic_name": generic_name,

        "brand_names": brand_names,

        "active_ingredients":
            active_ingredients,

        "uses": uses,

        "dosage": dosage,

        "side_effects": side_effects,

        "manufacturer": manufacturer,

        "route": route,

        "product_type": product_type,

        "warnings": warnings,

        "precautions": precautions,

        "official_label": {
            "source": (
                "DailyMed"
                if official_label_url
                else "openFDA"
            ),

            "url": (
                official_label_url
                or (
                    openfda_result.get(
                        "source_url"
                    )
                    if openfda_result
                    else None
                )
            ),

            "dailymed_set_id": (
                dailymed_result.get(
                    "set_id"
                )
                if dailymed_result
                else None
            ),
        },
    }


async def handle_medicine_query(
    query: str,
) -> Dict[str, Any]:
    """
    Main medicine retriever.

    Matching flow:

    1. Resolve the medicine through openFDA.
    2. Extract its brand, generic name and active ingredients.
    3. Pass those identifiers to DailyMed.
    4. Build one synchronized medicine result.

    This avoids independently matching two potentially
    different drug products.
    """

    query = query.strip()

    if not query:

        return {
            "intent": "medicine",

            "query": query,

            "payload": {
                "medicine": None,
            },

            "results": [],

            "source_results": {},

            "successful_sources": [],

            "failed_sources": [
                "openfda",
                "dailymed",
            ],

            "source_errors": {
                "query":
                    "Medicine query cannot be empty."
            },

            "total_results": 0,
        }

    source_results: Dict[str, Any] = {}

    successful_sources: List[str] = []

    failed_sources: List[str] = []

    source_errors: Dict[str, str] = {}

    openfda_result = None

    dailymed_result = None

    # ========================================================
    # STEP 1: RESOLVE MEDICINE THROUGH OPENFDA
    # ========================================================

    openfda_response = (
        await handle_openfda_drug(
            query
        )
    )

    if (
        openfda_response.get("success")
        and openfda_response.get("result")
    ):

        openfda_result = (
            openfda_response.get(
                "result"
            )
        )

        source_results[
            "openfda"
        ] = openfda_result

        successful_sources.append(
            "openfda"
        )

    else:

        failed_sources.append(
            "openfda"
        )

        source_errors[
            "openfda"
        ] = (
            openfda_response.get(
                "error"
            )
            or "Unknown openFDA error."
        )

    # ========================================================
    # STEP 2: SEARCH DAILYMED USING RESOLVED MEDICINE IDENTITY
    # ========================================================

    if openfda_result:

        brand_names = (
            openfda_result.get(
                "brand_names"
            )
            or []
        )

        generic_name = (
            openfda_result.get(
                "generic_name"
            )
        )

        active_ingredients = (
            openfda_result.get(
                "active_ingredients"
            )
            or []
        )

        dailymed_response = (
            await handle_dailymed(
                query=query,

                brand_names=
                    brand_names,

                generic_name=
                    generic_name,

                active_ingredients=
                    active_ingredients,
            )
        )

    else:

        # openFDA could not resolve the medicine.
        #
        # DailyMed is still allowed to search using the
        # original query as a fallback.

        dailymed_response = (
            await handle_dailymed(
                query=query
            )
        )

    # ========================================================
    # STEP 3: PROCESS DAILYMED RESPONSE
    # ========================================================

    if (
        dailymed_response.get("success")
        and dailymed_response.get("result")
    ):

        dailymed_result = (
            dailymed_response.get(
                "result"
            )
        )

        source_results[
            "dailymed"
        ] = dailymed_result

        successful_sources.append(
            "dailymed"
        )

    else:

        failed_sources.append(
            "dailymed"
        )

        source_errors[
            "dailymed"
        ] = (
            dailymed_response.get(
                "error"
            )
            or "Unknown DailyMed error."
        )

    # ========================================================
    # STEP 4: BUILD FINAL MEDICINE OBJECT
    # ========================================================

    medicine = _build_medicine_payload(
        query=query,

        openfda_result=
            openfda_result,

        dailymed_result=
            dailymed_result,
    )

    # ========================================================
    # BUILD RAW RESULT LIST
    # ========================================================

    results = []

    if openfda_result:

        results.append(
            openfda_result
        )

    if dailymed_result:

        results.append(
            dailymed_result
        )

    # ========================================================
    # FINAL RESPONSE
    # ========================================================

    return {
        "intent":
            "medicine",

        "query":
            query,

        "payload": {

            "medicine":
                medicine,

            "openfda":
                openfda_result,

            "dailymed":
                dailymed_result,
        },

        "results":
            results,

        "source_results":
            source_results,

        "successful_sources":
            successful_sources,

        "failed_sources":
            failed_sources,

        "source_errors":
            source_errors,

        "total_results":
            len(results),
    }