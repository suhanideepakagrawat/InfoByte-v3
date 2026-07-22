"""
openfda_drug.py

Retriever for medicine information from the openFDA Drug Label API.

Returns:
- Brand name
- Generic name
- Manufacturer
- Product type
- Route
- Active ingredients
- Uses / indications
- Dosage and administration
- Adverse reactions / side effects
- Warnings
- Source information
"""

import os
import re
from typing import Any, Dict, List, Optional
from urllib.parse import quote

import httpx


OPENFDA_BASE_URL = "https://api.fda.gov/drug/label.json"
OPENFDA_API_KEY = os.getenv("OPENFDA_API_KEY")

REQUEST_TIMEOUT = 20.0


def _first(value: Any, default: Optional[str] = None) -> Optional[str]:
    """
    Safely return the first item from an openFDA list field.
    """
    if isinstance(value, list) and value:
        return str(value[0]).strip()

    if isinstance(value, str) and value.strip():
        return value.strip()

    return default


def _as_list(value: Any) -> List[str]:
    """
    Convert an openFDA field into a clean list of strings.
    """
    if value is None:
        return []

    if isinstance(value, list):
        return [
            str(item).strip()
            for item in value
            if item is not None and str(item).strip()
        ]

    if isinstance(value, str) and value.strip():
        return [value.strip()]

    return []


