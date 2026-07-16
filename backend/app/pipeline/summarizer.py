import os
import time
from google import genai
from google.genai import types
from app.models.summary import InfoByteSynthesis

def generate_engine_synthesis(query: str, intent: str, results_dict: dict) -> InfoByteSynthesis:
    """
    Builds a bounded source canvas, sends it to Gemini with automatic retry logic,
    and returns the structured summary.
    """
    client = genai.Client()

    # 1. Format the isolated source environment blocks
    source_canvas = f"USER QUERY: {query}\nINTENT SCOPE: {intent}\n\n"
    for source_name, source_data in results_dict.items():
        payload = source_data.get("display_payload", {})
        main_text = payload.get("main_text", "")
        source_url = payload.get("source_url", "No direct link")
        source_canvas += f"=========================================\nSOURCE: {source_name.upper()}\nURL: {source_url}\n-----------------------------------------\n{main_text}\n=========================================\n\n"

    system_instruction = """
    You are the core synthesis and reasoning layer of the InfoByte architecture.
    You must populate two fields:
    1. factual_summary: Condense the provided context blocks. Do not add outside knowledge.
    2. llm_overview: Provide your own comprehensive, expert engineering overview.
    """

    # 2. Retry Logic with Exponential Backoff
    MAX_RETRIES = 3
    for attempt in range(MAX_RETRIES):
        try:
            response = client.models.generate_content(
                model='gemini-3.5-flash',
                contents=f"Please analyze these components and generate the engine contract response:\n\n{source_canvas}",
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    response_mime_type="application/json",
                    response_schema=InfoByteSynthesis,
                    temperature=0.2,
                ),
            )
            return response.parsed
            
        except Exception as e:
            # Check if the error is a 503 (Unavailable) or 429 (Too many requests)
            if ("503" in str(e) or "429" in str(e)) and attempt < MAX_RETRIES - 1:
                wait_time = (attempt + 1) * 2 # Wait 2s, 4s, 6s...
                print(f"[SUMMARIZER] Request throttled/unavailable. Retrying in {wait_time}s (Attempt {attempt+1}/{MAX_RETRIES})...")
                time.sleep(wait_time)
                continue
            else:
                print(f"[SUMMARIZER CORE ERROR] Gemini synthesis failed permanently: {e}")
                return InfoByteSynthesis(
                    factual_summary="Synthesis engine currently busy. Please try again in a moment.",
                    llm_overview="Synthesis model is temporarily unavailable due to high demand."
                )