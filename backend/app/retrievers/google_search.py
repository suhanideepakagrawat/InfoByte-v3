import os
import requests
from dotenv import load_dotenv

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '..', '..', '.env'))

SERPAPI_KEY = os.environ.get("SERPAPI_KEY2")

def handle_google_search(query: str) -> dict:
    if not SERPAPI_KEY:
        return {"display_payload": {"title": "Error", "main_text": "SERPAPI_KEY2 not configured."}}
        
    params = {
        "engine": "google",
        "q": query,
        "api_key": SERPAPI_KEY,
        "num": 5
    }
    
    try:
        response = requests.get("https://serpapi.com/search", params=params, timeout=15)
        data = response.json()
        results = data.get("organic_results", [])
        
        if not results:
            return {"display_payload": {"title": f"No Results for '{query}'", "main_text": "No results found on Google."}}

        # Explicitly slice the results list to exactly 5 items
        limited_results = results[:5]

        # Format results for the UI
        formatted_text = "\n\n".join([
            f"### {r['title']}\n{r.get('snippet', 'No snippet available.')}\n[🔗 {r['link']}]({r['link']})"
            for r in limited_results
        ])
        
        return {
            "display_payload": {
                "title": f"Google Search Results for '{query}'",
                "main_text": formatted_text,
                "source_url": data.get("search_metadata", {}).get("google_url", "https://google.com")
            }
        }
    except Exception as e:
        return {"display_payload": {"title": "Search Error", "main_text": f"Google API Error: {str(e)}"}}