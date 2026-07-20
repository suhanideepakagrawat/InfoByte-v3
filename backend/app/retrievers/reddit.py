import os
import requests


SCRAPER_SERVICE_URL = os.environ.get(
    "SCRAPER_SERVICE_URL",
    "http://localhost:10001"
)


def handle_reddit_query(
    search_query: str,
    detected_intent: str
) -> dict:

    try:
        response = requests.post(
            f"{SCRAPER_SERVICE_URL}/scrape/reddit",
            json={
                "query": search_query,
                "intent": detected_intent
            },
            timeout=120
        )

        response.raise_for_status()

        return response.json()

    except requests.exceptions.Timeout:
        return {
            "status": "error",
            "intent": detected_intent,
            "display_payload": {
                "title": "Reddit Retrieval Timeout",
                "main_text": (
                    "The Reddit scraper service took too long "
                    "to respond."
                ),
                "source_url": None,
                "metadata": {}
            }
        }

    except Exception as e:
        return {
            "status": "error",
            "intent": detected_intent,
            "display_payload": {
                "title": "Reddit Retrieval Error",
                "main_text": (
                    "The Reddit scraper service is currently "
                    "unavailable."
                ),
                "source_url": None,
                "metadata": {
                    "error_details": str(e)
                }
            }
        }