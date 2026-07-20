"""
news.py
Responsible for fetching news headlines from GNews and NewsMesh APIs.
"""

import os
from dotenv import load_dotenv
import requests

from app.pipeline.api_parser import clean_json_response


# ----------------------------------------------------------
# Environment variables
# ----------------------------------------------------------

load_dotenv(
    dotenv_path=os.path.join(
        os.path.dirname(__file__),
        "..",
        "..",
        ".env"
    )
)

GNEWS_API_KEY = os.environ.get("GNEWS_API_KEY")
NEWSMESH_API_KEY = os.environ.get("NEWSMESH_API_KEY")


# ----------------------------------------------------------
# Query preprocessing
# ----------------------------------------------------------

def extract_search_keywords(query: str) -> str:
    """
    Isolates the core search topic by removing common
    conversational and news-related stopwords.
    """

    stopwords = {
        "news",
        "article",
        "articles",
        "about",
        "regarding",
        "in",
        "on",
        "for",
        "latest",
        "recent",
        "show",
        "me",
        "find",
        "tell",
        "what",
        "is",
        "happening",
        "current",
    }

    words = (
        query.lower()
        .replace("?", "")
        .replace(".", "")
        .split()
    )

    clean_keywords = [
        word for word in words
        if word not in stopwords
    ]

    return (
        " ".join(clean_keywords).strip()
        if clean_keywords
        else query.strip()
    )


# ----------------------------------------------------------
# News retrieval
# ----------------------------------------------------------

def handle_news_query(search_query: str) -> dict:

    if not GNEWS_API_KEY and not NEWSMESH_API_KEY:
        return {
            "status": "error",
            "display_payload": {
                "title": "Error: No News API keys configured"
            }
        }

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/91.0.4472.124 Safari/537.36"
        )
    }

    refined_keywords = extract_search_keywords(search_query)

    combined_text = []
    providers_used = []
    first_url = None

    # ======================================================
    # 1. GNEWS
    # ======================================================

    if GNEWS_API_KEY:
        try:
            params = {
                "q": refined_keywords,
                "token": GNEWS_API_KEY,
                "lang": "en",
                "max": 1,
            }

            resp = requests.get(
                "https://gnews.io/api/v4/search",
                params=params,
                headers=headers,
                timeout=15,
            )

            print(
                f"[DEBUG] GNews request for "
                f"'{refined_keywords}' returned "
                f"status {resp.status_code}",
                flush=True,
            )

            if resp.status_code == 200:

                data = resp.json()
                articles = data.get("articles", [])

                print(
                    f"[DEBUG] GNews returned "
                    f"{len(articles)} article(s)",
                    flush=True,
                )

                if articles:

                    article = articles[0]

                    article_url = article.get("url")
                    article_title = article.get(
                        "title",
                        "No Title"
                    )

                    main_text = clean_json_response(
                        article,
                        [
                            "title",
                            "description",
                            "content",
                        ],
                    )

                    combined_text.append(
                        f"### 📰 GNews Top Story: "
                        f"{article_title}\n"
                        f"{main_text}\n\n"
                        f"[Read GNews Source]"
                        f"({article_url})"
                    )

                    providers_used.append("GNews")

                    if not first_url:
                        first_url = article_url

            else:
                print(
                    f"[DEBUG] GNews API error "
                    f"{resp.status_code}: "
                    f"{resp.text[:500]}",
                    flush=True,
                )

        except Exception as e:

            print(
                f"[DEBUG] GNews failed for "
                f"'{refined_keywords}': "
                f"{type(e).__name__}: {e}",
                flush=True,
            )

    # ======================================================
    # 2. NEWSMESH
    # ======================================================

    if NEWSMESH_API_KEY:
        try:
            params = {
                "query": refined_keywords,
                "apiKey": NEWSMESH_API_KEY,
                "language": "en",
                "limit": 1,
            }

            resp = requests.get(
                "https://api.newsmesh.co/v1/search",
                params=params,
                headers=headers,
                timeout=15,
            )

            print(
                f"[DEBUG] NewsMesh request for "
                f"'{refined_keywords}' returned "
                f"status {resp.status_code}",
                flush=True,
            )

            if resp.status_code == 200:

                data = resp.json()

                articles = (
                    data.get("data", [])
                    or data.get("articles", [])
                )

                print(
                    f"[DEBUG] NewsMesh returned "
                    f"{len(articles)} article(s)",
                    flush=True,
                )

                if articles:

                    article = articles[0]

                    article_url = (
                        article.get("url")
                        or article.get("link")
                    )

                    article_title = article.get(
                        "title",
                        "No Title"
                    )

                    main_text = clean_json_response(
                        article,
                        [
                            "title",
                            "description",
                            "content",
                        ],
                    )

                    combined_text.append(
                        f"### 📡 NewsMesh Top Story: "
                        f"{article_title}\n"
                        f"{main_text}\n\n"
                        f"[Read NewsMesh Source]"
                        f"({article_url})"
                    )

                    providers_used.append("NewsMesh")

                    if not first_url:
                        first_url = article_url

            else:
                print(
                    f"[DEBUG] NewsMesh API error "
                    f"{resp.status_code}: "
                    f"{resp.text[:500]}",
                    flush=True,
                )

        except Exception as e:

            print(
                f"[DEBUG] NewsMesh failed for "
                f"'{refined_keywords}': "
                f"{type(e).__name__}: {e}",
                flush=True,
            )

    # ======================================================
    # NO RESULTS
    # ======================================================

    if not combined_text:
        return {
            "status": "success",
            "display_payload": {
                "title": (
                    f"No Relevant News Found for "
                    f"'{search_query}'"
                ),
                "main_text": (
                    f"Could not find any recent news "
                    f"articles matching "
                    f"'{refined_keywords}' across "
                    f"available providers."
                ),
            },
        }

    # ======================================================
    # SUCCESS
    # ======================================================

    return {
        "status": "success",
        "display_payload": {
            "title": (
                f"Top Headlines for "
                f"'{search_query}'"
            ),
            "main_text": "\n\n---\n\n".join(
                combined_text
            ),
            "source_url": first_url,
            "metadata": {
                "provider": " & ".join(
                    providers_used
                )
            },
        },
        "system_metrics": {
            "latency_ms": 0
        },
    }
