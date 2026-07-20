"""
oracle.py

Responsible for looking up ORA codes via SerpAPI, crawling threads/docs 
via Playwright, and returning a standardized InfoByte v3 Data Contract.
"""

import os
import time
import re
import requests
from playwright.sync_api import sync_playwright
from app.pipeline.oracle_parser import (
    clean_scrape_result,
    extract_cause_and_action,
)

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

SERPAPI_KEY = os.environ.get("SERPAPI_KEY")
FORUM_DOMAINS = ["community.oracle.com", "forums.oracle.com"]

REQUEST_TIMEOUT = 30      
MAX_RETRIES = 3
BACKOFF_SECONDS = 3       

def _serpapi_search(query: str) -> list:
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = requests.get(
                "https://serpapi.com/search",
                params={"engine": "google", "q": query, "num": 5, "api_key": SERPAPI_KEY},
                timeout=REQUEST_TIMEOUT,
            )
            resp.raise_for_status()
            data = resp.json()
            if "error" in data:
                raise RuntimeError(f"SerpAPI internal error: {data['error']}")
            return data.get("organic_results", [])
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
            print(f"  [Oracle Retriever - Attempt {attempt}/{MAX_RETRIES}] Network failure: {e!r}")
            if attempt < MAX_RETRIES:
                time.sleep(BACKOFF_SECONDS * (2 ** (attempt - 1)))
        except requests.exceptions.HTTPError as e:
            raise RuntimeError(f"SerpAPI HTTP Fatal Status: {e}") from e
    raise RuntimeError("SerpAPI target retrieval failed completely after exhaustion of retries.")

def find_docs_url(query: str) -> str | None:
    if not SERPAPI_KEY:
        print("  [Debug] SERPAPI_KEY is missing.")
        return None
        
    results = _serpapi_search(f"site:docs.oracle.com {query}")
    
    for result in results:
        link = result.get("link", "")
        if "docs.oracle.com" in link:
            return link
            
    print(f"  [Debug] No docs.oracle.com link found in search results for: {query}")
    return None

def find_forum_url(error_code: str) -> str | None:
    if not SERPAPI_KEY:
        raise RuntimeError("Missing SERPAPI_KEY parameter in environment variables.")
    
    results = _serpapi_search(f"{error_code} oracle forum")
    if not results:
        return None

    # Loop through results and ONLY accept trusted domains
    for result in results:
        link = result.get("link", "")
        if any(domain in link for domain in FORUM_DOMAINS):
            return link
            
    print(f"  [Warning] No trusted Oracle forum domains found for: {error_code}")
    return None

# --- LEVEL 1: Smart Chunking Helper ---
def get_smart_snippet(raw_text: str, max_length: int = 2000) -> str:
    """Extracts text up to max_length without breaking paragraphs."""
    paragraphs = raw_text.split('\n\n')
    snippet = ""
    
    for p in paragraphs:
        if len(snippet) + len(p) > max_length:
            break
        if p.strip():
            snippet += p.strip() + "\n\n"
            
    if not snippet:
        return raw_text[:max_length].rsplit('.', 1)[0] + "."
        
    return snippet.strip()

