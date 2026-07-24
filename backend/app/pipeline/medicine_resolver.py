from __future__ import annotations

import ast
import json
import re
from typing import Any, Dict, List, Optional

from app.retrievers.indian_medicine import (
    search_indian_medicine,
)


# ============================================================
# CONSTANTS
# ============================================================

EMPTY_VALUES = {
    "",
    "nan",
    "none",
    "null",
    "n/a",
    "na",
}


FORM_WORDS = {
    "tablet",
    "tablets",
    "capsule",
    "capsules",
    "syrup",
    "suspension",
    "injection",
    "injectable",
    "cream",
    "ointment",
    "gel",
    "drops",
    "drop",
}


DOSAGE_PATTERN = re.compile(
    r"""
    \b
    \d+(?:\.\d+)?
    \s*
    (?:
        mg
        | mcg
        | μg
        | ug
        | g
        | gm
        | ml
        | iu
        | units?
        | %
    )
    (?:
        \s*/\s*
        \d*(?:\.\d+)?
        \s*
        (?:
            mg
            | mcg
            | μg
            | ug
            | g
            | gm
            | ml
            | iu
            | units?
        )
    )?
    \b
    """,
    re.IGNORECASE | re.VERBOSE,
)


# ============================================================
# GENERAL HELPERS
# ============================================================

def _is_empty_value(
    value: Any,
) -> bool:
    """
    Return True for missing or placeholder values.
    """

    if value is None:
        return True

    if isinstance(
        value,
        str,
    ):
        return (
            value.strip().lower()
            in EMPTY_VALUES
        )

    return False


def _deduplicate_strings(
    values: List[str],
) -> List[str]:
    """
    Remove duplicate ingredient names while preserving order.
    """

    output = []
    seen = set()

    for value in values:

        if not value:
            continue

        cleaned = str(
            value
        ).strip()

        if not cleaned:
            continue

        normalized = re.sub(
            r"\s+",
            " ",
            cleaned.lower(),
        ).strip()

        if normalized in seen:
            continue

        seen.add(
            normalized
        )

        output.append(
            cleaned
        )

    return output


# ============================================================
# INGREDIENT CLEANING
# ============================================================

def clean_ingredient_name(
    ingredient: Any,
) -> str:
    """
    Convert an ingredient value into a clean generic ingredient name.

    Examples:

        "Montelukast 10 mg"
            -> "Montelukast"

        "Levocetirizine Hydrochloride 5 mg"
            -> "Levocetirizine Hydrochloride"

        "Paracetamol (325mg)"
            -> "Paracetamol"

    This function should only receive an individual ingredient,
    not the complete serialized active_ingredients list.
    """

    if _is_empty_value(
        ingredient
    ):
        return ""

    value = str(
        ingredient
    ).strip()

    # --------------------------------------------------------
    # Remove bracketed strength information
    # --------------------------------------------------------

    value = re.sub(
        r"\([^)]*\d+(?:\.\d+)?\s*"
        r"(?:mg|mcg|μg|ug|g|gm|ml|iu|units?|%)"
        r"[^)]*\)",
        " ",
        value,
        flags=re.IGNORECASE,
    )

    # --------------------------------------------------------
    # Remove dosage strengths
    # --------------------------------------------------------

    value = DOSAGE_PATTERN.sub(
        " ",
        value,
    )

    # --------------------------------------------------------
    # Remove common dosage-form words
    # --------------------------------------------------------

    words = []

    for word in value.split():

        cleaned_word = re.sub(
            r"[^a-zA-Z0-9\-]",
            "",
            word,
        )

        if (
            cleaned_word.lower()
            in FORM_WORDS
        ):
            continue

        words.append(
            word
        )

    value = " ".join(
        words
    )

    # --------------------------------------------------------
    # Remove leftover separators and punctuation
    # --------------------------------------------------------

    value = re.sub(
        r"[|]+",
        " ",
        value,
    )

    value = re.sub(
        r"\s+",
        " ",
        value,
    )

    return value.strip(
        " ,;+/-[]{}'\""
    )


# ============================================================
# STRUCTURED ACTIVE INGREDIENT PARSING
# ============================================================

