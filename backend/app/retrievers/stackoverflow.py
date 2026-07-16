"""
stackoverflow.py
Retrieves technical context including question, top answers, and comments.
"""
import time
import requests
from app.pipeline.stackoverflow_parser import clean_stackoverflow_body

SEARCH_API = "https://api.stackexchange.com/2.3/search/advanced"
QUESTION_API = "https://api.stackexchange.com/2.3/questions"
ANSWERS_API = "https://api.stackexchange.com/2.3/answers"
HEADERS = {"User-Agent": "InfoByte/1.0"}

def handle_stackoverflow_query(search_query: str) -> dict:
    start_time = time.perf_counter()
    try:
        # STEP 1: Search for relevant question ID
        params = {"site": "stackoverflow", "q": search_query, "sort": "relevance", "pagesize": 1}
        resp = requests.get(SEARCH_API, params=params, headers=HEADERS, timeout=10)
        resp.raise_for_status()
        items = resp.json().get("items", [])
        if not items: raise ValueError("No discussions found.")
        
        q_id = str(items[0]["question_id"])

        # STEP 2: Fetch Question Data
        q_resp = requests.get(f"{QUESTION_API}/{q_id}", params={"site": "stackoverflow", "filter": "withbody"}, headers=HEADERS)
        q_data = q_resp.json().get("items", [{}])[0]

        # STEP 3: Fetch Top Answers (Sorted by votes)
        ans_resp = requests.get(f"{QUESTION_API}/{q_id}/answers", params={"site": "stackoverflow", "filter": "withbody", "sort": "votes", "pagesize": 3}, headers=HEADERS)
        answers_raw = ans_resp.json().get("items", [])

        # STEP 4: Build Answer + Comment Object
        processed_answers = []
        for ans in answers_raw:
            ans_id = str(ans["answer_id"])
            
            # Fetch Comments for this specific answer
            # NOTE: kept the "filter": "withbody" fix here — without it the SE
            # API omits the comment body field entirely and c["body"] throws
            # KeyError: 'body' the moment any answer actually has comments.
            c_resp = requests.get(f"{ANSWERS_API}/{ans_id}/comments", params={"site": "stackoverflow", "filter": "withbody"}, headers=HEADERS)
            comments = [{"text": c.get("body", c.get("body_markdown", "")), "author": c.get("owner", {}).get("display_name", "User")} for c in c_resp.json().get("items", [])[:3]]
            
            processed_answers.append({
                "text": clean_stackoverflow_body(ans.get("body", "")),
                "score": ans.get("score", 0),
                "comments": comments
            })

        latency_ms = int((time.perf_counter() - start_time) * 1000)

        return {
            "status": "success",
            "intent": "general_code",
            "display_payload": {
                "title": q_data.get("title", "Stack Overflow Discussion"),
                "main_text": clean_stackoverflow_body(q_data.get("body", "")),
                "source_url": q_data.get("link", ""),
                "metadata": {
                    "score": q_data.get("score", 0),
                    "answers": processed_answers
                }
            },
            "system_metrics": {"latency_ms": latency_ms, "confidence_score": 1.0}
        }
    except Exception as e:
        return {
            "status": "error",
            "display_payload": {"title": "Error", "main_text": str(e)},
            "system_metrics": {"latency_ms": 0, "confidence_score": 0.0}
        }