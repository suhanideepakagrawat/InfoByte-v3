"""
USDA FoodData Central Retriever
--------------------------------
Handles communication with USDA FoodData Central.

Responsibilities:
- Search for foods
- Rank results intelligently
- Prefer generic foods for generic queries
- Fetch complete food details
- Normalize USDA nutrient data
- Extract USDA-defined portions
- Scale nutrient values for arbitrary gram quantities
"""

import os
import re
from typing import Any, Dict, List, Optional

import httpx
from dotenv import load_dotenv


load_dotenv()


USDA_BASE_URL = "https://api.nal.usda.gov/fdc/v1"
USDA_API_KEY = os.getenv("USDA_FDC_API_KEY")

REQUEST_TIMEOUT = 20.0


# ---------------------------------------------------------------------------
# Nutrient definitions
# ---------------------------------------------------------------------------

NUTRIENT_MAP = {
    "Energy": "energy",
    "Protein": "protein",
    "Total lipid (fat)": "total_fat",
    "Carbohydrate, by difference": "carbohydrates",
    "Fiber, total dietary": "fiber",
    "Sugars, total including NLEA": "total_sugars",
    "Total Sugars": "total_sugars",

    "Fatty acids, total saturated": "saturated_fat",
    "Fatty acids, total monounsaturated": "monounsaturated_fat",
    "Fatty acids, total polyunsaturated": "polyunsaturated_fat",
    "Cholesterol": "cholesterol",

    "Calcium, Ca": "calcium",
    "Iron, Fe": "iron",
    "Magnesium, Mg": "magnesium",
    "Phosphorus, P": "phosphorus",
    "Potassium, K": "potassium",
    "Sodium, Na": "sodium",
    "Zinc, Zn": "zinc",

    "Vitamin A, RAE": "vitamin_a",
    "Vitamin C, total ascorbic acid": "vitamin_c",
    "Vitamin D (D2 + D3)": "vitamin_d",
    "Vitamin B-12": "vitamin_b12",
    "Folate, total": "folate",
}


# ---------------------------------------------------------------------------
# Ranking configuration
# ---------------------------------------------------------------------------

FORM_QUALIFIERS = {
    "dehydrated",
    "dried",
    "powder",
    "powdered",
    "baked",
    "fried",
    "roasted",
    "grilled",
    "cooked",
    "boiled",
    "steamed",
    "frozen",
    "canned",
    "sweetened",
    "unsweetened",
    "breaded",
    "smoked",
    "pickled",
    "juice",
    "syrup",
    "flavored",
    "flavour",
    "flavouring",
}


REFERENCE_QUALIFIERS = {
    "raw",
    "fresh",
}

# Preparation states that should be considered less generic
# when the user does not explicitly request them.
SPECIFIC_PREPARATION_WORDS = {
    "rotisserie",
    "sauteed",
    "stewed",
    "roasted",
    "fried",
    "grilled",
    "baked",
    "boiled",
    "smoked",
    "breaded",
    "seasoned",
    "marinated",
}

# Descriptors that generally identify a plain/reference version
# of a food rather than a prepared dish.
GENERIC_REFERENCE_WORDS = {
    "raw",
    "fresh",
    "boneless",
    "skinless",
    "plain",
    "unprepared",
}


# Words that often indicate the USDA result is a prepared
# multi-ingredient dish rather than the food itself.
PREPARED_DISH_WORDS = {
    "dish",
    "curry",
    "soup",
    "stew",
    "sandwich",
    "salad",
    "pizza",
    "burger",
    "casserole",
    "pie",
    "cake",
    "pudding",
    "sauce",
    "gravy",
    "mixed",
    "mixture",
    "palak",
    "saag",
    "masala",
    "tikka",
    "korma",
}


# Words that identify a generic base-food category.
GENERIC_FOOD_CATEGORY_WORDS = {
    "cheese",
    "milk",
    "fruit",
    "vegetable",
    "meat",
    "fish",
    "poultry",
    "egg",
    "grain",
    "rice",
    "bread",
    "legume",
    "bean",
    "nut",
    "seed",
}


