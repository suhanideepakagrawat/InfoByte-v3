"""
backend/app/retrievers/reddit.py
Fully synchronous implementation adapted from tested service/scraper files.
"""
import os
import time
import re
import requests
import urllib.parse # FIX: Added for URL encoding
from urllib.parse import urlparse, urlunparse
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
from app.pipeline.reddit_parser import format_reddit_threads

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

SERPAPI_KEY = os.environ.get("SERPAPI_KEY")

def _to_old_reddit(url: str) -> str:
    parsed = urlparse(url)
    if "reddit.com" not in parsed.netloc:
        return url
    new_netloc = "old.reddit.com"
    rewritten = parsed._replace(netloc=new_netloc)
    return urlunparse(rewritten)

def _clean_text(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r"\s+", " ", text)
    return text.strip()

def search_reddit(search_query: str) -> list:
    """Search Google for Reddit discussions via SerpAPI."""
    if not SERPAPI_KEY:
        print("[Reddit Retriever] Warning: SERPAPI_KEY not found.")
        return []

    # FIX: Safely encode the query so '&' and other symbols don't break the HTTP request
    safe_query = urllib.parse.quote_plus(search_query)
    google_query = f"site:reddit.com+{safe_query}"
    
    url = f"https://serpapi.com/search?engine=google&q={google_query}&api_key={SERPAPI_KEY}&num=5"

    try:
        response = requests.get(url, timeout=20) 
        response.raise_for_status()
        data = response.json()
    except Exception as e:
        print(f"[Reddit Search Failed] {e}")
        return [] 

    urls = []
    for result in data.get("organic_results", []):
        link = result.get("link", "")
        # FIX: Filter out subreddit main pages, we only want actual discussion threads
        if "reddit.com" in link.lower() and "/comments/" in link.lower() and link not in urls:
            urls.append(link)
            if len(urls) >= 5:
                break
    return urls

def scrape_reddit_post(page, url: str, max_comments: int = 10, timeout_ms: int = 20000) -> dict:
    old_url = _to_old_reddit(url)
    result = {"url": url, "title": "", "body": "", "comments": [], "error": None}

    try:
        page.goto(old_url, timeout=timeout_ms, wait_until="domcontentloaded")
        try:
            over18_button = page.locator("text=yes").first
            if over18_button.is_visible(timeout=1000):
                over18_button.click()
                page.wait_for_load_state("domcontentloaded", timeout=timeout_ms)
        except PlaywrightTimeoutError:
            pass

        try:
            page.wait_for_selector("#siteTable", timeout=timeout_ms)
        except PlaywrightTimeoutError:
            try:
                page.goto(old_url, timeout=timeout_ms, wait_until="load")
                page.wait_for_selector("#siteTable", timeout=timeout_ms)
            except PlaywrightTimeoutError:
                result["error"] = f"#siteTable never appeared for {old_url}"
                return result

        post_container = page.locator("#siteTable .thing").first

        title_el = post_container.locator("a.title").first
        if title_el.count() > 0:
            result["title"] = _clean_text(title_el.inner_text())
        else:
            result["title"] = _clean_text(page.title())

        body_el = post_container.locator("div.usertext-body div.md").first
        if body_el.count() > 0:
            result["body"] = _clean_text(body_el.inner_text())

        comment_blocks = page.locator("div.commentarea > div.sitetable > div.comment").all()
        if not comment_blocks:
            comment_blocks = page.locator("div.commentarea .comment").all()

        for block in comment_blocks[:max_comments]:
            try:
                author_el = block.locator("a.author").first
                text_el = block.locator("div.usertext-body div.md").first

                author = _clean_text(author_el.inner_text()) if author_el.count() > 0 else "[unknown]"
                text = _clean_text(text_el.inner_text()) if text_el.count() > 0 else ""

                if text:
                    result["comments"].append({"author": author, "text": text})
            except Exception:
                continue

    except PlaywrightTimeoutError:
        result["error"] = f"Timeout loading {old_url}"
    except Exception as e:
        result["error"] = str(e)

    return result

def scrape_reddit_posts(urls: list, max_comments: int = 10, delay_seconds: float = 1.0) -> list:
    results = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        try:
            page.goto("https://old.reddit.com/", timeout=15000, wait_until="domcontentloaded")
            time.sleep(1.5)
        except PlaywrightTimeoutError:
            pass

        for i, url in enumerate(urls):
            result = scrape_reddit_post(page, url, max_comments=max_comments)
            results.append(result)
            if i < len(urls) - 1:
                time.sleep(delay_seconds)

        failed_urls = [r["url"] for r in results if r["error"]]
        if failed_urls:
            for url in failed_urls:
                retry_result = scrape_reddit_post(page, url, max_comments=max_comments)
                if not retry_result["error"]:
                    for idx, r in enumerate(results):
                        if r["url"] == url:
                            results[idx] = retry_result
                            break
                time.sleep(delay_seconds)
        browser.close()
    return results

def handle_reddit_query(search_query: str, detected_intent: str) -> dict:
    start_time = time.perf_counter()
    try:
        urls = search_reddit(search_query)
        valid_threads = []
        
        if urls:
            scraped_data = scrape_reddit_posts(urls, max_comments=5)
            for thread in scraped_data:
                if not thread.get("error"):
                    valid_threads.append(thread)
        
        if not valid_threads:
            latency_ms = int((time.perf_counter() - start_time) * 1000)
            return {
                "status": "success",
                "intent": detected_intent,
                "extracted_parameters": {"search_query": search_query},
                "display_payload": {
                    "title": "No Relevant Discussions Found",
                    "main_text": f"Could not find any specific Reddit discussions matching the exact query: '{search_query}'.",
                    "source_url": None,
                    "metadata": {"replies_count": 0}
                },
                "system_metrics": {"latency_ms": latency_ms, "confidence_score": 1.0}
            }

        for thread in valid_threads:
            thread["url"] = thread["url"].replace("old.reddit.com", "www.reddit.com")

        main_text = format_reddit_threads(valid_threads)
        latency_ms = int((time.perf_counter() - start_time) * 1000)

        return {
            "status": "success",
            "intent": detected_intent,
            "extracted_parameters": {"search_query": search_query},
            "display_payload": {
                "title": f"Top {len(valid_threads)} Reddit Discussions",
                "main_text": main_text,
                "source_url": valid_threads[0]["url"] if valid_threads else None,
                "metadata": {
                    "threads_scraped": len(valid_threads),
                    "total_comments_scraped": sum(len(t["comments"]) for t in valid_threads),
                    "threads": valid_threads
                }
            },
            "system_metrics": {"latency_ms": latency_ms, "confidence_score": 1.0}
        }
    except Exception as e:
        latency_ms = int((time.perf_counter() - start_time) * 1000)
        return {
            "status": "error",
            "intent": detected_intent,
            "extracted_parameters": {"search_query": search_query},
            "display_payload": {
                "title": "Reddit Retrieval Error",
                "main_text": "Failed to scrape community discussions.",
                "source_url": None,
                "metadata": {"error_details": str(e)}
            },
            "system_metrics": {"latency_ms": latency_ms, "confidence_score": 0.0}
        }