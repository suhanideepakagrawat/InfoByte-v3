"""
documentation.py

Searches for official documentation using SerpAPI, fetches the raw HTML using 
a headless browser (to bypass 429 blocks), and extracts the most relevant sections.
"""
import os
import time
import requests
from playwright.sync_api import sync_playwright
from app.pipeline.docs_parser import extract_relevant_docs

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

SERPAPI_KEY = os.environ.get("SERPAPI_KEY")

DOC_DOMAINS = [
    "docs.", "readthedocs.io", "developer.", "api.", "manual.", 
    "learn.", "reference.", "react.dev", "nextjs.org/docs"
]

def find_documentation_url(query: str) -> str | None:
    """Uses SerpAPI to find the top official documentation link."""
    if not SERPAPI_KEY:
        raise RuntimeError("Missing SERPAPI_KEY parameter in environment variables.")
    
    try:
        resp = requests.get(
            "https://serpapi.com/search",
            params={"engine": "google", "q": f"{query} documentation", "num": 5, "api_key": SERPAPI_KEY},
            timeout=15
        )
        resp.raise_for_status()
        results = resp.json().get("organic_results", [])
        
        for result in results:
            url = result.get("link", "")
            if any(domain in url.lower() for domain in DOC_DOMAINS):
                return url
                
        if results:
            return results[0].get("link", "")
            
        return None
    except Exception as e:
        print(f"[Docs Retriever] SerpAPI Error: {e}")
        return None

def fetch_html_with_playwright(url: str) -> str:
    """Uses headless Chromium to bypass Cloudflare/ReadTheDocs blocks."""
    html_content = ""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        # Using a highly standard user-agent helps bypass bot detection
        page = browser.new_page(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        )
        try:
            page.goto(url, timeout=20000, wait_until="domcontentloaded")
            
            # THE FIX: Force the browser to wait for the actual docs to render.
            # This gives Cloudflare 8 seconds to process its background JS challenge.
            try:
                page.wait_for_selector("main, [role='main'], .document, article", timeout=8000)
            except Exception:
                # If the specific selector isn't found, wait an extra 3 seconds 
                # as a fallback before scraping whatever is on the screen.
                page.wait_for_timeout(3000)
                
            html_content = page.content()
        except Exception as e:
            print(f"[Docs Scraper] Playwright Error: {e}")
        finally:
            browser.close()
            
    return html_content

def handle_documentation_query(search_query: str) -> dict:
    """
    Executes the documentation search, scrapes the HTML via Playwright, 
    scores chunks, and formats into the Data Contract.
    """
    start_time = time.perf_counter()
    try:
        url = find_documentation_url(search_query)
        if not url:
            raise ValueError("No official documentation found on Google.")
            
        # Fetch the HTML using Playwright to bypass WAFs
        raw_html = fetch_html_with_playwright(url)
        
        if not raw_html:
            raise ValueError("Failed to fetch HTML content from the target URL.")
            
        # Parse and score the chunks
        relevant_text = extract_relevant_docs(raw_html, search_query, max_chunks=3)
        
        if not relevant_text:
             raise ValueError("Failed to extract readable text from documentation DOM.")
             
        latency_ms = int((time.perf_counter() - start_time) * 1000)

        return {
            "status": "success",
            "intent": "general_code",
            "extracted_parameters": {"search_query": search_query},
            "display_payload": {
                "title": f"Official Documentation: {search_query}",
                "main_text": relevant_text,
                "source_url": url,
                "metadata": {
                    "extraction_method": "TF_Keyword_Scoring_Playwright"
                }
            },
            "system_metrics": {
                "latency_ms": latency_ms,
                "confidence_score": 1.0
            }
        }
    except Exception as e:
        latency_ms = int((time.perf_counter() - start_time) * 1000)
        return {
            "status": "error",
            "intent": "general_code",
            "extracted_parameters": {"search_query": search_query},
            "display_payload": {
                "title": "Documentation Retrieval Error",
                "main_text": "Failed to scrape official documentation.",
                "source_url": None,
                "metadata": {"error_details": str(e)}
            },
            "system_metrics": {"latency_ms": latency_ms, "confidence_score": 0.0}
        }