# ---------------------------------------------------------------------------
# API key validation
# ---------------------------------------------------------------------------

def _validate_api_key() -> None:
    if not USDA_API_KEY:
        raise RuntimeError(
            "USDA_FDC_API_KEY environment variable is not configured."
        )


# ---------------------------------------------------------------------------
# Text helpers
# ---------------------------------------------------------------------------

def _normalize_query(
    value: str,
) -> str:
    if not value:
        return ""

    value = value.lower().strip()
    value = re.sub(r"[^a-z0-9\s]", " ", value)
    value = re.sub(r"\s+", " ", value)
    return value.strip()


# ---------------------------------------------------------------------------
# Nutrient helpers
# ---------------------------------------------------------------------------

def _extract_nutrient_value(
    nutrient_entry: Dict[str, Any],
) -> Optional[float]:
    value = nutrient_entry.get("value")
    if value is None:
        value = nutrient_entry.get("amount")

    if value is None:
        return None

    try:
        return round(float(value), 4)
    except (TypeError, ValueError):
        return None


def _extract_nutrient_name(
    nutrient_entry: Dict[str, Any],
) -> Optional[str]:
    name = nutrient_entry.get("nutrientName")
    if name:
        return str(name)

    nutrient = nutrient_entry.get("nutrient")
    if isinstance(nutrient, dict):
        return nutrient.get("name")

    return None


def _extract_nutrient_unit(
    nutrient_entry: Dict[str, Any],
) -> Optional[str]:
    unit = nutrient_entry.get("unitName")
    if unit:
        return str(unit)

    nutrient = nutrient_entry.get("nutrient")
    if isinstance(nutrient, dict):
        return nutrient.get("unitName")

    return None


def _normalize_unit(
    unit: Optional[str],
) -> Optional[str]:
    if not unit:
        return None

    unit_map = {
        "G": "g",
        "MG": "mg",
        "UG": "µg",
        "KCAL": "kcal",
        "KJ": "kJ",
    }

    return unit_map.get(unit.upper(), unit)


# ---------------------------------------------------------------------------
# USDA search
# ---------------------------------------------------------------------------

async def search_food(
    query: str,
    page_size: int = 50,
) -> List[Dict[str, Any]]:
    _validate_api_key()

    query = query.strip()
    if not query:
        return []

    url = f"{USDA_BASE_URL}/foods/search"
    params = {
        "api_key": USDA_API_KEY,
        "query": query,
        "pageSize": page_size,
    }

    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
        response = await client.get(url, params=params)
        response.raise_for_status()
        data = response.json()

    return data.get("foods", [])


# ---------------------------------------------------------------------------
# Ranking
# ---------------------------------------------------------------------------