def _parse_serialized_value(
    value: str,
) -> Optional[Any]:
    """
    Safely parse a string containing a Python or JSON structure.

    Example CSV value:

        "[{'name': 'Levocetirizine',
           'strength': '5mg'},
          {'name': 'Montelukast',
           'strength': '10mg'}]"

    ast.literal_eval handles Python-style single quotes.

    json.loads is retained as a fallback for JSON-formatted values.
    """

    if not value:
        return None

    stripped = value.strip()

    if not (
        stripped.startswith("[")
        or stripped.startswith("{")
    ):
        return None

    # --------------------------------------------------------
    # Try Python literal representation
    # --------------------------------------------------------

    try:

        parsed = ast.literal_eval(
            stripped
        )

        if isinstance(
            parsed,
            (list, dict),
        ):
            return parsed

    except (
        ValueError,
        SyntaxError,
        TypeError,
    ):
        pass

    # --------------------------------------------------------
    # Try JSON representation
    # --------------------------------------------------------

    try:

        parsed = json.loads(
            stripped
        )

        if isinstance(
            parsed,
            (list, dict),
        ):
            return parsed

    except (
        json.JSONDecodeError,
        TypeError,
    ):
        pass

    return None


def _extract_names_from_structured_value(
    value: Any,
) -> List[str]:
    """
    Extract ingredient names from structured ingredient data.

    Supported structures:

    1. List of dictionaries:

        [
            {
                "name": "Levocetirizine",
                "strength": "5mg"
            },
            {
                "name": "Montelukast",
                "strength": "10mg"
            }
        ]

    2. Single dictionary:

        {
            "name": "Paracetamol",
            "strength": "500mg"
        }

    3. List of strings:

        [
            "Paracetamol",
            "Caffeine"
        ]
    """

    ingredients = []

    if isinstance(
        value,
        dict,
    ):

        name = (
            value.get("name")
            or value.get("ingredient")
            or value.get(
                "active_ingredient"
            )
            or value.get(
                "activeIngredient"
            )
        )

        if name:

            cleaned = (
                clean_ingredient_name(
                    name
                )
            )

            if cleaned:
                ingredients.append(
                    cleaned
                )

        return ingredients

    if isinstance(
        value,
        list,
    ):

        for item in value:

            if isinstance(
                item,
                dict,
            ):

                name = (
                    item.get("name")
                    or item.get(
                        "ingredient"
                    )
                    or item.get(
                        "active_ingredient"
                    )
                    or item.get(
                        "activeIngredient"
                    )
                )

                if not name:
                    continue

                cleaned = (
                    clean_ingredient_name(
                        name
                    )
                )

                if cleaned:
                    ingredients.append(
                        cleaned
                    )

            elif isinstance(
                item,
                str,
            ):

                cleaned = (
                    clean_ingredient_name(
                        item
                    )
                )

                if cleaned:
                    ingredients.append(
                        cleaned
                    )

    return _deduplicate_strings(
        ingredients
    )


def parse_active_ingredients(
    value: Any,
) -> List[str]:
    """
    Parse active ingredient data from the Indian medicines dataset.

    This specifically fixes CSV values such as:

        "[{'name': 'Aceclofenac',
           'strength': '100mg',
           'full_description':
               'Aceclofenac (100mg)'},
          {'name': 'Paracetamol',
           'strength': '325mg',
           'full_description':
               'Paracetamol (325mg)'}]"

    Result:

        [
            "Aceclofenac",
            "Paracetamol"
        ]

    The function also supports:
    - actual Python lists
    - actual dictionaries
    - JSON strings
    - ordinary composition strings
    """

    if _is_empty_value(
        value
    ):
        return []

    # --------------------------------------------------------
    # Already structured
    # --------------------------------------------------------

    if isinstance(
        value,
        (list, dict),
    ):

        ingredients = (
            _extract_names_from_structured_value(
                value
            )
        )

        if ingredients:
            return ingredients

    # --------------------------------------------------------
    # Serialized list/dictionary
    # --------------------------------------------------------

    if isinstance(
        value,
        str,
    ):

        parsed = (
            _parse_serialized_value(
                value
            )
        )

        if parsed is not None:

            ingredients = (
                _extract_names_from_structured_value(
                    parsed
                )
            )

            if ingredients:
                return ingredients

    # --------------------------------------------------------
    # Final fallback: ordinary composition string
    # --------------------------------------------------------

    return split_composition(
        str(value)
    )


