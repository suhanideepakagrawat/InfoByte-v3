"""
news.py
Responsible for fetching news headlines from GNews and NewsMesh APIs.
"""

import os
import requests
from dotenv import load_dotenv

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

import re
from difflib import SequenceMatcher


# ----------------------------------------------------------
# Query preprocessing
# ----------------------------------------------------------

# Only remove conversational filler.
# Never remove meaningful entity words like
# "article", "section", "constitution", etc.
FILLER_WORDS = {
    "show",
    "find",
    "tell",
    "give",
    "display",
    "fetch",
    "latest",
    "recent",
    "current",
    "please",
    "me",
    "about",
    "regarding",
    "happening",
}


# Known entity expansions
ENTITY_EXPANSIONS = {
    "article 370": "Article 370",
    "section 144": "Section 144",
    "python gil": "Python GIL",
    "ora-00001": "ORA-00001 Oracle",
    "openai": "OpenAI",
    "ipl": "Indian Premier League",
    "article 35a": "Article 35A",
}


def normalize_query(text: str) -> str:
    """
    Normalize punctuation and whitespace while preserving
    semantic keywords.
    """

    text = text.lower()

    text = re.sub(r"[-_/]", " ", text)
    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"\s+", " ", text)

    return text.strip()


def extract_search_keywords(query: str) -> str:
    """
    Removes ONLY conversational filler.
    Never removes entity words.
    """

    normalized = normalize_query(query)

    words = normalized.split()

    cleaned = [
        word
        for word in words
        if word not in FILLER_WORDS
    ]

    if not cleaned:
        return query.strip()

    return " ".join(cleaned)


def expand_news_query(query: str) -> str:
    """
    Expands well-known entities before sending them
    to the news provider.
    """

    normalized = normalize_query(query)

    for entity, expanded in ENTITY_EXPANSIONS.items():
        if entity in normalized:
            return expanded

    return query


def keyword_overlap(query: str, text: str) -> int:
    """
    Counts overlapping keywords.
    """

    q = set(normalize_query(query).split())
    t = set(normalize_query(text).split())

    return len(q & t)


def score_article(query: str, article: dict) -> int:
    """
    Assigns a relevance score.
    """

    title = article.get("title", "")
    description = article.get("description", "")

    title_lower = title.lower()
    desc_lower = description.lower()

    score = 0

    normalized_query = normalize_query(query)

    if normalized_query in normalize_query(title):
        score += 100

    if normalized_query in normalize_query(description):
        score += 60

    overlap_title = keyword_overlap(query, title)

    overlap_desc = keyword_overlap(query, description)

    score += overlap_title * 25
    score += overlap_desc * 15

    return score


def deduplicate_articles(articles):
    """
    Removes duplicate titles and URLs.
    """

    unique = []

    seen_urls = set()
    seen_titles = []

    for article in articles:

        url = article.get("url", "")

        title = article.get("title", "")

        if url in seen_urls:
            continue

        duplicate = False

        for existing in seen_titles:

            similarity = SequenceMatcher(
                None,
                existing.lower(),
                title.lower()
            ).ratio()

            if similarity > 0.90:
                duplicate = True
                break

        if duplicate:
            continue

        seen_urls.add(url)
        seen_titles.append(title)

        unique.append(article)

    return unique

# ----------------------------------------------------------
# News retrieval
# ----------------------------------------------------------

def handle_news_query(search_query: str) -> dict:

    # ------------------------------------------------------
    # Check API keys
    # ------------------------------------------------------

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
    expanded_query = expand_news_query(refined_keywords)

    combined_text = []
    providers_used = []
    first_url = None

    # ======================================================
    # 1. GNEWS - TOP 3 ARTICLES
    # ======================================================

    if GNEWS_API_KEY:
        
        # Build fallback list and remove duplicates while preserving order
        candidate_queries_raw = [
            expanded_query,
            refined_keywords,
            search_query
        ]
        
        candidate_queries = []
        seen_queries = set()
        for q in candidate_queries_raw:
            if q and q not in seen_queries:
                candidate_queries.append(q)
                seen_queries.add(q)
                
        for current_query in candidate_queries:
            try:
                print(f"[DEBUG] Trying GNews query: {current_query}", flush=True)

                params = {
                    "q": current_query,
                    "token": GNEWS_API_KEY,
                    "lang": "en",
                    "max": 10,
                }

                resp = requests.get(
                    "https://gnews.io/api/v4/search",
                    params=params,
                    headers=headers,
                    timeout=60,
                )

                print(
                    f"[DEBUG] GNews request for "
                    f"'{current_query}' returned "
                    f"status {resp.status_code}",
                    flush=True,
                )

                if resp.status_code == 200:

                    data = resp.json()

                    articles = data.get("articles", [])

                    print(
                        f"[DEBUG] Retrieved {len(articles)} articles",
                        flush=True,
                    )

                    if articles:
                        
                        print(f"[DEBUG] Using query: {current_query}", flush=True)

                        # ----------------------------------------
                        # Remove duplicates
                        # ----------------------------------------

                        articles = deduplicate_articles(
                            articles
                        )

                        # ----------------------------------------
                        # Rank locally
                        # ----------------------------------------

                        ranked = sorted(
                            articles,
                            key=lambda article: score_article(
                                refined_keywords,
                                article,
                            ),
                            reverse=True,
                        )

                        ranked = ranked[:3]

                        gnews_results = []

                        for index, article in enumerate(
                            ranked,
                            start=1,
                        ):

                            article_url = article.get("url")

                            article_title = article.get(
                                "title",
                                "No Title",
                            )

                            main_text = clean_json_response(
                                article,
                                [
                                    "description",
                                    "content",
                                ],
                            )

                            relevance = score_article(
                                refined_keywords,
                                article,
                            )

                            print(
                                f"[DEBUG] "
                                f"Rank {index} | "
                                f"Score={relevance} | "
                                f"{article_title}",
                                flush=True,
                            )

                            gnews_results.append(
                                f"### {index}. "
                                f"{article_title}\n\n"
                                f"{main_text}\n\n"
                                f"[Read Full Article]"
                                f"({article_url})"
                            )

                            if (
                                not first_url
                                and article_url
                            ):
                                first_url = article_url

                        combined_text.append(
                            "## 📰 Top 3 GNews Results\n\n"
                            + "\n\n---\n\n".join(
                                gnews_results
                            )
                        )

                        providers_used.append(
                            "GNews"
                        )
                        
                        # Stop trying fallback queries once articles are found
                        break

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
                    f"'{current_query}': "
                    f"{type(e).__name__}: {e}",
                    flush=True,
                )

    # ======================================================
    # 2. NEWSMESH - TOP STORY
    # ======================================================

    if NEWSMESH_API_KEY:
        try:
            params = {
                "q": expanded_query,
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
                f"'{expanded_query}' returned "
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
                            "description",
                            "content",
                        ],
                    )

                    combined_text.append(
                        f"### 📡 NewsMesh Top Story: "
                        f"{article_title}\n\n"
                        f"{main_text}\n\n"
                        f"[Read NewsMesh Source]"
                        f"({article_url})"
                    )

                    providers_used.append("NewsMesh")

                    if not first_url and article_url:
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