def _clean_text(text: Optional[str]) -> Optional[str]:
    """
    Remove excessive whitespace while preserving readable text.
    """
    if not text:
        return None

    text = re.sub(r"\r\n?", "\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()


def _combine_sections(value: Any) -> Optional[str]:
    """
    Combine multi-part label sections into one readable string.
    """
    sections = _as_list(value)

    cleaned_sections = [
        _clean_text(section)
        for section in sections
        if _clean_text(section)
    ]

    if not cleaned_sections:
        return None

    return "\n\n".join(cleaned_sections)


def _normalize_name(name: str) -> str:
    """
    Normalize a medicine name for matching.
    """
    return re.sub(r"[^a-z0-9]+", " ", name.lower()).strip()


def _calculate_match_score(
    result: Dict[str, Any],
    query: str,
) -> int:
    """
    Score an openFDA result so the most relevant product label
    is selected when multiple labels are returned.
    """
    openfda = result.get("openfda") or {}

    normalized_query = _normalize_name(query)

    brand_names = [
        _normalize_name(name)
        for name in _as_list(openfda.get("brand_name"))
    ]

    generic_names = [
        _normalize_name(name)
        for name in _as_list(openfda.get("generic_name"))
    ]

    substance_names = [
        _normalize_name(name)
        for name in _as_list(openfda.get("substance_name"))
    ]

    score = 0

    for name in brand_names:
        if name == normalized_query:
            score += 100
        elif normalized_query in name or name in normalized_query:
            score += 50

    for name in generic_names:
        if name == normalized_query:
            score += 90
        elif normalized_query in name or name in normalized_query:
            score += 40

    for name in substance_names:
        if name == normalized_query:
            score += 80
        elif normalized_query in name or name in normalized_query:
            score += 30

    # Prefer labels containing the fields InfoByte needs.
    if result.get("dosage_and_administration"):
        score += 10

    if result.get("indications_and_usage") or result.get("purpose"):
        score += 10

    if result.get("active_ingredient") or openfda.get("substance_name"):
        score += 10

    if result.get("adverse_reactions") or result.get("warnings"):
        score += 5

    return score


def _extract_active_ingredients(
    result: Dict[str, Any]
) -> List[Dict[str, Optional[str]]]:
    """
    Extract active ingredients.

    openFDA labels are not completely uniform, so this function
    supports both the active_ingredient label section and the
    structured openfda.substance_name field.
    """
    openfda = result.get("openfda") or {}

    ingredient_sections = _as_list(result.get("active_ingredient"))
    substance_names = _as_list(openfda.get("substance_name"))

    ingredients: List[Dict[str, Optional[str]]] = []
    seen = set()

    for section in ingredient_sections:
        cleaned = _clean_text(section)

        if not cleaned:
            continue

        # Common OTC patterns:
        # Acetaminophen 500 mg
        # Acetaminophen 500 mg in each tablet
        pattern = re.compile(
            r"([A-Za-z][A-Za-z0-9\s\-/(),.]+?)"
            r"\s+(\d+(?:\.\d+)?\s*"
            r"(?:mg|mcg|g|mL|ml|%|unit|units|IU)"
            r"(?:\s*/\s*[A-Za-z0-9]+)?)",
            re.IGNORECASE,
        )

        matches = pattern.findall(cleaned)

        if matches:
            for name, strength in matches:
                name = name.strip(" :-\n\t")
                strength = strength.strip()

                key = (
                    name.lower(),
                    strength.lower(),
                )

                if key not in seen:
                    seen.add(key)

                    ingredients.append(
                        {
                            "name": name,
                            "strength": strength,
                        }
                    )

        else:
            key = (cleaned.lower(), None)

            if key not in seen:
                seen.add(key)

                ingredients.append(
                    {
                        "name": cleaned,
                        "strength": None,
                    }
                )

    # Fall back to structured substance names.
    if not ingredients:
        for substance in substance_names:
            key = (substance.lower(), None)

            if key not in seen:
                seen.add(key)

                ingredients.append(
                    {
                        "name": substance,
                        "strength": None,
                    }
                )

    return ingredients


def _extract_uses(result: Dict[str, Any]) -> List[str]:
    """
    Extract factual use/indication sections from the label.
    """
    uses: List[str] = []

    for field in (
        "indications_and_usage",
        "purpose",
    ):
        for section in _as_list(result.get(field)):
            cleaned = _clean_text(section)

            if cleaned and cleaned not in uses:
                uses.append(cleaned)

    return uses

def _extract_side_effects(
    result: Dict[str, Any]
) -> List[str]:
    """
    Extract actual side-effect/adverse-reaction information
    from the official openFDA product label.

    Only the dedicated adverse_reactions field is treated as
    side-effect information.

    Warnings and precautions are intentionally NOT included
    because they are separate medical information and should
    be displayed independently.
    """
    side_effects: List[str] = []

    for section in _as_list(
        result.get("adverse_reactions")
    ):
        cleaned = _clean_text(section)

        if (
            cleaned
            and cleaned not in side_effects
        ):
            side_effects.append(cleaned)

    return side_effects


def _normalize_result(
    result: Dict[str, Any],
    query: str,
) -> Dict[str, Any]:
    """
    Convert a raw openFDA label into InfoByte's medicine format.
    """
    openfda = result.get("openfda") or {}

    brand_names = _as_list(openfda.get("brand_name"))
    generic_names = _as_list(openfda.get("generic_name"))

    medicine_name = (
        _first(brand_names)
        or _first(generic_names)
        or query
    )

    generic_name = _first(generic_names)

    effective_time = result.get("effective_time")

    if effective_time and len(str(effective_time)) == 8:
        effective_time = (
            f"{effective_time[0:4]}-"
            f"{effective_time[4:6]}-"
            f"{effective_time[6:8]}"
        )

    return {
        "source": "openfda",
        "result_type": "medicine_label",

        "medicine_name": medicine_name,
        "brand_names": brand_names,
        "generic_name": generic_name,

        "manufacturer": _first(
            openfda.get("manufacturer_name")
        ),

        "product_type": _first(
            openfda.get("product_type")
        ),

        "route": _as_list(
            openfda.get("route")
        ),

        "active_ingredients": _extract_active_ingredients(
            result
        ),

        "uses": _extract_uses(result),

        "dosage_and_administration": _combine_sections(
            result.get("dosage_and_administration")
        ),

        "side_effects": _extract_side_effects(result),

        "warnings": _combine_sections(
            result.get("warnings")
        ),

        "precautions": _combine_sections(
            result.get("precautions")
        ),

        "warnings_and_cautions": _combine_sections(
            result.get("warnings_and_cautions")
        ),

        "do_not_use": _combine_sections(
            result.get("do_not_use")
        ),

        "ask_doctor": _combine_sections(
            result.get("ask_doctor")
        ),

        "stop_use": _combine_sections(
            result.get("stop_use")
        ),

        "effective_date": effective_time,

        "application_number": _first(
            openfda.get("application_number")
        ),

        "product_ndc": _as_list(
            openfda.get("product_ndc")
        ),

        "source_name": "openFDA Drug Label",
        "source_url": "https://open.fda.gov/apis/drug/label/",
    }


async def _perform_search(
    client: httpx.AsyncClient,
    search_expression: str,
    limit: int = 10,
) -> List[Dict[str, Any]]:
    """
    Execute one openFDA search.
    """
    params = {
        "search": search_expression,
        "limit": limit,
    }

    if OPENFDA_API_KEY:
        params["api_key"] = OPENFDA_API_KEY

    response = await client.get(
        OPENFDA_BASE_URL,
        params=params,
    )

    if response.status_code == 404:
        return []

    response.raise_for_status()

    data = response.json()

    return data.get("results", [])


async def search_openfda_drug(
    query: str,
) -> Optional[Dict[str, Any]]:
    """
    Search openFDA using progressively broader fields.

    Search order:
    1. Brand name
    2. Generic name
    3. Substance name
    4. General text search
    """
    query = query.strip()

    if not query:
        return None

    escaped_query = query.replace('"', '\\"')

    search_attempts = [
        f'openfda.brand_name:"{escaped_query}"',
        f'openfda.generic_name:"{escaped_query}"',
        f'openfda.substance_name:"{escaped_query}"',
        f'"{escaped_query}"',
    ]

    collected_results: List[Dict[str, Any]] = []

    async with httpx.AsyncClient(
        timeout=REQUEST_TIMEOUT
    ) as client:

        for search_expression in search_attempts:
            try:
                results = await _perform_search(
                    client,
                    search_expression,
                )

                if results:
                    collected_results.extend(results)

                    # Exact field matches are usually sufficient.
                    if search_expression.startswith(
                        (
                            "openfda.brand_name",
                            "openfda.generic_name",
                            "openfda.substance_name",
                        )
                    ):
                        break

            except httpx.HTTPStatusError as exc:
                # Continue to the next search strategy for 404.
                if exc.response.status_code == 404:
                    continue

                raise

    if not collected_results:
        return None

    # Remove duplicate labels.
    unique_results = []
    seen_ids = set()

    for result in collected_results:
        result_id = result.get("id")

        if result_id and result_id in seen_ids:
            continue

        if result_id:
            seen_ids.add(result_id)

        unique_results.append(result)

    best_result = max(
        unique_results,
        key=lambda item: _calculate_match_score(
            item,
            query,
        ),
    )

    return _normalize_result(
        best_result,
        query,
    )


async def handle_openfda_drug(
    query: str,
) -> Dict[str, Any]:
    """
    Public retriever wrapper.
    """
    try:
        result = await search_openfda_drug(query)

        if not result:
            return {
                "success": False,
                "source": "openfda",
                "query": query,
                "result": None,
                "error": "No matching drug label found.",
            }

        return {
            "success": True,
            "source": "openfda",
            "query": query,
            "result": result,
            "error": None,
        }

    except Exception as exc:
        return {
            "success": False,
            "source": "openfda",
            "query": query,
            "result": None,
            "error": str(exc),
        }