# ============================================================
# COMPOSITION SPLITTING
# ============================================================

def split_composition(
    composition: Optional[str],
) -> List[str]:
    """
    Split ordinary textual compositions into individual ingredients.

    Supported examples:

        Montelukast 10 mg + Levocetirizine 5 mg

        Montelukast (10mg), Levocetirizine (5mg)

        Montelukast | Levocetirizine

        Montelukast; Levocetirizine

    Structured list strings are also detected and redirected through
    the structured parser.
    """

    if _is_empty_value(
        composition
    ):
        return []

    value = str(
        composition
    ).strip()

    if not value:
        return []

    # --------------------------------------------------------
    # Detect serialized structured values first
    # --------------------------------------------------------

    parsed = (
        _parse_serialized_value(
            value
        )
    )

    if parsed is not None:

        ingredients = (
            _extract_names_from_structured_value(
                parsed
            )
        )

        if ingredients:
            return ingredients

    # --------------------------------------------------------
    # Normalize separators
    # --------------------------------------------------------

    value = re.sub(
        r"\s*\+\s*",
        "|||",
        value,
    )

    value = re.sub(
        r"\s*\|\s*",
        "|||",
        value,
    )

    value = re.sub(
        r"\s*;\s*",
        "|||",
        value,
    )

    # Split commas when they appear to introduce another
    # capitalized ingredient name.
    value = re.sub(
        r",\s*(?=[A-Z][A-Za-z])",
        "|||",
        value,
    )

    parts = value.split(
        "|||"
    )

    ingredients = []

    for part in parts:

        cleaned = (
            clean_ingredient_name(
                part
            )
        )

        if cleaned:
            ingredients.append(
                cleaned
            )

    return _deduplicate_strings(
        ingredients
    )


# ============================================================
# INGREDIENT SOURCE SELECTION
# ============================================================