# --- LEVEL 2: HTML-Aware Scraper ---
def scrape_docs_page(url: str) -> str | None:
    # JavaScript to target only semantic content and format code blocks
    SMART_EXTRACT_JS = """
        () => {
            const container = document.querySelector('main') || document.querySelector('article') || document.querySelector('.book') || document.body;
            if (!container) return "";
            
            // Remove navigational junk
            container.querySelectorAll('nav, header, footer, aside, script, style').forEach(el => el.remove());
            
            let extracted = [];
            // Target specific semantic tags
            container.querySelectorAll('h1, h2, h3, p, pre, li').forEach(el => {
                let text = el.innerText.trim();
                if (text) {
                    if (el.tagName.toLowerCase() === 'pre') {
                        extracted.push("```\\n" + text + "\\n```");
                    } else if (el.tagName.toLowerCase().startsWith('h')) {
                        extracted.push("\\n**" + text + "**");
                    } else {
                        extracted.push(text);
                    }
                }
            });
            // Deduplicate contiguous identical lines (common in nested HTML lists)
            return extracted.filter((item, pos, arr) => pos === 0 || item !== arr[pos-1]).join('\\n\\n');
        }
    """
    
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--disable-gpu",
                "--disable-dev-shm-usage",
                "--disable-extensions",
                "--disable-background-networking",
                "--disable-background-timer-throttling",
                "--disable-renderer-backgrounding",
                "--disable-default-apps",
                "--disable-sync",
                "--mute-audio",
                "--no-first-run",
                "--no-default-browser-check",
            ],
        )
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        )

        def block_heavy_resources(route):
            if route.request.resource_type in {"image", "media", "font"}:
                route.abort()
            else:
                route.continue_()

        context.route("**/*", block_heavy_resources)
        page = context.new_page()
        try:
            page.goto(url, wait_until="load", timeout=30000)
            page.wait_for_timeout(2000) # JS Render Buffer
            
            text = page.evaluate(SMART_EXTRACT_JS)
            if text and len(text) > 50:
                return text
                
            return None
            
        except Exception as e:
            print(f"  [Warning] Failed to scrape documentation page: {e}")
            return None
        finally:
            page.close()
            context.close()
            browser.close()

def scrape_forum_thread(url: str) -> dict:
    DOM_WALK_JS = """
        (el) => {
            function isBlockish(node) {
                try {
                    const d = window.getComputedStyle(node).display;
                    return d === 'block' || d === 'list-item' || d === 'flex' || d.startsWith('table');
                } catch (e) { return false; }
            }
            function walk(node) {
                if (node.nodeType === Node.TEXT_NODE) return node.textContent;
                if (node.nodeType !== Node.ELEMENT_NODE) return '';
                const tag = node.tagName.toLowerCase();
                if (tag === 'br') return '\\n';
                if (tag === 'script' || tag === 'style') return '';
                let text = '';
                for (const child of node.childNodes) { text += walk(child); }
                if (isBlockish(node)) { text += '\\n'; }
                return text;
            }
            return walk(el);
        }
    """
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--disable-gpu",
                "--disable-dev-shm-usage",
                "--disable-extensions",
                "--disable-background-networking",
                "--disable-background-timer-throttling",
                "--disable-renderer-backgrounding",
                "--disable-default-apps",
                "--disable-sync",
                "--mute-audio",
                "--no-first-run",
                "--no-default-browser-check",
            ],
        )
        context = browser.new_context(user_agent="Mozilla/5.0")

        def block_heavy_resources(route):
            if route.request.resource_type in {"image", "media", "font"}:
                route.abort()
            else:
                route.continue_()

        context.route("**/*", block_heavy_resources)
        page = context.new_page()
        page.goto(url, wait_until="load", timeout=30000)

        try:
            page.wait_for_selector("[class*='message-body'], [class*='MessageBody'], article, main", timeout=10000)
        except Exception:
            pass

        page.wait_for_timeout(2000)
        page.evaluate("() => { document.querySelectorAll('nav, header, footer, aside').forEach(el => el.remove()); }")
        
        title = page.title()
        candidate_selectors = ["[class*='message-body']", "[class*='MessageBody']", "[class*='post-content']", "main", "article"]
        
        posts = []
        for sel in candidate_selectors:
            elements = page.query_selector_all(sel)
            if elements:
                posts = [element.evaluate(DOM_WALK_JS).strip() for element in elements if element.evaluate(DOM_WALK_JS).strip()]
                break
        if not posts:
            body_element = page.query_selector("body")
            if body_element:
                posts = [body_element.evaluate(DOM_WALK_JS)]
        
        browser.close()
    
    return {"url": url, "title": title, "posts": [re.sub(r"\n{3,}", "\n\n", p) for p in posts]}

