"""
router.py
Multi-Intent Parallel Router via RoBERTa Classifier
"""

import concurrent.futures
from typing import Optional
from app.api.classifier import intent_classifier
from app.pipeline.summarizer import generate_engine_synthesis

# Retrievers
from app.retrievers.oracle import handle_oracle_query
from app.retrievers.weather import handle_weather_query
from app.retrievers.wikipedia import handle_wiki_query
from app.retrievers.news import handle_news_query
from app.retrievers.stackoverflow import handle_stackoverflow_query
from app.retrievers.reddit import handle_reddit_query
from app.retrievers.google_search import handle_google_search


def _inject_intent(response: dict, intent: str) -> dict:
    """Ensures every response maintains the intent key for the frontend parsing."""
    if not isinstance(response, dict):
        response = {
            "status": "success",
            "display_payload": {
                "main_text": str(response)
            }
        }
    
    # If the scraper failed, format the error so the frontend displays it
    if "error" in response and "display_payload" not in response:
        response["display_payload"] = {
            "title": "Extraction Failed",
            "main_text": f"Scraper Error: {response['error']}"
        }

    if "intent" not in response:
        response["intent"] = intent

    return response


# ----------------------------------------------------------
# Display priority of sources for each intent
# ----------------------------------------------------------

INTENT_SOURCE_ORDER = {
    "technical_oracle": ["oracle", "stackoverflow", "google_search"],
    "technical_code": ["stackoverflow", "reddit", "google_search"],
    "general_wiki": ["wikipedia", "google_search"],
    "movies": ["wikipedia", "google_search"],
    "weather": ["weather", "google_search"],
    "discussion_social": ["news", "reddit", "google_search"],
    "google_search": ["google_search"]
}


def route_query(user_query: str, confirmed_intent: Optional[str] = None, skip_synthesis: bool = False) -> dict:
    query_lower = user_query.lower().strip()

    # 1. Intent Determination
    if confirmed_intent:
        top_intent = confirmed_intent
        selected_intents = [top_intent]
        predictions = [{"label": top_intent, "score": 1.0}]
    else:
        predictions = intent_classifier.predict_intents(query_lower)
        if not predictions:
            return {"error": "Empty or invalid query received."}
        top_intent = predictions[0]["label"]
        selected_intents = [top_intent]

    # 3. Build scraper list
    scraper_map = {}
    for intent in selected_intents:
        if intent == "technical_code":
            scraper_map["stackoverflow"] = handle_stackoverflow_query
            scraper_map["reddit"] = lambda q: handle_reddit_query(q, "technical_code")
        elif intent == "technical_oracle":
            scraper_map["oracle"] = handle_oracle_query
            scraper_map["stackoverflow"] = handle_stackoverflow_query
        elif intent == "general_wiki" or intent == "movies":
            scraper_map["wikipedia"] = handle_wiki_query
        elif intent == "weather":
            scraper_map["weather"] = handle_weather_query
        elif intent == "discussion_social":
            scraper_map["news"] = handle_news_query
            scraper_map["reddit"] = lambda q: handle_reddit_query(q, "discussion_social")
        elif intent == "google_search":
            pass

    # ALWAYS execute Google Search universally to guarantee context fallback
    scraper_map["google_search"] = handle_google_search

    # 4. Execute all scrapers in parallel safely
    completed_results = {}
    with concurrent.futures.ThreadPoolExecutor() as executor:
        future_to_source = {executor.submit(func, user_query): source for source, func in scraper_map.items()}
        for future in concurrent.futures.as_completed(future_to_source):
            source = future_to_source[future]
            try:
                result = future.result()
                completed_results[source] = _inject_intent(result, top_intent)
            except Exception as exc:
                print(f"[ROUTER ERROR] Source '{source}' failed: {exc}")
                completed_results[source] = _inject_intent({"error": str(exc)}, top_intent)

    # 5. Reorder payload
    packaged_data = {}
    for intent in selected_intents:
        for source in INTENT_SOURCE_ORDER.get(intent, []):
            if source in completed_results and source not in packaged_data:
                packaged_data[source] = completed_results[source]
                
    for source, result in completed_results.items():
        if source not in packaged_data: 
            packaged_data[source] = result

    # 5.5 Gemini Synthesis Generation (Bypassed initially to render UI instantly)
    if skip_synthesis:
        ai_synthesis = None
    else:
        try:
            synth = generate_engine_synthesis(query_lower, top_intent, packaged_data)
            ai_synthesis = {
                "factual_summary": synth.factual_summary,
                "llm_overview": synth.llm_overview
            }
        except Exception as e:
            ai_synthesis = {
                "factual_summary": "⚠️ Gemini API Limit Exceeded. The AI synthesis engine is temporarily unavailable due to quota restrictions.",
                "llm_overview": f"System Message: {str(e)}"
            }

    # 6. Response
    return {
        "intents_detected": selected_intents,
        "confidence_scores": {p["label"]: f"{p['score'] * 100:.2f}%" for p in predictions[:2]},
        "payload": packaged_data,
        "ai_synthesis": ai_synthesis
    }