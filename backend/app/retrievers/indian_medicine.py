from __future__ import annotations

import csv
import re
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional
from difflib import SequenceMatcher


# ============================================================
# PATH CONFIGURATION
# ============================================================

CURRENT_FILE = Path(__file__).resolve()

# app/retrievers/indian_medicine.py
# -> app/db/indian_medicines.csv
CSV_PATH = CURRENT_FILE.parent.parent / "db" / "indian_medicines.csv"


# ============================================================
# POSSIBLE CSV COLUMN NAMES
# ============================================================

NAME_COLUMNS = [
    "medicine_name",
    "medicine name",
    "name",
    "product_name",
    "product name",
    "brand_name",
    "brand name",
]

MANUFACTURER_COLUMNS = [
    "manufacturer",
    "manufacturer_name",
    "manufacturer name",
    "marketer",
    "company",
]

TYPE_COLUMNS = [
    "type",
    "medicine_type",
    "medicine type",
    "dosage_form",
    "dosage form",
    "form",
]

COMPOSITION_COLUMNS = [
    "composition",
    "salt_composition",
    "salt composition",
    "ingredients",
    "ingredient",
]

PRIMARY_INGREDIENT_COLUMNS = [
    "primary_ingredients",
    "primary ingredients",
    "primary_ingredient",
    "primary ingredient",
    "primaryIngredient",
]

ACTIVE_INGREDIENT_COLUMNS = [
    "active_ingredients",
    "active ingredients",
    "active_ingredient",
    "active ingredient",
    "activeIngredient",
    "activeIngredients",
]

PACKAGING_COLUMNS = [
    "packaging",
    "package",
    "pack_size",
    "pack size",
]


# ============================================================
# NORMALIZATION
# ============================================================

def normalize_text(value: Any) -> str:
    """
    Normalize text for medicine-name matching.

    Example:
        "Montair-LC Tablet" -> "montair lc tablet"
    """

    if value is None:
        return ""

    value = str(value).strip().lower()

    # Replace punctuation with spaces.
    value = re.sub(r"[^a-z0-9]+", " ", value)

    # Collapse repeated whitespace.
    value = re.sub(r"\s+", " ", value)

    return value.strip()


def normalize_column_name(value: str) -> str:
    """
    Normalize CSV column names so variations such as:

        Primary Ingredients
        primary_ingredients
        primary-ingredients

    can be treated similarly.
    """

    value = str(value).strip().lower()
    value = re.sub(r"[^a-z0-9]+", "_", value)
    return value.strip("_")


def _get_field(
    row: Dict[str, Any],
    possible_names: List[str],
) -> Optional[str]:
    """
    Retrieve a field from a CSV row using multiple possible column names.
    """

    normalized_row = {
        normalize_column_name(key): value
        for key, value in row.items()
        if key is not None
    }

    for name in possible_names:
        normalized_name = normalize_column_name(name)

        if normalized_name in normalized_row:
            value = normalized_row[normalized_name]

            if value is not None:
                value = str(value).strip()

                if value and value.lower() not in {
                    "nan",
                    "none",
                    "null",
                    "n/a",
                    "na",
                }:
                    return value

    return None


# ============================================================
# DATASET LOADING
# ============================================================

@lru_cache(maxsize=1)
def load_indian_medicine_dataset() -> List[Dict[str, Any]]:
    """
    Load the Indian medicine dataset once and cache it in memory.

    The dataset is not re-read for every request.
    """

    if not CSV_PATH.exists():
        raise FileNotFoundError(
            f"Indian medicine dataset not found at: {CSV_PATH}"
        )

    medicines: List[Dict[str, Any]] = []

    with CSV_PATH.open(
        "r",
        encoding="utf-8-sig",
        errors="replace",
        newline="",
    ) as file:

        reader = csv.DictReader(file)

        if not reader.fieldnames:
            raise RuntimeError(
                "Indian medicine CSV does not contain a valid header row."
            )

        for row_number, row in enumerate(reader, start=2):

            medicine_name = _get_field(row, NAME_COLUMNS)

            if not medicine_name:
                continue

            normalized_name = normalize_text(medicine_name)

            if not normalized_name:
                continue

            medicine = {
                "medicine_name": medicine_name,
                "normalized_name": normalized_name,

                "manufacturer": _get_field(
                    row,
                    MANUFACTURER_COLUMNS,
                ),

                "type": _get_field(
                    row,
                    TYPE_COLUMNS,
                ),

                "composition": _get_field(
                    row,
                    COMPOSITION_COLUMNS,
                ),

                "primary_ingredients": _get_field(
                    row,
                    PRIMARY_INGREDIENT_COLUMNS,
                ),

                "active_ingredients": _get_field(
                    row,
                    ACTIVE_INGREDIENT_COLUMNS,
                ),

                "packaging": _get_field(
                    row,
                    PACKAGING_COLUMNS,
                ),

                "_row_number": row_number,
            }

            medicines.append(medicine)

    print(
        f"[INDIAN MEDICINE] Loaded "
        f"{len(medicines)} medicine records from {CSV_PATH}"
    )

    return medicines


# ============================================================
# EXACT LOOKUP INDEX
# ============================================================