def handle_oracle_query(search_query: str) -> dict:
    start_time = time.perf_counter()
    search_query = search_query.strip()
    
    error_match = re.search(r'(ORA-\d{4,5}|FRM-\d{4,5}|OSD-\d{4,5})', search_query, re.IGNORECASE)
    is_error_code = bool(error_match)
    target_term = error_match.group(1).upper() if is_error_code else search_query

    # PATH 1: Forums
    if is_error_code:
        try:
            forum_url = find_forum_url(target_term)
            if forum_url:
                raw_scrape = scrape_forum_thread(forum_url)
                cleaned_payload = clean_scrape_result(raw_scrape)
                
                if cleaned_payload.get("question") or cleaned_payload.get("replies"):
                    latency_ms = int((time.perf_counter() - start_time) * 1000)
                    return {
                        "status": "success",
                        "intent": "technical_oracle",
                        "extracted_parameters": {"query": target_term},
                        "display_payload": {
                            "title": cleaned_payload.get("title", f"Oracle Forums: {target_term}"),
                            "main_text": cleaned_payload.get("question", ""), 
                            "source_url": forum_url,
                            "metadata": {
                                "source_type": "Community Forums",
                                "replies": cleaned_payload.get("replies", []),
                                "replies_count": len(cleaned_payload.get("replies", []))
                            }
                        },
                        "system_metrics": {"latency_ms": latency_ms, "confidence_score": 0.8}
                    }
        except Exception as e:
            print(f"  [Debug] Forum path failed for {target_term}: {e}. Falling back to Docs...")

    # PATH 2: Official Documentation
    try:
        # Refine broad queries to fetch deeper technical pages
        search_intent = target_term if is_error_code else f"{target_term} concepts or usage"
        docs_url = find_docs_url(search_intent)
        
        if docs_url:
            raw_doc_text = scrape_docs_page(docs_url)
            if raw_doc_text:
                latency_ms = int((time.perf_counter() - start_time) * 1000)
                
                # Apply Level 1: Smart Chunking to the perfectly scraped text
                main_text = get_smart_snippet(raw_doc_text, 2000)
                extraction_method = "Semantic DOM Parsing + Smart Chunking"
                
                # Apply pure deterministic regex for error codes if possible
                if is_error_code:
                    parsed_doc = extract_cause_and_action(raw_doc_text)
                    if parsed_doc:
                        main_text = f"**CAUSE:**\n{parsed_doc['cause']}\n\n**ACTION:**\n{parsed_doc['action']}"
                        extraction_method = "Deterministic Regex Extraction"
                
                return {
                    "status": "success",
                    "intent": "technical_oracle",
                    "extracted_parameters": {"query": target_term},
                    "display_payload": {
                        "title": f"Oracle Official Documentation: {target_term}",
                        "main_text": main_text, 
                        "source_url": docs_url,
                        "metadata": {
                            "source_type": "Official Documentation",
                            "extraction_method": extraction_method
                        }
                    },
                    "system_metrics": {"latency_ms": latency_ms, "confidence_score": 1.0}
                }
            else:
                print(f"  [Debug] Scraper returned empty content for URL: {docs_url}")
        else:
            print(f"  [Debug] Could not locate a valid Docs URL for: {target_term}")
    except Exception as e:
        print(f"  [Debug] Documentation path failed: {e}")

    # PATH 3: Failure
    latency_ms = int((time.perf_counter() - start_time) * 1000)
    return {
        "status": "error",
        "intent": "technical_oracle",
        "extracted_parameters": {"query": target_term},
        "display_payload": {
            "title": f"Oracle Search Failed ({target_term})",
            "main_text": "Could not find relevant discussions on Oracle Forums or Official Documentation.",
            "source_url": None,
            "metadata": {}
        },
        "system_metrics": {"latency_ms": latency_ms, "confidence_score": 0.0}
    }