def _calculate_match_score(
    food: Dict[str, Any],
    query: str,
) -> float:
    query_normalized = _normalize_query(query)
    description = _normalize_query(food.get("description", ""))
    additional_descriptions = _normalize_query(
        food.get("additionalDescriptions", "")
    )

    data_type = str(food.get("dataType", "")).lower()

    brand_owner = food.get("brandOwner")
    brand_name = food.get("brandName")

    food_category = food.get("foodCategory")
    if isinstance(food_category, dict):
        food_category = food_category.get("description", "")

    food_category = _normalize_query(str(food_category or ""))

    query_words = set(query_normalized.split())
    description_words = set(description.split())
    category_words = set(food_category.split())

    if not query_words:
        return -10000

    overlap = query_words & description_words
    if not overlap:
        return -1000

    score = 0.0

    # 1. Query coverage
    coverage = len(overlap) / len(query_words)
    score += coverage * 120

    # 2. All requested words present
    if query_words.issubset(description_words):
        score += 60

    # 3. Description precision
    precision = len(overlap) / len(description_words)
    score += precision * 40

    # 4. Exact text match
    if description == query_normalized:
        score += 50
    elif description.startswith(query_normalized + " "):
        score += 25
    elif query_normalized in description:
        score += 15

    # 5. Dataset preference
    if "foundation" in data_type:
        score += 90
    elif "survey" in data_type:
        score += 85
    elif "sr legacy" in data_type:
        score += 75

    # 6. Detect whether brand was explicitly requested
    brand_text = _normalize_query(
        " ".join([str(brand_owner or ""), str(brand_name or "")])
    )

    brand_words = {
        word for word in brand_text.split() if len(word) >= 3
    }

    brand_requested = bool(brand_words & query_words)

    # 7. Branded product handling
    is_branded = (
        "branded" in data_type
        or bool(brand_owner)
        or bool(brand_name)
    )

    if is_branded:
        if brand_requested:
            score += 80
        else:
            score -= 120

    # 8. Preparation qualifiers
    for qualifier in FORM_QUALIFIERS:
        qualifier_in_description = qualifier in description_words
        qualifier_in_query = qualifier in query_words

        if qualifier_in_description and not qualifier_in_query:
            score -= 55
        elif qualifier_in_description and qualifier_in_query:
            score += 35

    # 9. Raw/reference foods
    for qualifier in REFERENCE_QUALIFIERS:
        if qualifier in description_words:
            if qualifier in query_words:
                score += 30
            else:
                score += 15

    unrequested_specific_preparations = (
        description_words.intersection(SPECIFIC_PREPARATION_WORDS) - query_words
    )
    score -= len(unrequested_specific_preparations) * 35

    query_requests_specific_preparation = bool(
        query_words & SPECIFIC_PREPARATION_WORDS
    )

    if not query_requests_specific_preparation:
        reference_descriptors = description_words & GENERIC_REFERENCE_WORDS
        score += len(reference_descriptors) * 10

    # 10. Prepared dish penalty
    unwanted_dish_words = (
        description_words.intersection(PREPARED_DISH_WORDS) - query_words
    )
    score -= len(unwanted_dish_words) * 90

    # 11. Generic single-food query
    if len(query_words) == 1 and query_words.issubset(description_words):
        extra_words = description_words - query_words
        generic_descriptors = {
            "cheese", "fruit", "vegetable", "meat", "poultry", "fish",
            "milk", "egg", "grain", "rice", "bean", "beans", "legume",
            "nut", "nuts", "seed", "seeds", "raw", "fresh",
        }

        if extra_words and extra_words.issubset(generic_descriptors):
            score += 70
        elif not extra_words:
            score += 20
        elif len(extra_words) == 1:
            score += 5
        else:
            score -= min(len(extra_words) * 15, 60)

    # 12. Category relevance
    if query_words & category_words:
        score += 20

    # 13. Additional descriptions
    if query_normalized and query_normalized in additional_descriptions:
        score += 10

    return score


def select_best_food_match(
    foods: List[Dict[str, Any]],
    query: str,
) -> Optional[Dict[str, Any]]:
    if not foods:
        return None

    ranked_foods = sorted(
        foods,
        key=lambda food: (
            _calculate_match_score(food, query),
            1 if "foundation" in str(food.get("dataType", "")).lower() else 0,
            1 if "survey" in str(food.get("dataType", "")).lower() else 0,
        ),
        reverse=True,
    )

    return ranked_foods[0]


def get_top_food_matches(
    foods: List[Dict[str, Any]],
    query: str,
    limit: int = 5,
) -> List[Dict[str, Any]]:
    ranked_foods = sorted(
        foods,
        key=lambda food: (
            _calculate_match_score(food, query),
            1 if "foundation" in str(food.get("dataType", "")).lower() else 0,
            1 if "survey" in str(food.get("dataType", "")).lower() else 0,
        ),
        reverse=True,
    )

    matches = []
    for food in ranked_foods[:limit]:
        matches.append(
            {
                "fdc_id": food.get("fdcId"),
                "description": food.get("description"),
                "data_type": food.get("dataType"),
                "food_category": food.get("foodCategory"),
                "brand_owner": food.get("brandOwner"),
                "match_score": round(_calculate_match_score(food, query), 2),
            }
        )

    return matches


