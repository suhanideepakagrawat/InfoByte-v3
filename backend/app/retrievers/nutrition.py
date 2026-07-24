"""
InfoByte Food & Nutrition Retriever
------------------------------------
Orchestrates the Food & Nutrition pipeline.

Pipeline:
Original user query
        |
        v
Nutrition Query Parser
        |
        +---- Food query
        |
        +---- Requested quantity
        |
        v
USDA FoodData Central
        |
        +---- Base nutrients
        |
        +---- USDA-defined portions
        |
        +---- Requested portion nutrients
        |
        v
Structured InfoByte response
"""

from typing import Any, Dict, Optional

import httpx

from app.pipeline.nutrition_parser import parse_nutrition_query
from app.retrievers.usda_food import get_nutrition_data


async def retrieve_nutrition(
    query: str,
    fdc_id: Optional[int] = None,
    requested_grams: Optional[float] = None,
) -> Dict[str, Any]:
    original_query = query.strip()

    if not original_query and not fdc_id:
        return {
            "intent": "food_nutrition",
            "query": original_query,
            "food_query": "",
            "requested_grams": None,
            "payload": {"nutrition": None},
            "source": "usda_fooddata_central",
            "success": False,
            "error": "Food query cannot be empty.",
        }

    parsed_query = parse_nutrition_query(original_query)
    food_query = parsed_query.get("food_query") or original_query
    parsed_grams = parsed_query.get("requested_grams")

    final_grams = requested_grams if requested_grams is not None else parsed_grams

    try:
        nutrition_data = await get_nutrition_data(
            query=food_query,
            requested_grams=final_grams,
            fdc_id=fdc_id,
        )

        if not nutrition_data:
            return {
                "intent": "food_nutrition",
                "query": original_query,
                "food_query": food_query,
                "requested_grams": final_grams,
                "payload": {"nutrition": None},
                "source": "usda_fooddata_central",
                "success": False,
                "error": f"No matching food for '{food_query}' was found in USDA FoodData Central.",
            }

        return {
            "intent": "food_nutrition",
            "query": original_query,
            "food_query": food_query,
            "requested_grams": final_grams,
            "payload": {"nutrition": nutrition_data},
            "source": "usda_fooddata_central",
            "success": True,
        }

    except httpx.TimeoutException:
        return {
            "intent": "food_nutrition",
            "query": original_query,
            "food_query": food_query,
            "requested_grams": final_grams,
            "payload": {"nutrition": None},
            "source": "usda_fooddata_central",
            "success": False,
            "error": "USDA FoodData Central request timed out.",
        }

    except httpx.HTTPStatusError as exc:
        status_code = exc.response.status_code if exc.response is not None else None
        return {
            "intent": "food_nutrition",
            "query": original_query,
            "food_query": food_query,
            "requested_grams": final_grams,
            "payload": {"nutrition": None},
            "source": "usda_fooddata_central",
            "success": False,
            "error": f"USDA FoodData Central returned HTTP status {status_code}.",
        }

    except httpx.RequestError:
        return {
            "intent": "food_nutrition",
            "query": original_query,
            "food_query": food_query,
            "requested_grams": final_grams,
            "payload": {"nutrition": None},
            "source": "usda_fooddata_central",
            "success": False,
            "error": "Could not connect to USDA FoodData Central.",
        }

    except Exception as exc:
        print("[nutrition] Unexpected error:", repr(exc))
        return {
            "intent": "food_nutrition",
            "query": original_query,
            "food_query": food_query,
            "requested_grams": final_grams,
            "payload": {"nutrition": None},
            "source": "usda_fooddata_central",
            "success": False,
            "error": "An unexpected error occurred while retrieving nutrition information.",
        }


async def get_food_nutrition(
    query: str,
    fdc_id: Optional[int] = None,
    requested_grams: Optional[float] = None,
) -> Dict[str, Any]:
    return await retrieve_nutrition(
        query=query,
        fdc_id=fdc_id,
        requested_grams=requested_grams,
    )