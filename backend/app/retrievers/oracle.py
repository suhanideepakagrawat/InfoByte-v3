import os
import requests


SCRAPER_SERVICE_URL = os.environ.get(
    "SCRAPER_SERVICE_URL",
    "http://localhost:10001"
)


def handle_oracle_query(search_query: str) -> dict:

    try:
        response = requests.post(
            f"{SCRAPER_SERVICE_URL}/scrape/oracle",
            json={
                "query": search_query
            },
            timeout=120
        )

        response.raise_for_status()

        return response.json()

    except requests.exceptions.Timeout:
        return {
            "status": "error",
            "intent": "technical_oracle",
            "display_payload": {
                "title": "Oracle Retrieval Timeout",
                "main_text": (
                    "The Oracle scraper service took too long "
                    "to respond."
                ),
                "source_url": None,
                "metadata": {}
            }
        }

    except Exception as e:
        return {
            "status": "error",
            "intent": "technical_oracle",
            "display_payload": {
                "title": "Oracle Retrieval Error",
                "main_text": (
                    "The Oracle scraper service is currently "
                    "unavailable."
                ),
                "source_url": None,
                "metadata": {
                    "error_details": str(e)
                }
            }
        }