# ---------------------------------------------------------------------------
# Detailed food retrieval
# ---------------------------------------------------------------------------

async def get_food_details(
    fdc_id: int,
) -> Dict[str, Any]:
    _validate_api_key()

    url = f"{USDA_BASE_URL}/food/{fdc_id}"
    params = {
        "api_key": USDA_API_KEY,
    }

    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
        response = await client.get(url, params=params)
        response.raise_for_status()
        return response.json()


# ---------------------------------------------------------------------------
# Nutrient extraction
# ---------------------------------------------------------------------------

def extract_nutrients(
    food_data: Dict[str, Any],
) -> Dict[str, Any]:
    nutrients = {}
    food_nutrients = food_data.get("foodNutrients", [])

    for entry in food_nutrients:
        nutrient_name = _extract_nutrient_name(entry)
        if not nutrient_name:
            continue

        mapped_name = NUTRIENT_MAP.get(nutrient_name)
        if not mapped_name:
            continue

        value = _extract_nutrient_value(entry)
        if value is None:
            continue

        unit = _normalize_unit(_extract_nutrient_unit(entry))

        if mapped_name == "energy":
            if unit == "kcal":
                nutrients["energy_kcal"] = {"value": value, "unit": "kcal"}
            elif unit == "kJ":
                nutrients["energy_kj"] = {"value": value, "unit": "kJ"}
            continue

        nutrients[mapped_name] = {"value": value, "unit": unit}

    return nutrients


# ---------------------------------------------------------------------------
# USDA-defined portions
# ---------------------------------------------------------------------------

def extract_food_portions(
    food_data: Dict[str, Any],
) -> List[Dict[str, Any]]:
    portions = []
    seen = set()

    food_portions = food_data.get("foodPortions")
    if food_portions is None:
        food_portions = food_data.get("foodPortion", [])

    if isinstance(food_portions, dict):
        food_portions = [food_portions]

    for portion in (food_portions or []):
        if not isinstance(portion, dict):
            continue

        gram_weight = portion.get("gramWeight")
        amount = portion.get("amount")
        modifier = portion.get("modifier")
        measure_unit = portion.get("measureUnit")

        unit_name = None
        if isinstance(measure_unit, dict):
            unit_name = measure_unit.get("name") or measure_unit.get("abbreviation")
        else:
            unit_name = portion.get("measureUnitName") or portion.get("measureUnitAbbreviation")

        description = portion.get("portionDescription")

        if not description:
            parts = []
            if amount is not None:
                if isinstance(amount, (int, float)):
                    parts.append(f"{amount:g}")
                else:
                    parts.append(str(amount))

            if unit_name:
                parts.append(str(unit_name))

            if modifier:
                parts.append(str(modifier))

            description = " ".join(parts).strip()

        if not description and gram_weight is not None:
            description = f"{gram_weight} g"

        unique_key = (_normalize_query(description or ""), str(gram_weight))
        if unique_key in seen:
            continue

        seen.add(unique_key)
        portions.append(
            {
                "description": description or "USDA portion",
                "amount": amount,
                "unit": unit_name,
                "modifier": modifier,
                "gram_weight": gram_weight,
            }
        )

    serving_size = food_data.get("servingSize")
    serving_unit = food_data.get("servingSizeUnit")
    household_text = food_data.get("householdServingFullText")

    if serving_size is not None:
        gram_weight = None
        normalized_unit = _normalize_query(serving_unit or "")

        if normalized_unit in {"g", "gram", "grams"}:
            try:
                gram_weight = float(serving_size)
            except (TypeError, ValueError):
                gram_weight = None

        if household_text:
            description = household_text
        else:
            description = f"{serving_size} {serving_unit or ''}".strip()

        unique_key = (_normalize_query(description), str(gram_weight))
        if unique_key not in seen:
            portions.append(
                {
                    "description": description,
                    "amount": serving_size,
                    "unit": serving_unit,
                    "modifier": None,
                    "gram_weight": gram_weight,
                }
            )

    return portions