def extract_ingredients_from_product(
    product: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Determine and parse the best ingredient source.

    Priority:

        1. active_ingredients
        2. primary_ingredients
        3. composition

    The important distinction is that active_ingredients may contain
    a serialized list of dictionaries, while the other fields may
    contain ordinary text.
    """

    active_ingredients = (
        product.get(
            "active_ingredients"
        )
    )

    primary_ingredients = (
        product.get(
            "primary_ingredients"
        )
    )

    composition = (
        product.get(
            "composition"
        )
    )

    source_field = None
    source_value = None
    ingredients = []

    # --------------------------------------------------------
    # Active ingredients
    # --------------------------------------------------------

    if not _is_empty_value(
        active_ingredients
    ):

        parsed = (
            parse_active_ingredients(
                active_ingredients
            )
        )

        if parsed:

            source_field = (
                "active_ingredients"
            )

            source_value = (
                active_ingredients
            )

            ingredients = parsed

    # --------------------------------------------------------
    # Primary ingredients fallback
    # --------------------------------------------------------

    if (
        not ingredients
        and not _is_empty_value(
            primary_ingredients
        )
    ):

        parsed = (
            parse_active_ingredients(
                primary_ingredients
            )
        )

        if parsed:

            source_field = (
                "primary_ingredients"
            )

            source_value = (
                primary_ingredients
            )

            ingredients = parsed

    # --------------------------------------------------------
    # Composition fallback
    # --------------------------------------------------------

    if (
        not ingredients
        and not _is_empty_value(
            composition
        )
    ):

        parsed = (
            parse_active_ingredients(
                composition
            )
        )

        if parsed:

            source_field = (
                "composition"
            )

            source_value = (
                composition
            )

            ingredients = parsed

    return {
        "source_field":
            source_field,

        "raw_value":
            source_value,

        "ingredients":
            _deduplicate_strings(
                ingredients
            ),
    }


# ============================================================
# SEARCH TERM GENERATION
# ============================================================

def build_ingredient_search_terms(
    ingredients: List[str],
) -> Dict[str, Any]:
    """
    Build openFDA and DailyMed fallback terms.

    Example:

        [
            "Levocetirizine",
            "Montelukast"
        ]

    becomes:

        {
            "combination":
                "Levocetirizine Montelukast",

            "individual": [
                "Levocetirizine",
                "Montelukast"
            ],

            "ingredient_count": 2,

            "is_combination": True
        }
    """

    cleaned_ingredients = []

    for ingredient in ingredients:

        cleaned = (
            clean_ingredient_name(
                ingredient
            )
        )

        if cleaned:
            cleaned_ingredients.append(
                cleaned
            )

    cleaned_ingredients = (
        _deduplicate_strings(
            cleaned_ingredients
        )
    )

    combination_query = None

    if cleaned_ingredients:

        combination_query = " ".join(
            cleaned_ingredients
        )

    return {
        "combination":
            combination_query,

        "individual":
            cleaned_ingredients,

        "ingredient_count":
            len(
                cleaned_ingredients
            ),

        "is_combination":
            (
                len(
                    cleaned_ingredients
                )
                > 1
            ),
    }


# ============================================================
# RESOLUTION STATUS
# ============================================================

def determine_resolution_status(
    indian_result: Dict[str, Any],
    ingredients: List[str],
) -> str:
    """
    Determine the medicine resolution state.
    """

    if not indian_result.get(
        "found"
    ):
        return "NOT_FOUND"

    match_type = (
        indian_result.get(
            "match_type"
        )
    )

    if not ingredients:

        if match_type == "exact":
            return (
                "INDIAN_BRAND_FOUND_"
                "NO_INGREDIENTS"
            )

        return "AMBIGUOUS_MATCH"

    if match_type == "fuzzy":

        if len(ingredients) > 1:
            return (
                "INDIAN_BRAND_FUZZY_"
                "RESOLVED_COMBINATION"
            )

        return (
            "INDIAN_BRAND_FUZZY_"
            "RESOLVED_SINGLE_INGREDIENT"
        )

    if len(ingredients) == 1:

        return (
            "INDIAN_BRAND_RESOLVED_"
            "SINGLE_INGREDIENT"
        )

    return (
        "INDIAN_BRAND_RESOLVED_"
        "COMBINATION"
    )


# ============================================================
# ALTERNATIVE MATCH FORMATTING
# ============================================================

def _format_alternative_match(
    match: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Format an alternative medicine match and resolve its ingredients.

    This keeps alternative matches useful for future frontend
    interaction without changing the original raw product fields.
    """

    ingredient_result = (
        extract_ingredients_from_product(
            match
        )
    )

    ingredients = (
        ingredient_result.get(
            "ingredients"
        )
        or []
    )

    return {
        "medicine_name":
            match.get(
                "medicine_name"
            ),

        "manufacturer":
            match.get(
                "manufacturer"
            ),

        "type":
            match.get(
                "type"
            ),

        "composition":
            match.get(
                "composition"
            ),

        "primary_ingredients":
            match.get(
                "primary_ingredients"
            ),

        "active_ingredients":
            match.get(
                "active_ingredients"
            ),

        "packaging":
            match.get(
                "packaging"
            ),

        "resolved_ingredients":
            ingredients,

        "search_terms":
            build_ingredient_search_terms(
                ingredients
            ),

        "match_score":
            match.get(
                "match_score"
            ),
    }


# ============================================================
# EMPTY RESPONSE
# ============================================================

def _empty_resolution(
    query: str,
    status: str,
) -> Dict[str, Any]:
    """
    Build a consistent empty resolution response.
    """

    return {
        "resolved":
            False,

        "query":
            query,

        "status":
            status,

        "product":
            None,

        "ingredient_resolution": {
            "source_field":
                None,

            "raw_value":
                None,

            "ingredients":
                [],
        },

        "ingredients":
            [],

        "search_terms": {
            "combination":
                None,

            "individual":
                [],

            "ingredient_count":
                0,

            "is_combination":
                False,
        },

        "alternative_matches":
            [],
    }


# ============================================================
# MAIN RESOLVER
# ============================================================

def resolve_medicine_query(
    query: str,
    allow_fuzzy: bool = True,
) -> Dict[str, Any]:
    """
    Resolve an Indian medicine brand into generic ingredients.

    Flow:

        User query
            |
            v
        Indian medicine dataset
            |
            v
        Best product match
            |
            v
        Parse structured active_ingredients
            |
            v
        Extract individual generic ingredient names
            |
            v
        Build openFDA / DailyMed fallback queries
    """

    query = str(
        query or ""
    ).strip()

    if not query:

        return _empty_resolution(
            query=query,
            status="EMPTY_QUERY",
        )

    # --------------------------------------------------------
    # Search Indian medicine dataset
    # --------------------------------------------------------

    indian_result = (
        search_indian_medicine(
            query=query,
            limit=5,
            allow_fuzzy=allow_fuzzy,
        )
    )

    if not indian_result.get(
        "found"
    ):

        return _empty_resolution(
            query=query,
            status="NOT_FOUND",
        )

    # --------------------------------------------------------
    # Select best product
    # --------------------------------------------------------

    product = (
        indian_result.get(
            "best_match"
        )
    )

    if not product:

        return _empty_resolution(
            query=query,
            status="NOT_FOUND",
        )

    # --------------------------------------------------------
    # Resolve ingredients
    # --------------------------------------------------------

    ingredient_result = (
        extract_ingredients_from_product(
            product
        )
    )

    ingredients = (
        ingredient_result.get(
            "ingredients"
        )
        or []
    )

    # --------------------------------------------------------
    # Build fallback search terms
    # --------------------------------------------------------

    search_terms = (
        build_ingredient_search_terms(
            ingredients
        )
    )

    # --------------------------------------------------------
    # Determine resolution status
    # --------------------------------------------------------

    status = (
        determine_resolution_status(
            indian_result,
            ingredients,
        )
    )

    # --------------------------------------------------------
    # Alternative matches
    # --------------------------------------------------------

    alternative_matches = []

    for match in (
        indian_result.get(
            "matches"
        )
        or []
    )[1:]:

        alternative_matches.append(
            _format_alternative_match(
                match
            )
        )

    # --------------------------------------------------------
    # Final response
    # --------------------------------------------------------

    return {
        "resolved":
            bool(
                ingredients
            ),

        "query":
            query,

        "status":
            status,

        "match_type":
            indian_result.get(
                "match_type"
            ),

        "match_score":
            product.get(
                "match_score"
            ),

        "product": {

            "medicine_name":
                product.get(
                    "medicine_name"
                ),

            "manufacturer":
                product.get(
                    "manufacturer"
                ),

            "type":
                product.get(
                    "type"
                ),

            "composition":
                product.get(
                    "composition"
                ),

            "primary_ingredients":
                product.get(
                    "primary_ingredients"
                ),

            "active_ingredients":
                product.get(
                    "active_ingredients"
                ),

            "packaging":
                product.get(
                    "packaging"
                ),
        },

        "ingredient_resolution": {

            "source_field":
                ingredient_result.get(
                    "source_field"
                ),

            "raw_value":
                ingredient_result.get(
                    "raw_value"
                ),

            "ingredients":
                ingredients,
        },

        "ingredients":
            ingredients,

        "search_terms":
            search_terms,

        "alternative_matches":
            alternative_matches,
    }


# ============================================================
# HELPER FOR MEDICINE.PY
# ============================================================

def get_fallback_medicine_queries(
    query: str,
) -> List[str]:
    """
    Return ordered fallback queries for medicine.py.

    Example:

        Montair LC

    returns:

        [
            "Levocetirizine Montelukast",
            "Levocetirizine",
            "Montelukast"
        ]

    Zerodol SP may return:

        [
            "Aceclofenac Paracetamol",
            "Aceclofenac",
            "Paracetamol"
        ]
    """

    resolution = (
        resolve_medicine_query(
            query
        )
    )

    if not resolution.get(
        "resolved"
    ):
        return []

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

    for ingredient in (
        search_terms.get(
            "individual"
        )
        or []
    ):

        if ingredient not in queries:

            queries.append(
                ingredient
            )

    return queries