@lru_cache(maxsize=1)
def build_exact_name_index() -> Dict[str, List[Dict[str, Any]]]:
    """
    Build an exact lookup dictionary.

    Example:

        {
            "montair lc": [
                {...}
            ]
        }

    Multiple records are retained because the same brand may have
    different strengths or dosage forms.
    """

    medicines = load_indian_medicine_dataset()

    index: Dict[str, List[Dict[str, Any]]] = {}

    for medicine in medicines:

        normalized_name = medicine["normalized_name"]

        index.setdefault(
            normalized_name,
            [],
        ).append(medicine)

    return index


# ============================================================
# MATCH SCORING
# ============================================================

def calculate_match_score(
    query: str,
    medicine_name: str,
) -> float:
    """
    Calculate a simple medicine-name similarity score.

    Returns:
        float between 0 and 1.
    """

    normalized_query = normalize_text(query)
    normalized_name = normalize_text(medicine_name)

    if not normalized_query or not normalized_name:
        return 0.0

    # Perfect match.
    if normalized_query == normalized_name:
        return 1.0

    query_tokens = set(normalized_query.split())
    name_tokens = set(normalized_name.split())

    # Query is fully contained in the product name.
    if query_tokens and query_tokens.issubset(name_tokens):

        extra_tokens = len(name_tokens - query_tokens)

        return max(
            0.80,
            0.95 - (extra_tokens * 0.03),
        )

    sequence_score = SequenceMatcher(
        None,
        normalized_query,
        normalized_name,
    ).ratio()

    if query_tokens or name_tokens:

        token_overlap = len(
            query_tokens & name_tokens
        ) / max(
            len(query_tokens | name_tokens),
            1,
        )

    else:
        token_overlap = 0.0

    final_score = (
        sequence_score * 0.70
        +
        token_overlap * 0.30
    )

    return round(final_score, 4)


# ============================================================
# EXACT SEARCH
# ============================================================

def find_exact_indian_medicine(
    query: str,
) -> List[Dict[str, Any]]:
    """
    Find exact Indian medicine-name matches.
    """

    normalized_query = normalize_text(query)

    if not normalized_query:
        return []

    index = build_exact_name_index()

    matches = index.get(
        normalized_query,
        [],
    )

    results = []

    for medicine in matches:

        result = medicine.copy()

        result["match_type"] = "exact"
        result["match_score"] = 1.0

        results.append(result)

    return results


# ============================================================
# FUZZY SEARCH
# ============================================================

def find_fuzzy_indian_medicines(
    query: str,
    limit: int = 5,
    minimum_score: float = 0.72,
) -> List[Dict[str, Any]]:
    """
    Find approximate medicine-name matches.

    This should only be used when exact matching fails.
    """

    normalized_query = normalize_text(query)

    if not normalized_query:
        return []

    medicines = load_indian_medicine_dataset()

    scored_matches = []

    for medicine in medicines:

        score = calculate_match_score(
            normalized_query,
            medicine["normalized_name"],
        )

        if score < minimum_score:
            continue

        result = medicine.copy()

        result["match_type"] = "fuzzy"
        result["match_score"] = score

        scored_matches.append(result)

    scored_matches.sort(
        key=lambda item: item["match_score"],
        reverse=True,
    )

    return scored_matches[:limit]


# ============================================================
# MAIN SEARCH FUNCTION
# ============================================================

def search_indian_medicine(
    query: str,
    limit: int = 5,
    allow_fuzzy: bool = True,
) -> Dict[str, Any]:
    """
    Main public function used by the medicine resolver.

    Search priority:

        1. Exact medicine-name match
        2. Fuzzy medicine-name match
        3. No result

    The function does NOT call OpenFDA or DailyMed.
    It only resolves the Indian product.
    """

    query = str(query or "").strip()

    if not query:

        return {
            "found": False,
            "query": query,
            "match_type": "none",
            "best_match": None,
            "matches": [],
        }

    # --------------------------------------------------------
    # Exact search
    # --------------------------------------------------------

    exact_matches = find_exact_indian_medicine(
        query
    )

    if exact_matches:

        return {
            "found": True,
            "query": query,
            "match_type": "exact",
            "best_match": exact_matches[0],
            "matches": exact_matches[:limit],
        }

    # --------------------------------------------------------
    # Fuzzy search
    # --------------------------------------------------------

    if allow_fuzzy:

        fuzzy_matches = find_fuzzy_indian_medicines(
            query=query,
            limit=limit,
        )

        if fuzzy_matches:

            return {
                "found": True,
                "query": query,
                "match_type": "fuzzy",
                "best_match": fuzzy_matches[0],
                "matches": fuzzy_matches,
            }

    # --------------------------------------------------------
    # No result
    # --------------------------------------------------------

    return {
        "found": False,
        "query": query,
        "match_type": "none",
        "best_match": None,
        "matches": [],
    }


# ============================================================
# DATASET INFORMATION
# ============================================================

def get_dataset_info() -> Dict[str, Any]:
    """
    Useful for debugging the imported dataset.
    """

    medicines = load_indian_medicine_dataset()

    return {
        "dataset_path": str(CSV_PATH),
        "record_count": len(medicines),
    }