# ---------------------------------------------------------------------------
# Nutrient scaling
# ---------------------------------------------------------------------------

def scale_nutrients(
    nutrients: Dict[str, Any],
    grams: float,
) -> Dict[str, Any]:
    """
    Scale USDA per-100-g nutrients to an arbitrary requested gram quantity.
    Formula: requested_value = per_100g_value * grams / 100
    """
    if grams <= 0:
        return {}

    scale_factor = grams / 100.0
    scaled = {}

    for nutrient_name, nutrient_data in nutrients.items():
        value = nutrient_data.get("value")
        unit = nutrient_data.get("unit")

        if value is None:
            continue

        try:
            scaled_value = float(value) * scale_factor
        except (TypeError, ValueError):
            continue

        scaled[nutrient_name] = {
            "value": round(scaled_value, 4),
            "unit": unit,
        }

    return scaled


# ---------------------------------------------------------------------------
# Nutrient basis
# ---------------------------------------------------------------------------

def _get_nutrient_basis(
    food_data: Dict[str, Any],
) -> Dict[str, Any]:
    return {
        "amount": 100,
        "unit": "g",
        "display": "per 100 g",
    }


# ---------------------------------------------------------------------------
# Complete nutrition pipeline
# ---------------------------------------------------------------------------

async def get_nutrition_data(
    query: str,
    requested_grams: Optional[float] = None,
    fdc_id: Optional[int] = None,
) -> Optional[Dict[str, Any]]:
    query = query.strip()
    if not query and not fdc_id:
        return None

    foods = []
    best_match = None

    if query:
        foods = await search_food(query=query, page_size=50)

    if fdc_id is not None:
        target_fdc_id = fdc_id
    else:
        if not foods:
            return None
        best_match = select_best_food_match(foods, query)
        if not best_match:
            return None
        target_fdc_id = best_match.get("fdcId")

    if not target_fdc_id:
        return None

    food_details = await get_food_details(target_fdc_id)
    nutrients = extract_nutrients(food_details)
    usda_portions = extract_food_portions(food_details)

    requested_portion = None
    requested_portion_nutrients = None

    if requested_grams is not None:
        requested_portion = {
            "amount": requested_grams,
            "unit": "g",
            "display": f"{requested_grams:g} g",
        }
        requested_portion_nutrients = scale_nutrients(
            nutrients,
            requested_grams,
        )

    top_matches = get_top_food_matches(foods, query) if foods else []

    food_category = food_details.get("foodCategory")
    if isinstance(food_category, dict):
        food_category = food_category.get("description")

    return {
        "source": "usda_fooddata_central",
        "source_name": "USDA FoodData Central",
        "result_type": "nutrition_information",
        "query": query,
        "food_name": food_details.get("description") or (best_match.get("description") if best_match else ""),
        "fdc_id": target_fdc_id,
        "data_type": food_details.get("dataType") or (best_match.get("dataType") if best_match else ""),
        "food_category": food_category or (best_match.get("foodCategory") if best_match else ""),
        "brand_owner": food_details.get("brandOwner") or (best_match.get("brandOwner") if best_match else ""),
        "serving_size": food_details.get("servingSize"),
        "serving_unit": food_details.get("servingSizeUnit"),
        "nutrient_basis": _get_nutrient_basis(food_details),
        "nutrients": nutrients,
        "usda_defined_portions": usda_portions,
        "requested_portion": requested_portion,
        "requested_portion_nutrients": requested_portion_nutrients,
        "alternative_matches": top_matches,
        "source_url": f"https://fdc.nal.usda.gov/food-details/{target_fdc_id}/nutrients",
    }