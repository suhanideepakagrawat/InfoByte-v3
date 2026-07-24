"""
Nutrition Query Parser
----------------------
Extracts:
1. The actual food name
2. An optional requested quantity in grams

Examples:

"nutritional value of paneer"
    -> food_query = "paneer"
    -> requested_grams = None

"nutritional value of 200g paneer"
    -> food_query = "paneer"
    -> requested_grams = 200

"calories in 250 grams chicken breast"
    -> food_query = "chicken breast"
    -> requested_grams = 250
"""

import re
from typing import Any, Dict, Optional


PREFIX_PATTERNS = [
    # General nutrition
    r"^what\s+is\s+the\s+nutritional\s+value\s+of\s+",
    r"^what\s+are\s+the\s+nutritional\s+values\s+of\s+",
    r"^tell\s+me\s+the\s+nutritional\s+value\s+of\s+",
    r"^show\s+me\s+the\s+nutritional\s+value\s+of\s+",
    r"^nutritional\s+value\s+of\s+",
    r"^nutrition\s+facts\s+for\s+",
    r"^nutrition\s+facts\s+of\s+",
    r"^nutrition\s+information\s+for\s+",
    r"^nutrition\s+information\s+of\s+",
    r"^nutrients\s+in\s+",

    # Calories
    r"^how\s+many\s+calories\s+are\s+there\s+in\s+",
    r"^how\s+many\s+calories\s+are\s+in\s+",
    r"^how\s+many\s+calories\s+in\s+",
    r"^calories\s+in\s+",

    # Protein
    r"^how\s+much\s+protein\s+is\s+there\s+in\s+",
    r"^how\s+much\s+protein\s+is\s+in\s+",
    r"^how\s+much\s+protein\s+in\s+",
    r"^protein\s+content\s+of\s+",
    r"^protein\s+in\s+",

    # Carbohydrates
    r"^how\s+many\s+carbs\s+are\s+in\s+",
    r"^how\s+much\s+carbohydrate\s+is\s+in\s+",
    r"^carbohydrate\s+content\s+of\s+",
    r"^carbohydrates\s+in\s+",
    r"^carbs\s+in\s+",

    # Fat
    r"^how\s+much\s+fat\s+is\s+in\s+",
    r"^fat\s+content\s+of\s+",
    r"^fat\s+in\s+",

    # Fiber
    r"^how\s+much\s+fiber\s+is\s+in\s+",
    r"^fiber\s+content\s+of\s+",
    r"^fiber\s+in\s+",
]


# Matches:
# 200g
# 200 g
# 200 gram
# 200 grams
# 150.5g
GRAM_PATTERN = re.compile(
    r"\b(\d+(?:\.\d+)?)\s*(?:g|gram|grams)\b",
    flags=re.IGNORECASE,
)


def _clean_food_query(query: str) -> str:
    """
    Remove common nutrition-related prefixes.
    """

    if not query:
        return ""

    original_query = query.strip()

    cleaned = re.sub(
        r"\s+",
        " ",
        original_query,
    )

    for pattern in PREFIX_PATTERNS:

        updated = re.sub(
            pattern,
            "",
            cleaned,
            flags=re.IGNORECASE,
        )

        if updated != cleaned:
            cleaned = updated.strip()
            break

    return cleaned


def extract_requested_grams(
    query: str,
) -> Optional[float]:
    """
    Extract a requested gram quantity.

    Examples:

    "200g paneer"
        -> 200

    "250 grams chicken breast"
        -> 250

    "banana"
        -> None
    """

    if not query:
        return None

    match = GRAM_PATTERN.search(query)

    if not match:
        return None

    try:
        amount = float(match.group(1))

        if amount <= 0:
            return None

        return amount

    except (TypeError, ValueError):
        return None


def extract_food_query(query: str) -> str:
    """
    Extract only the food name.

    Quantity expressions are removed before the query
    is sent to USDA.

    Examples:

    "nutritional value of 200g paneer"
        -> "paneer"

    "calories in 250 grams chicken breast"
        -> "chicken breast"

    "paneer"
        -> "paneer"
    """

    if not query:
        return ""

    original_query = query.strip()

    cleaned = _clean_food_query(
        original_query
    )

    # Remove gram quantity.
    cleaned = GRAM_PATTERN.sub(
        "",
        cleaned,
    )

    # Normalize whitespace.
    cleaned = re.sub(
        r"\s+",
        " ",
        cleaned,
    )

    cleaned = cleaned.strip(" ?!.,")

    if not cleaned:
        return original_query

    return cleaned


def parse_nutrition_query(
    query: str,
) -> Dict[str, Any]:
    """
    Parse the complete nutrition query.

    Returns:

    {
        "food_query": "paneer",
        "requested_grams": 250
    }
    """

    return {
        "food_query": extract_food_query(
            query
        ),

        "requested_grams": (
            extract_requested_grams(
                query
            )
        ),
    }