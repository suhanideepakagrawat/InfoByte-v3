"""
medicine.py

Medicine retriever orchestrator.

Sources:
- openFDA Drug Label API
- DailyMed
- Indian Medicine Dataset (brand resolution fallback)

The module returns factual label information only.

It does not generate:
- Medical opinions
- Personalized dosage recommendations
- Treatment recommendations
- Inferred dosage information

Structured dosage values are extracted only when they are explicitly
present in official label text.
"""

import ast
import re
from typing import Any, Dict, List, Optional, Tuple

from app.retrievers.openfda_drug import (
    handle_openfda_drug,
)

from app.retrievers.dailymed import (
    handle_dailymed,
)

from app.pipeline.medicine_resolver import (
    resolve_medicine_query,
)

from app.pipeline.medicine_formatter import (
    format_medicine_payload,
)


# ============================================================
# TEXT HELPERS
# ============================================================

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


def _normalize_identity(
    value: Any,
) -> str:
    """
    Normalize medicine or ingredient names for comparison.
    """
    if value is None:
        return ""

    return re.sub(
        r"[^a-z0-9]+",
        " ",
        str(value).lower(),
    ).strip()


# ============================================================
# DOSAGE EXTRACTION
# ============================================================

def _extract_amount_per_dose(
    text: str,
) -> Optional[str]:
    """
    Extract an explicitly stated amount per dose.
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


# ============================================================
# GENERAL HELPERS
# ============================================================

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


def _extract_openfda_ingredient_names(
    openfda_result: Optional[Dict[str, Any]],
) -> List[str]:
    """
    Extract ingredient names from the normalized openFDA result.
    """
    if not openfda_result:
        return []

    output = []
    seen = set()

    for ingredient in (
        openfda_result.get(
            "active_ingredients"
        )
        or []
    ):

        if isinstance(
            ingredient,
            dict,
        ):
            name = ingredient.get(
                "name"
            )

        else:
            name = ingredient

        if not name:
            continue

        name = str(name).strip()

        normalized = _normalize_identity(
            name
        )

        if (
            normalized
            and normalized not in seen
        ):
            seen.add(
                normalized
            )

            output.append(
                name
            )

    return output


def _ingredients_overlap(
    resolved_ingredients: List[str],
    openfda_result: Optional[Dict[str, Any]],
) -> bool:
    """
    Determine whether an openFDA result is related to at least one
    ingredient resolved from the Indian medicine dataset.
    """
    if not resolved_ingredients:
        return False

    if not openfda_result:
        return False

    candidate_values = []

    candidate_values.extend(
        _extract_openfda_ingredient_names(
            openfda_result
        )
    )

    generic_name = (
        openfda_result.get(
            "generic_name"
        )
    )

    if generic_name:
        candidate_values.append(
            generic_name
        )

    candidate_values.extend(
        openfda_result.get(
            "brand_names"
        )
        or []
    )

    medicine_name = (
        openfda_result.get(
            "medicine_name"
        )
    )

    if medicine_name:
        candidate_values.append(
            medicine_name
        )

    normalized_candidates = [
        _normalize_identity(
            value
        )
        for value in candidate_values
        if value
    ]

    for expected in resolved_ingredients:

        normalized_expected = (
            _normalize_identity(
                expected
            )
        )

        if not normalized_expected:
            continue

        expected_tokens = set(
            normalized_expected.split()
        )

        for candidate in normalized_candidates:

            if not candidate:
                continue

            if (
                normalized_expected
                == candidate
            ):
                return True

            if (
                normalized_expected
                in candidate
            ):
                return True

            if (
                candidate
                in normalized_expected
            ):
                return True

            candidate_tokens = set(
                candidate.split()
            )

            if (
                expected_tokens
                and expected_tokens.issubset(
                    candidate_tokens
                )
            ):
                return True

    return False


def _build_indian_fallback_queries(
    resolution: Dict[str, Any],
) -> List[str]:
    """
    Build ordered openFDA fallback queries.
    """
    search_terms = (
        resolution.get(
            "search_terms"
        )
        or {}
    )

    queries = []

    combination = (
        search_terms.get(
            "combination"
        )
    )

    if combination:
        queries.append(
            combination
        )

    queries.extend(
        search_terms.get(
            "individual"
        )
        or []
    )

    output = []
    seen = set()

    for value in queries:

        if not value:
            continue

        value = str(
            value
        ).strip()

        normalized = (
            _normalize_identity(
                value
            )
        )

        if (
            not normalized
            or normalized in seen
        ):
            continue

        seen.add(
            normalized
        )

        output.append(
            value
        )

    return output


# ============================================================
# INDIAN MEDICINE FALLBACK
# ============================================================

async def _resolve_openfda_through_indian_dataset(
    query: str,
) -> Tuple[
    Optional[Dict[str, Any]],
    Optional[Dict[str, Any]],
    Optional[str],
    List[Dict[str, Any]],
]:
    """
    Resolve an Indian medicine brand and attempt openFDA searches
    using the extracted ingredient identities.
    """

    try:

        resolution = (
            resolve_medicine_query(
                query
            )
        )

    except Exception as exc:

        return (
            {
                "resolved": False,
                "query": query,
                "status":
                    "INDIAN_RESOLUTION_ERROR",
                "error": str(exc),
            },
            None,
            None,
            [],
        )

    if not resolution.get(
        "resolved"
    ):

        return (
            resolution,
            None,
            None,
            [],
        )

    resolved_ingredients = (
        resolution.get(
            "ingredients"
        )
        or []
    )

    fallback_queries = (
        _build_indian_fallback_queries(
            resolution
        )
    )

    attempted_queries = []

    for fallback_query in fallback_queries:

        response = (
            await handle_openfda_drug(
                fallback_query
            )
        )

        attempt = {
            "query":
                fallback_query,

            "success":
                bool(
                    response.get(
                        "success"
                    )
                ),

            "accepted":
                False,

            "error":
                response.get(
                    "error"
                ),
        }

        candidate = (
            response.get(
                "result"
            )
            if response.get(
                "success"
            )
            else None
        )

        if (
            candidate
            and _ingredients_overlap(
                resolved_ingredients,
                candidate,
            )
        ):

            attempt[
                "accepted"
            ] = True

            attempted_queries.append(
                attempt
            )

            return (
                resolution,
                candidate,
                fallback_query,
                attempted_queries,
            )

        attempted_queries.append(
            attempt
        )

    return (
        resolution,
        None,
        None,
        attempted_queries,
    )


# ============================================================
# PAYLOAD BUILDER
# ============================================================

def _build_medicine_payload(
    query: str,
    openfda_result: Optional[Dict[str, Any]],
    dailymed_result: Optional[Dict[str, Any]],
    indian_resolution: Optional[
        Dict[str, Any]
    ] = None,
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

        dosage = (
            parse_dosage_information(
                openfda_result.get(
                    "dosage_and_administration"
                )
            )
        )

        side_effects = (
            _deduplicate_strings(
                openfda_result.get(
                    "side_effects"
                )
                or []
            )
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
            "label_instructions":
                None,

            "amount_per_dose":
                None,

            "dose_interval":
                None,

            "maximum_dose":
                None,
        }

        side_effects = []

        manufacturer = None
        route = []
        product_type = None
        warnings = None
        precautions = None

    indian_product = None
    resolved_ingredients = []

    if indian_resolution:

        indian_product = (
            indian_resolution.get(
                "product"
            )
        )

        resolved_ingredients = (
            indian_resolution.get(
                "ingredients"
            )
            or []
        )

        if indian_product:

            indian_brand_name = (
                indian_product.get(
                    "medicine_name"
                )
            )

            if indian_brand_name:
                medicine_name = (
                    indian_brand_name
                )

            indian_manufacturer = (
                indian_product.get(
                    "manufacturer"
                )
            )

            if indian_manufacturer:
                manufacturer = (
                    indian_manufacturer
                )

    official_label_url = None

    if dailymed_result:

        official_label_url = (
            dailymed_result.get(
                "source_url"
            )
        )

    structured_sections = {
        "uses": {"title": "Uses", "items": uses},
        "dosage": {
            "title": "Dosage & Administration",
            "raw_text": dosage.get("label_instructions") if isinstance(dosage, dict) else None,
            "facts": {
                "amount_per_dose": dosage.get("amount_per_dose") if isinstance(dosage, dict) else None,
                "dose_interval": dosage.get("dose_interval") if isinstance(dosage, dict) else None,
                "maximum_dose": dosage.get("maximum_dose") if isinstance(dosage, dict) else None,
            },
        },
        "side_effects": {"title": "Side Effects / Adverse Reactions", "items": side_effects},
        "warnings": {"title": "Warnings", "raw_text": warnings},
        "precautions": {"title": "Precautions", "raw_text": precautions},
    }

    return {
        "structured_sections": structured_sections,

        "medicine_name":
            medicine_name,

        "generic_name":
            generic_name,

        "brand_names":
            brand_names,

        "active_ingredients":
            active_ingredients,

        "uses":
            uses,

        "dosage":
            dosage,

        "side_effects":
            side_effects,

        "manufacturer":
            manufacturer,

        "route":
            route,

        "product_type":
            product_type,

        "warnings":
            warnings,

        "precautions":
            precautions,

        "indian_brand_resolution": (
            {
                "resolved":
                    True,

                "product":
                    indian_product,

                "resolved_ingredients":
                    resolved_ingredients,

                "status":
                    indian_resolution.get(
                        "status"
                    ),

                "match_type":
                    indian_resolution.get(
                        "match_type"
                    ),

                "match_score":
                    indian_resolution.get(
                        "match_score"
                    ),
            }
            if indian_resolution
            and indian_resolution.get(
                "resolved"
            )
            else None
        ),

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


# ============================================================
# MAIN MEDICINE HANDLER
# ============================================================

async def _handle_medicine_query_single_label(
    query: str,
) -> Dict[str, Any]:
    """
    Main medicine retriever single label processor.
    """

    query = str(
        query or ""
    ).strip()

    if not query:

        return {
            "intent":
                "medicine",

            "query":
                query,

            "payload": {
                "medicine":
                    None,

                "openfda":
                    None,

                "dailymed":
                    None,

                "indian_medicine_resolution":
                    None,
            },

            "results":
                [],

            "source_results":
                {},

            "successful_sources":
                [],

            "failed_sources": [
                "openfda",
                "dailymed",
            ],

            "source_errors": {
                "query":
                    "Medicine query cannot be empty."
            },

            "total_results":
                0,
        }

    source_results: Dict[
        str,
        Any,
    ] = {}

    successful_sources: List[
        str
    ] = []

    failed_sources: List[
        str
    ] = []

    source_errors: Dict[
        str,
        str,
    ] = {}

    openfda_result = None
    dailymed_result = None
    indian_resolution = None

    resolution_path = (
        "direct_openfda"
    )

    resolved_openfda_query = (
        query
    )

    fallback_attempts = []

    # STEP 1: PRESERVE EXISTING DIRECT OPENFDA FLOW
    direct_openfda_response = (
        await handle_openfda_drug(
            query
        )
    )

    if (
        direct_openfda_response.get(
            "success"
        )
        and direct_openfda_response.get(
            "result"
        )
    ):

        openfda_result = (
            direct_openfda_response.get(
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

        direct_openfda_error = (
            direct_openfda_response.get(
                "error"
            )
            or "Unknown openFDA error."
        )

        # STEP 2: INDIAN MEDICINE FALLBACK
        (
            indian_resolution,
            fallback_openfda_result,
            successful_fallback_query,
            fallback_attempts,
        ) = (
            await _resolve_openfda_through_indian_dataset(
                query
            )
        )

        if indian_resolution:

            source_results[
                "indian_medicine"
            ] = indian_resolution

            if indian_resolution.get(
                "resolved"
            ):

                successful_sources.append(
                    "indian_medicine"
                )

        if fallback_openfda_result:

            openfda_result = (
                fallback_openfda_result
            )

            resolved_openfda_query = (
                successful_fallback_query
                or query
            )

            resolution_path = (
                "indian_brand_to_openfda"
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
                direct_openfda_error
            )

            if (
                indian_resolution
                and indian_resolution.get(
                    "resolved"
                )
            ):

                resolution_path = (
                    "indian_brand_resolved_"
                    "official_label_not_found"
                )

                source_errors[
                    "openfda_fallback"
                ] = (
                    "The Indian medicine brand was "
                    "resolved successfully, but no "
                    "sufficiently related openFDA "
                    "label was found."
                )

            elif (
                indian_resolution
                and indian_resolution.get(
                    "status"
                )
                == "INDIAN_RESOLUTION_ERROR"
            ):

                source_errors[
                    "indian_medicine"
                ] = (
                    indian_resolution.get(
                        "error"
                    )
                    or
                    "Indian medicine resolution failed."
                )

            else:

                source_errors[
                    "indian_medicine"
                ] = (
                    "No matching medicine was found "
                    "in the Indian medicine dataset."
                )

    # STEP 3: SEARCH DAILYMED
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
                query=(
                    resolved_openfda_query
                    if indian_resolution
                    and indian_resolution.get(
                        "resolved"
                    )
                    else query
                ),

                brand_names=
                    brand_names,

                generic_name=
                    generic_name,

                active_ingredients=
                    active_ingredients,
            )
        )

    elif (
        indian_resolution
        and indian_resolution.get(
            "resolved"
        )
    ):

        resolved_ingredients = (
            indian_resolution.get(
                "ingredients"
            )
            or []
        )

        search_terms = (
            indian_resolution.get(
                "search_terms"
            )
            or {}
        )

        dailymed_query = (
            search_terms.get(
                "combination"
            )
            or (
                resolved_ingredients[0]
                if resolved_ingredients
                else query
            )
        )

        ingredient_objects = [
            {
                "name":
                    ingredient,

                "strength":
                    None,
            }
            for ingredient
            in resolved_ingredients
        ]

        dailymed_response = (
            await handle_dailymed(
                query=dailymed_query,

                brand_names=[],

                generic_name=None,

                active_ingredients=
                    ingredient_objects,
            )
        )

    else:

        dailymed_response = (
            await handle_dailymed(
                query=query
            )
        )

    # STEP 4: PROCESS DAILYMED RESPONSE
    if (
        dailymed_response.get(
            "success"
        )
        and dailymed_response.get(
            "result"
        )
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

    # STEP 5: BUILD FINAL MEDICINE OBJECT
    medicine = (
        _build_medicine_payload(
            query=query,

            openfda_result=
                openfda_result,

            dailymed_result=
                dailymed_result,

            indian_resolution=
                indian_resolution,
        )
    )

    # STEP 6: BUILD RAW RESULT LIST
    results = []

    if (
        indian_resolution
        and indian_resolution.get(
            "resolved"
        )
    ):

        results.append(
            {
                "source":
                    "indian_medicine",

                "result_type":
                    "indian_brand_resolution",

                "query":
                    query,

                "resolution":
                    indian_resolution,
            }
        )

    if openfda_result:

        results.append(
            openfda_result
        )

    if dailymed_result:

        results.append(
            dailymed_result
        )

    successful_sources = list(
        dict.fromkeys(
            successful_sources
        )
    )

    failed_sources = [
        source
        for source
        in dict.fromkeys(
            failed_sources
        )
        if source
        not in successful_sources
    ]

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

            "indian_medicine_resolution":
                indian_resolution,

            "resolution_metadata": {
                "resolution_path":
                    resolution_path,

                "original_query":
                    query,

                "resolved_openfda_query":
                    resolved_openfda_query,

                "fallback_attempts":
                    fallback_attempts,
            },
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


# ============================================================
# COMBINATION MEDICINE INGREDIENT LABEL ENRICHMENT
# ============================================================

async def _fetch_official_label_for_ingredient(
    ingredient: str,
) -> Dict[str, Any]:
    """
    Fetch openFDA and DailyMed information independently
    for one resolved active ingredient.
    """

    ingredient = str(ingredient or "").strip()

    output = {
        "ingredient": ingredient,
        "openfda": None,
        "dailymed": None,
        "medicine": None,
        "successful_sources": [],
        "failed_sources": [],
        "source_errors": {},
    }

    if not ingredient:
        return output

    openfda_response = await handle_openfda_drug(
        ingredient
    )

    if (
        openfda_response.get("success")
        and openfda_response.get("result")
    ):

        candidate = openfda_response["result"]

        if _ingredients_overlap(
            [ingredient],
            candidate,
        ):

            output["openfda"] = candidate

            output[
                "successful_sources"
            ].append(
                "openfda"
            )

        else:

            output[
                "failed_sources"
            ].append(
                "openfda"
            )

            output[
                "source_errors"
            ][
                "openfda"
            ] = (
                "Returned openFDA result did not "
                "sufficiently match the ingredient."
            )

    else:

        output[
            "failed_sources"
        ].append(
            "openfda"
        )

        output[
            "source_errors"
        ][
            "openfda"
        ] = (
            openfda_response.get(
                "error"
            )
            or
            "No matching openFDA label found."
        )

    if output["openfda"]:

        result = output[
            "openfda"
        ]

        dailymed_response = (
            await handle_dailymed(
                query=ingredient,

                brand_names=(
                    result.get(
                        "brand_names"
                    )
                    or []
                ),

                generic_name=(
                    result.get(
                        "generic_name"
                    )
                ),

                active_ingredients=(
                    result.get(
                        "active_ingredients"
                    )
                    or []
                ),
            )
        )

    else:

        dailymed_response = (
            await handle_dailymed(
                query=ingredient,

                brand_names=[],

                generic_name=
                    ingredient,

                active_ingredients=[
                    {
                        "name":
                            ingredient,

                        "strength":
                            None,
                    }
                ],
            )
        )

    if (
        dailymed_response.get(
            "success"
        )
        and dailymed_response.get(
            "result"
        )
    ):

        dailymed_candidate = (
            dailymed_response[
                "result"
            ]
        )

        dailymed_identity = (
            dailymed_candidate.get(
                "label_title"
            )
            or dailymed_candidate.get(
                "medicine_name"
            )
            or ""
        )

        normalized_ingredient = (
            _normalize_identity(
                ingredient
            )
        )

        normalized_dailymed_identity = (
            _normalize_identity(
                dailymed_identity
            )
        )

        if (
            normalized_ingredient
            and normalized_dailymed_identity
            and (
                normalized_ingredient
                in normalized_dailymed_identity
                or normalized_dailymed_identity
                in normalized_ingredient
            )
        ):

            output[
                "dailymed"
            ] = dailymed_candidate

            output[
                "successful_sources"
            ].append(
                "dailymed"
            )

        else:

            output[
                "failed_sources"
            ].append(
                "dailymed"
            )

            output[
                "source_errors"
            ][
                "dailymed"
            ] = (
                "Returned DailyMed result did not "
                "sufficiently match the ingredient."
            )

    else:

        output[
            "failed_sources"
        ].append(
            "dailymed"
        )

        output[
            "source_errors"
        ][
            "dailymed"
        ] = (
            dailymed_response.get(
                "error"
            )
            or
            "No matching DailyMed label found."
        )

    if (
        output["openfda"]
        or output["dailymed"]
    ):

        output[
            "medicine"
        ] = (
            _build_medicine_payload(
                query=ingredient,

                openfda_result=
                    output["openfda"],

                dailymed_result=
                    output["dailymed"],

                indian_resolution=
                    None,
            )
        )

    output[
        "successful_sources"
    ] = list(
        dict.fromkeys(
            output[
                "successful_sources"
            ]
        )
    )

    output[
        "failed_sources"
    ] = [
        source

        for source
        in dict.fromkeys(
            output[
                "failed_sources"
            ]
        )

        if source
        not in output[
            "successful_sources"
        ]
    ]

    return output


# ============================================================
# PUBLIC MEDICINE HANDLER
# ============================================================

async def handle_medicine_query(
    query: str,
) -> Dict[str, Any]:
    """
    Run the medicine pipeline and pass final payload through format_medicine_payload().
    All retrieval, resolution, and combination logic is preserved completely.
    """

    response = await _handle_medicine_query_single_label(
        query
    )

    payload = response.get("payload") or {}

    resolution = payload.get(
        "indian_medicine_resolution"
    )

    ingredient_labels = []
    unique_ingredients = []

    if (
        resolution
        and resolution.get("resolved")
    ):

        seen = set()

        for ingredient in (
            resolution.get("ingredients")
            or []
        ):

            value = str(
                ingredient or ""
            ).strip()

            normalized = _normalize_identity(
                value
            )

            if (
                not normalized
                or normalized in seen
            ):
                continue

            seen.add(normalized)

            unique_ingredients.append(
                value
            )

        if len(unique_ingredients) > 1:

            for ingredient in unique_ingredients:

                ingredient_label = (
                    await
                    _fetch_official_label_for_ingredient(
                        ingredient
                    )
                )

                ingredient_labels.append(
                    ingredient_label
                )

    payload["ingredient_labels"] = (
        ingredient_labels
    )

    medicine = payload.get(
        "medicine"
    )

    if isinstance(
        medicine,
        dict,
    ):

        medicine[
            "ingredient_labels"
        ] = ingredient_labels

        if ingredient_labels:

            medicine[
                "combination_label_notice"
            ] = (
                "This medicine contains multiple active "
                "ingredients. Official label information "
                "is resolved separately for each ingredient. "
                "Information from one ingredient must not be "
                "interpreted as the official label for the "
                "complete combination product."
            )

        else:

            medicine[
                "combination_label_notice"
            ] = None

    is_combination = (
        resolution
        and resolution.get("resolved")
        and len(unique_ingredients) > 1
    )

    if is_combination:

        product = (
            resolution.get("product")
            or {}
        )

        medicine = (
            payload.get("medicine")
            or {}
        )

        medicine["medicine_name"] = (
            product.get("medicine_name")
            or query
        )

        medicine["manufacturer"] = (
            product.get("manufacturer")
        )

        medicine["product_type"] = (
            product.get("type")
        )

        active_ingredients = []

        raw_active_ingredients = (
            product.get(
                "active_ingredients"
            )
        )

        parsed_active_ingredients = []

        if isinstance(
            raw_active_ingredients,
            list,
        ):

            parsed_active_ingredients = (
                raw_active_ingredients
            )

        elif isinstance(
            raw_active_ingredients,
            str,
        ):

            try:

                parsed = ast.literal_eval(
                    raw_active_ingredients
                )

                if isinstance(
                    parsed,
                    list,
                ):

                    parsed_active_ingredients = (
                        parsed
                    )

            except (
                ValueError,
                SyntaxError,
                TypeError,
            ):

                parsed_active_ingredients = []

        for item in (
            parsed_active_ingredients
        ):

            if not isinstance(
                item,
                dict,
            ):
                continue

            name = str(
                item.get("name")
                or ""
            ).strip()

            strength = str(
                item.get("strength")
                or ""
            ).strip()

            if not name:
                continue

            active_ingredients.append(
                {
                    "name": name,

                    "strength": (
                        strength
                        if strength
                        else None
                    ),
                }
            )

        if not active_ingredients:

            active_ingredients = [

                {
                    "name": ingredient,
                    "strength": None,
                }

                for ingredient
                in unique_ingredients
            ]

        medicine[
            "active_ingredients"
        ] = active_ingredients

        medicine["generic_name"] = None
        medicine["brand_names"] = []
        medicine["uses"] = []

        medicine["dosage"] = {
            "label_instructions": None,
            "amount_per_dose": None,
            "dose_interval": None,
            "maximum_dose": None,
        }

        medicine["side_effects"] = []
        medicine["warnings"] = None
        medicine["precautions"] = None
        medicine["route"] = []

        medicine["official_label"] = {
            "source": None,
            "url": None,
            "dailymed_set_id": None,
        }

        medicine[
            "combination_label_notice"
        ] = (
            "This is a combination medicine containing "
            "multiple active ingredients. Official clinical "
            "information is provided separately for each "
            "ingredient below. No single ingredient label "
            "should be interpreted as the official label "
            "for the complete combination product."
        )

        payload["medicine"] = medicine

        payload["openfda"] = None
        payload["dailymed"] = None

        source_results = response.get(
            "source_results"
        )

        if isinstance(
            source_results,
            dict,
        ):
            source_results.pop(
                "openfda",
                None,
            )

            source_results.pop(
                "dailymed",
                None,
            )

    if ingredient_labels:

        response.setdefault(
            "source_results",
            {},
        )[
            "ingredient_labels"
        ] = ingredient_labels

    if is_combination:

        existing_results = (
            response.get("results")
            or []
        )

        cleaned_results = []

        for result in existing_results:

            source = result.get(
                "source"
            )

            if source in {
                "openfda",
                "dailymed",
            }:
                continue

            cleaned_results.append(
                result
            )

        response["results"] = (
            cleaned_results
        )

    results = response.setdefault(
        "results",
        [],
    )

    for label in ingredient_labels:

        if (
            not label.get("openfda")
            and
            not label.get("dailymed")
        ):
            continue

        results.append(
            {
                "source":
                    "ingredient_official_labels",

                "result_type":
                    "ingredient_label_bundle",

                "ingredient":
                    label.get("ingredient"),

                "openfda":
                    label.get("openfda"),

                "dailymed":
                    label.get("dailymed"),

                "medicine":
                    label.get("medicine"),
            }
        )

    if is_combination:

        successful_sources = [
            source
            for source in (
                response.get(
                    "successful_sources"
                )
                or []
            )
            if source not in {
                "openfda",
                "dailymed",
            }
        ]

        if ingredient_labels:

            successful_sources.append(
                "ingredient_official_labels"
            )

        response[
            "successful_sources"
        ] = list(
            dict.fromkeys(
                successful_sources
            )
        )

        response[
            "failed_sources"
        ] = [

            source

            for source in (
                response.get(
                    "failed_sources"
                )
                or []
            )

            if source not in {
                "openfda",
                "dailymed",
            }
        ]

    response["total_results"] = len(
        results
    )

    metadata = payload.setdefault(
        "resolution_metadata",
        {},
    )

    metadata[
        "ingredient_label_resolution"
    ] = {

        "attempted":
            bool(
                ingredient_labels
            ),

        "ingredient_count":
            len(
                ingredient_labels
            ),

        "ingredients": [

            item.get(
                "ingredient"
            )

            for item
            in ingredient_labels
        ],

        "successful": [

            item.get(
                "ingredient"
            )

            for item
            in ingredient_labels

            if (
                item.get("openfda")
                or
                item.get("dailymed")
            )
        ],
    }

    if is_combination:

        metadata[
            "resolution_path"
        ] = (
            "indian_combination_brand_to_ingredient_labels"
        )

        metadata[
            "resolved_openfda_query"
        ] = None

    # FORMAT PAYLOAD BEFORE RETURNING
    formatted_payload = format_medicine_payload(payload)
    payload["formatted_data"] = formatted_payload

    return response