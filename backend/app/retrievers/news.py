"""
news.py
Responsible for fetching news headlines.
"""

import os
import re
from dotenv import load_dotenv
import requests
from playwright.sync_api import sync_playwright
from app.pipeline.api_parser import clean_json_response

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '..', '..', '.env'))

GNEWS_API_KEY = os.environ.get("GNEWS_API_KEY")
NEWSMESH_API_KEY = os.environ.get("NEWSMESH_API_KEY")

# ----------------------------------------------------------
# Article extraction config
# ----------------------------------------------------------

ARTICLE_CONTAINER_SELECTORS = [
    "article",
    "[itemprop='articleBody']",
    ".artText",            
    ".article_content",
    ".article-content",
    ".story-content",
    ".story-element-text",
    "#article-body",
    ".entry-content",
    "div.content--container p",
]

BOILERPLATE_STOP_MARKERS = [
    "catch all the business news",
    "choose your reason below",
    "log out of your current",
    "read your daily newspaper",
    "download the economic times news app",
    "subscribe to",
    "related articles",
    "more from this section",
    "trending news",
]

BOILERPLATE_LINE_PATTERNS = [
    r"^\(catch all",
    r"^download the .* app",
    r"^subscribe to",
    r"^share this article",
    r"^also read:",
    r"^also read\b",
    r"^open source link$",
]


def _is_boilerplate_line(text: str) -> bool:
    lowered = text.strip().lower()
    return any(re.match(pat, lowered) for pat in BOILERPLATE_LINE_PATTERNS)


def _hits_stop_marker(text: str) -> bool:
    lowered = text.strip().lower()
    return any(marker in lowered for marker in BOILERPLATE_STOP_MARKERS)


def _extract_from_container(page) -> str:
    for selector in ARTICLE_CONTAINER_SELECTORS:
        try:
            nodes = page.query_selector_all(f"{selector} p")
            if not nodes:
                nodes = page.query_selector_all(selector)
            texts = [n.inner_text().strip() for n in nodes]
            texts = [t for t in texts if len(t) > 40 and not _is_boilerplate_line(t)]
            if len(texts) >= 2:
                return "\n\n".join(texts)
        except Exception:
            continue
    return ""


def _extract_fallback_all_paragraphs(page) -> str:
    paragraphs = page.query_selector_all("p")
    collected = []
    for p in paragraphs:
        text = p.inner_text().strip()
        if len(text) <= 80:
            continue
        if _hits_stop_marker(text):
            break
        if _is_boilerplate_line(text):
            continue
        collected.append(text)
    return "\n\n".join(collected)


def fetch_full_content(url: str) -> str:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        try:
            page.goto(url, timeout=15000, wait_until="domcontentloaded")
            content = _extract_from_container(page)
            if not content:
                content = _extract_fallback_all_paragraphs(page)
            return content if content else "Full content not available via scraper."
        except Exception as e:
            print(f"[DEBUG] Scraper Error: {e}")
            return None
        finally:
            browser.close()


def extract_search_keywords(query: str) -> str:
    """Isolates core topics and removes conversational/structural stopwords."""
    stopwords = {
        "news", "article", "articles", "about", "regarding", "in", "on", "for", 
        "latest", "recent", "show", "me", "find", "tell", "what", "is", "happening", "current"
    }
    words = query.lower().replace("?", "").replace(".", "").split()
    clean_keywords = [w for w in words if w not in stopwords]
    
    return " ".join(clean_keywords).strip() if clean_keywords else query.strip()


def handle_news_query(search_query: str) -> dict:
    if not GNEWS_API_KEY and not NEWSMESH_API_KEY:
        return {"status": "error", "display_payload": {"title": "Error: No News API keys set in .env"}}

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }

    # Extract clean keywords for search
    refined_keywords = extract_search_keywords(search_query)

    combined_text = []
    providers_used = []
    first_url = None 
    
    # 1. Fetch from GNews
    if GNEWS_API_KEY:
        try:
            params = {
                "q": refined_keywords, 
                "token": GNEWS_API_KEY, 
                "lang": "en",
                "max": 1  
            }
            resp = requests.get("https://gnews.io/api/v4/search", params=params, headers=headers, timeout=15)
            if resp.status_code == 200:
                data = resp.json()
                articles = data.get("articles", [])
                
                if articles:
                    article = articles[0]
                    main_text = clean_json_response(article, ["title", "description", "content"])
                    article_url = article.get("url")
                    
                    if "…" in main_text or "..." in main_text:
                        full_content = fetch_full_content(article_url)
                        if full_content:
                            main_text = full_content

                    combined_text.append(f"### 📰 GNews Top Story: {article.get('title', 'No Title')}\n{main_text}\n\n[Read GNews Source]({article_url})")
                    providers_used.append("GNews")
                    
                    if not first_url:
                        first_url = article_url
        except Exception as e:
            print(f"[DEBUG] GNews failed for '{refined_keywords}': {e}")

    # 2. Fetch from NewsMesh
    if NEWSMESH_API_KEY:
        try:
            params = {
                "query": refined_keywords, 
                "apiKey": NEWSMESH_API_KEY, 
                "language": "en",
                "limit": 1  
            }
            resp = requests.get("https://api.newsmesh.co/v1/search", params=params, headers=headers, timeout=15) 
            if resp.status_code == 200:
                data = resp.json()
                articles = data.get("data", []) or data.get("articles", [])
                
                if articles:
                    article = articles[0]
                    article_url = article.get("url") or article.get("link")
                    article_title = article.get("title", "No Title")
                    
                    main_text = clean_json_response(article, ["title", "description", "content"])
                    
                    if "…" in main_text or "..." in main_text:
                        full_content = fetch_full_content(article_url)
                        if full_content:
                            main_text = full_content

                    combined_text.append(f"### 📡 NewsMesh Top Story: {article_title}\n{main_text}\n\n[Read NewsMesh Source]({article_url})")
                    providers_used.append("NewsMesh")
                    
                    if not first_url:
                        first_url = article_url
        except Exception as e:
            print(f"[DEBUG] NewsMesh failed for '{refined_keywords}': {e}")

    if not combined_text:
        return {
            "status": "success", 
            "display_payload": {
                "title": f"No Relevant News Found for '{search_query}'", 
                "main_text": f"Could not find any recent news articles matching '{refined_keywords}' across available providers."
            }
        }

    return {
        "status": "success",
        "display_payload": {
            # UPDATED: Using the original search_query here instead of refined_keywords
            "title": f"Top Headlines for '{search_query}'",
            "main_text": "\n\n---\n\n".join(combined_text),
            "source_url": first_url,
            "metadata": {"provider": f"{' & '.join(providers_used)} + Playwright Scraper"}
        },
        "system_metrics": {"latency_ms": 0} 
    }