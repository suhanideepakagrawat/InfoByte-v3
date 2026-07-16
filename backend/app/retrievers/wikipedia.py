"""
wikipedia.py
Now supports OpenSearch for disambiguation.
"""

import time
import requests
from app.pipeline.wiki_parser import parse_article, clean_article

def search_wikipedia(query: str, limit: int = 5) -> list:
    """Uses Wikipedia OpenSearch API to get candidate articles."""
    url = "https://en.wikipedia.org/w/api.php"
    params = {
        "action": "opensearch",
        "search": query,
        "limit": limit,
        "format": "json"
    }
    headers = {'User-Agent': 'InfoByteBot/1.0 (techstudent@shivnadar.edu.in)'}
    response = requests.get(url, params=params, headers=headers, timeout=10)
    response.raise_for_status()
    data = response.json()
    # Data format: [query, [titles], [descriptions], [urls]]
    results = []
    # Zip the three lists into a list of dicts
    for i in range(len(data[1])):
        results.append({
            "title": data[1][i],
            "description": data[2][i],
            "url": data[3][i]
        })
    return results

def download_article(url: str) -> str:
    headers = {'User-Agent': 'InfoByteBot/1.0 (techstudent@shivnadar.edu.in)'}
    response = requests.get(url, headers=headers, timeout=10)
    response.raise_for_status()
    return response.text

def handle_wiki_query(normalized_query: str, url: str = None) -> dict:
    start_time = time.perf_counter()

    # 1. If no URL is provided, perform a search to see if we need to disambiguate
    if not url:
        results = search_wikipedia(normalized_query)
        # If we have multiple results, return them as options
        if len(results) > 1:
            return {
                "status": "success",
                "intent": "wiki",
                "display_payload": {
                    "title": f"Multiple results for '{normalized_query}'",
                    "main_text": "Please select one of the following articles:",
                    "source_url": None,
                    "metadata": {"requires_selection": True, "options": results}
                },
                "system_metrics": {"latency_ms": int((time.perf_counter() - start_time) * 1000)}
            }
        elif len(results) == 1:
            url = results[0]["url"]
        else:
            return {"status": "error", "display_payload": {"title": "No results found"}}

    # 2. Proceed to scrape the selected URL
    try:
        html = download_article(url)
        parsed = parse_article(html)
        cleaned = clean_article(parsed)
        
        return {
            "status": "success",
            "intent": "wiki",
            "display_payload": {
                "title": cleaned.get("title"),
                "main_text": cleaned.get("full_text"),
                "source_url": url,
                "metadata": {"requires_selection": False}
            },
            "system_metrics": {"latency_ms": int((time.perf_counter() - start_time) * 1000)}
        }
    except Exception as e:
        return {"status": "error", "display_payload": {"title": "Scraping Error", "main_text": str(e)}}