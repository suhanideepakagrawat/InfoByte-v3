"""
OpenAlex academic research retriever.
"""

import os

import requests

from app.pipeline.academic_parser import parse_openalex_results


OPENALEX_API_URL = "https://api.openalex.org/works"


def handle_openalex_query(
    query: str,
    max_results: int = 5
) -> dict:

    if not query or not query.strip():

        return {
            "status": "error",
            "source": "openalex",
            "error": "Empty academic research query.",
        }

    api_key = os.getenv("OPENALEX_API_KEY")

    if not api_key:

        return {
            "status": "error",
            "source": "openalex",
            "error": (
                "OPENALEX_API_KEY environment variable "
                "is not configured."
            ),
        }

    max_results = max(1, min(max_results, 10))

    params = {
        "search": query.strip(),
        "per-page": max_results,
        "api_key": api_key,
        "select": (
            "id,"
            "doi,"
            "display_name,"
            "publication_year,"
            "publication_date,"
            "cited_by_count,"
            "authorships,"
            "abstract_inverted_index,"
            "primary_location,"
            "open_access,"
            "topics"
        ),
    }

    try:

        response = requests.get(
            OPENALEX_API_URL,
            params=params,
            timeout=20,
            headers={
                "User-Agent": "InfoByte/1.0 Academic Research Engine"
            },
        )

        response.raise_for_status()

        data = response.json()

        works = data.get("results", [])

        parsed_results = parse_openalex_results(works)

        return {
            "status": "success",
            "source": "openalex",
            "display_payload": {
                "title": "OpenAlex Research Results",
                "main_text": (
                    f"Found {len(parsed_results)} relevant "
                    f"academic works for '{query}'."
                ),
                "results": parsed_results,
            },
            "results": parsed_results,
        }

    except requests.RequestException as exc:

        return {
            "status": "error",
            "source": "openalex",
            "error": f"OpenAlex request failed: {str(exc)}",
        }

    except ValueError as exc:

        return {
            "status": "error",
            "source": "openalex",
            "error": (
                "OpenAlex returned an invalid JSON response: "
                f"{str(exc)}"
            ),
        }

    except Exception as exc:

        return {
            "status": "error",
            "source": "openalex",
            "error": str(exc),
        }