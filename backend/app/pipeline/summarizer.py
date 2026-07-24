"""
summarizer.py

Groq-powered bounded synthesis engine for InfoByte.

Features:
- Query-relevant evidence selection
- Source-level extraction
- Text chunking
- Duplicate removal
- Relevance ranking
- Hard evidence budget
- Per-source diversity
- 413 / oversized request protection
- Retry only for genuinely transient errors
- Strict source-bounded synthesis
"""

import json
import os
import re
import time
from typing import Any, Dict, List, Tuple

from dotenv import load_dotenv
from groq import Groq

from app.models.summary import InfoByteSynthesis


# ==========================================================
# Environment
# ==========================================================

load_dotenv()


# ==========================================================
# Configuration
# ==========================================================

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

GROQ_MODEL = os.getenv(
    "GROQ_MODEL",
    "llama-3.3-70b-versatile"
)

MAX_RETRIES = 3


# ----------------------------------------------------------
# Evidence size controls
# ----------------------------------------------------------

MAX_CHUNK_CHARS = 1800
MAX_SELECTED_CHUNKS = 12
MAX_EVIDENCE_CHARS = 24000
MAX_CHUNKS_PER_SOURCE = 4
MIN_CHUNK_CHARS = 60


# ==========================================================
# Groq Client
# ==========================================================

def _get_groq_client() -> Groq:
    """
    Create and return the Groq client.
    """
    if not GROQ_API_KEY:
        raise RuntimeError(
            "GROQ_API_KEY is not configured. "
            "Add GROQ_API_KEY to the environment."
        )

    return Groq(
        api_key=GROQ_API_KEY
    )


# ==========================================================
# Basic Text Helpers
# ==========================================================

def _safe_json(value: Any) -> str:
    """
    Safely convert structured data into compact JSON.
    """
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            default=str,
            separators=(",", ":")
        )
    except Exception:
        return str(value)


def _normalize_whitespace(text: str) -> str:
    """
    Normalize repeated whitespace while preserving readable
    paragraph boundaries where possible.
    """
    if not text:
        return ""

    text = str(text)
    text = text.replace("\r\n", "\n")
    text = text.replace("\r", "\n")

    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()


def _normalize_for_duplicate_check(text: str) -> str:
    """
    Produce a normalized representation for duplicate detection.
    """
    text = text.lower()
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"[^\w\s]", "", text)
    return text.strip()


def _tokenize_for_relevance(text: str) -> set:
    """
    Lightweight keyword tokenization.
    """
    if not text:
        return set()

    words = re.findall(r"[a-zA-Z0-9]+", text.lower())

    stopwords = {
        "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
        "of", "to", "in", "on", "for", "with", "and", "or", "from", "by",
        "at", "as", "it", "this", "that", "these", "those", "what", "which",
        "who", "whom", "how", "why", "when", "where", "tell", "me", "about",
        "give", "show", "find", "search"
    }

    return {
        word
        for word in words
        if len(word) > 1 and word not in stopwords
    }


# ==========================================================
# Source Extraction
# ==========================================================

def _extract_source_url(source_data: Any) -> str:
    """
    Extract the primary source URL if available.
    """
    if not isinstance(source_data, dict):
        return ""

    display_payload = source_data.get("display_payload")

    if isinstance(display_payload, dict):
        source_url = display_payload.get("source_url")
        if source_url:
            return str(source_url)

    for key in ["source_url", "url", "link"]:
        value = source_data.get(key)
        if value:
            return str(value)

    return ""


def _extract_text_recursive(value: Any, depth: int = 0) -> List[str]:
    """
    Recursively extract useful textual values from nested retriever structures.
    """
    if depth > 6:
        return []

    parts = []

    if value is None:
        return parts

    if isinstance(value, str):
        cleaned = _normalize_whitespace(value)
        if cleaned:
            parts.append(cleaned)
        return parts

    if isinstance(value, (int, float, bool)):
        return parts

    if isinstance(value, list):
        for item in value:
            parts.extend(_extract_text_recursive(item, depth + 1))
        return parts

    if isinstance(value, dict):
        ignored_keys = {
            "status", "intent", "source_url", "url", "link",
            "http_status", "status_code", "response_time", "latency", "success"
        }

        for key, item in value.items():
            if key in ignored_keys:
                continue
            parts.extend(_extract_text_recursive(item, depth + 1))
        return parts

    return parts


def _extract_source_content(source_data: Any) -> str:
    """
    Extract meaningful textual content from one retriever result.
    """
    if source_data is None:
        return ""

    if isinstance(source_data, str):
        return _normalize_whitespace(source_data)

    if not isinstance(source_data, dict):
        return _normalize_whitespace(str(source_data))

    parts = []
    display_payload = source_data.get("display_payload")

    if isinstance(display_payload, dict):
        title = display_payload.get("title")
        if title:
            parts.append(str(title))

        main_text = display_payload.get("main_text")
        if main_text:
            parts.extend(_extract_text_recursive(main_text))

        for key, value in display_payload.items():
            if key in {"title", "main_text", "source_url"}:
                continue
            parts.extend(_extract_text_recursive(value))

    for key, value in source_data.items():
        if key in {"display_payload", "intent", "status", "source_url", "url", "link"}:
            continue
        parts.extend(_extract_text_recursive(value))

    unique_parts = []
    seen = set()

    for part in parts:
        normalized = _normalize_for_duplicate_check(part)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        unique_parts.append(part)

    return "\n\n".join(unique_parts)


# ==========================================================
# Chunking
# ==========================================================

def _split_long_text(text: str, max_chars: int) -> List[str]:
    """
    Split one long paragraph using sentence boundaries.
    """
    sentences = re.split(r"(?<=[.!?])\s+", text)
    chunks = []
    current = ""

    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue

        if len(sentence) > max_chars:
            if current:
                chunks.append(current.strip())
                current = ""

            start = 0
            while start < len(sentence):
                end = start + max_chars
                piece = sentence[start:end].strip()
                if piece:
                    chunks.append(piece)
                start = end
            continue

        candidate = f"{current} {sentence}" if current else sentence
        if len(candidate) <= max_chars:
            current = candidate
        else:
            if current:
                chunks.append(current.strip())
            current = sentence

    if current:
        chunks.append(current.strip())

    return chunks


def _chunk_text(text: str) -> List[str]:
    """
    Convert source content into manageable semantic chunks.
    """
    text = _normalize_whitespace(text)
    if not text:
        return []

    paragraphs = re.split(r"\n\s*\n", text)
    chunks = []
    current = ""

    for paragraph in paragraphs:
        paragraph = paragraph.strip()
        if not paragraph:
            continue

        if len(paragraph) > MAX_CHUNK_CHARS:
            if current:
                chunks.append(current.strip())
                current = ""
            chunks.extend(_split_long_text(paragraph, MAX_CHUNK_CHARS))
            continue

        candidate = f"{current}\n\n{paragraph}" if current else paragraph
        if len(candidate) <= MAX_CHUNK_CHARS:
            current = candidate
        else:
            if current:
                chunks.append(current.strip())
            current = paragraph

    if current:
        chunks.append(current.strip())

    return [chunk for chunk in chunks if len(chunk) >= MIN_CHUNK_CHARS]


# ==========================================================
# Duplicate Detection
# ==========================================================

def _is_near_duplicate(text: str, selected_texts: List[str]) -> bool:
    """
    Detect substantial duplicate overlap.
    """
    normalized = _normalize_for_duplicate_check(text)
    if not normalized:
        return True

    words = set(normalized.split())
    if not words:
        return True

    for existing in selected_texts:
        existing_normalized = _normalize_for_duplicate_check(existing)
        if normalized == existing_normalized:
            return True

        existing_words = set(existing_normalized.split())
        if not existing_words:
            continue

        intersection = len(words.intersection(existing_words))
        smaller_size = min(len(words), len(existing_words))

        if smaller_size == 0:
            continue

        if (intersection / smaller_size) >= 0.85:
            return True

    return False


# ==========================================================
# Relevance Ranking
# ==========================================================

def _calculate_relevance_score(
    query: str,
    intent: str,
    source_name: str,
    chunk: str
) -> float:
    """
    Calculate lightweight lexical relevance.
    """
    query_terms = _tokenize_for_relevance(query)
    intent_terms = _tokenize_for_relevance(intent.replace("_", " "))
    chunk_terms = _tokenize_for_relevance(chunk)
    source_terms = _tokenize_for_relevance(source_name)

    if not chunk_terms:
        return 0.0

    query_overlap = len(query_terms.intersection(chunk_terms))
    intent_overlap = len(intent_terms.intersection(chunk_terms))
    source_overlap = len(query_terms.intersection(source_terms))

    score = 0.0
    score += query_overlap * 5.0
    score += intent_overlap * 1.5
    score += source_overlap * 2.0

    normalized_query = query.lower().strip()
    normalized_chunk = chunk.lower()

    if normalized_query and normalized_query in normalized_chunk:
        score += 10.0

    if query_terms:
        coverage = query_overlap / len(query_terms)
        score += coverage * 10.0

    return score


# ==========================================================
# Evidence Selection
# ==========================================================

def _collect_candidate_chunks(
    query: str,
    intent: str,
    results_dict: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """
    Extract, chunk, and score all retrieved sources.
    """
    candidates = []

    for source_name, source_data in results_dict.items():
        source_content = _extract_source_content(source_data)
        if not source_content:
            continue

        source_url = _extract_source_url(source_data)
        chunks = _chunk_text(source_content)

        for index, chunk in enumerate(chunks):
            score = _calculate_relevance_score(
                query=query,
                intent=intent,
                source_name=source_name,
                chunk=chunk
            )

            candidates.append({
                "source_name": str(source_name),
                "source_url": source_url,
                "chunk_index": index,
                "text": chunk,
                "score": score
            })

    candidates.sort(key=lambda item: item["score"], reverse=True)
    return candidates


def _select_evidence_chunks(
    query: str,
    intent: str,
    results_dict: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """
    Select relevant evidence under the hard prompt budget.
    """
    candidates = _collect_candidate_chunks(query=query, intent=intent, results_dict=results_dict)
    if not candidates:
        return []

    selected = []
    selected_texts = []
    source_counts = {}
    total_chars = 0

    for candidate in candidates:
        if len(selected) >= MAX_SELECTED_CHUNKS:
            break

        source_name = candidate["source_name"]
        current_source_count = source_counts.get(source_name, 0)

        if current_source_count >= MAX_CHUNKS_PER_SOURCE:
            continue

        text = candidate["text"]
        if _is_near_duplicate(text, selected_texts):
            continue

        projected_size = total_chars + len(text)
        if projected_size > MAX_EVIDENCE_CHARS:
            continue

        selected.append(candidate)
        selected_texts.append(text)
        total_chars = projected_size
        source_counts[source_name] = current_source_count + 1

    minimum_desired_chunks = min(5, MAX_SELECTED_CHUNKS)

    if len(selected) < minimum_desired_chunks:
        for candidate in candidates:
            if len(selected) >= minimum_desired_chunks:
                break
            if candidate in selected:
                continue

            source_name = candidate["source_name"]
            current_source_count = source_counts.get(source_name, 0)

            if current_source_count >= MAX_CHUNKS_PER_SOURCE:
                continue

            text = candidate["text"]
            if _is_near_duplicate(text, selected_texts):
                continue

            projected_size = total_chars + len(text)
            if projected_size > MAX_EVIDENCE_CHARS:
                continue

            selected.append(candidate)
            selected_texts.append(text)
            total_chars = projected_size
            source_counts[source_name] = current_source_count + 1

    return selected


# ==========================================================
# Source Canvas
# ==========================================================

def _build_source_canvas(
    query: str,
    intent: str,
    results_dict: Dict[str, Any]
) -> Tuple[str, int]:
    """
    Build a bounded evidence canvas.
    """
    selected_chunks = _select_evidence_chunks(query=query, intent=intent, results_dict=results_dict)

    blocks = [
        f"USER QUERY:\n{query}",
        f"CONFIRMED INTENT:\n{intent}",
        "EVIDENCE RULE:\nThe following retrieved excerpts are the only permitted factual evidence."
    ]

    if not selected_chunks:
        blocks.append("NO USABLE RETRIEVED EVIDENCE WAS AVAILABLE.")
        return ("\n\n".join(blocks), 0)

    for index, item in enumerate(selected_chunks, start=1):
        source_name = item["source_name"]
        source_url = item["source_url"]
        text = item["text"]

        block = [f"[EVIDENCE {index}]", f"SOURCE: {source_name}"]
        if source_url:
            block.append(f"URL: {source_url}")

        block.append(f"CONTENT:\n{text}")
        blocks.append("\n".join(block))

    return ("\n\n".join(blocks), len(selected_chunks))


# ==========================================================
# System Prompts
# ==========================================================

SYSTEM_INSTRUCTION = """
You are the bounded synthesis layer of the InfoByte search
and retrieval system.

You receive:
1. A user query.
2. A confirmed query intent.
3. Selected excerpts from externally retrieved sources.

You must return exactly one valid JSON object containing
exactly these two string fields:
{
  "factual_summary": "...",
  "llm_overview": "..."
}

STRICT EVIDENCE RULES:
- The supplied evidence excerpts are the ONLY factual knowledge available to you.
- Never introduce facts from pretrained knowledge.
- Never invent missing details.
- Never fill factual gaps using assumptions.
- Never fabricate citations, URLs, statistics, quotations, research findings, medical information, technical facts, or dates.
- If sources disagree, explicitly state the disagreement.
- If the evidence is insufficient, state that clearly.

FACTUAL_SUMMARY:
Create a concise and directly relevant answer using only information explicitly supported by the supplied evidence.

LLM_OVERVIEW:
Create a structured synthesis of the supplied evidence.

Return valid JSON only. Do not use Markdown code fences.
"""

MEDICINE_SYSTEM_INSTRUCTION = """
You are the bounded medical synthesis layer of the InfoByte search system.

Summarize ONLY the provided evidence.
Do NOT summarize medicine cards or re-read raw FDA text if structured summaries exist.

Generate a synthesis covering ONLY these four areas in llm_overview:
- Overview
- Key clinical points
- Safety summary
- When to seek medical advice

STRICT CONSTRAINTS:
- Keep the ENTIRE summary under 250 words.
- Do NOT hallucinate or infer missing facts.
- Rely strictly on the provided evidence excerpts.

You must return exactly one valid JSON object containing exactly these two string fields:
{
  "factual_summary": "...",
  "llm_overview": "..."
}

Return valid JSON only. Do not use Markdown code fences.
"""


# ==========================================================
# Response Parser
# ==========================================================

def _parse_groq_response(raw_content: str) -> InfoByteSynthesis:
    """
    Parse and validate Groq's JSON response.
    """
    if not raw_content:
        raise ValueError("Groq returned an empty response.")

    cleaned = raw_content.strip()
    if cleaned.startswith("```json"):
        cleaned = cleaned[7:]
    elif cleaned.startswith("```"):
        cleaned = cleaned[3:]

    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]

    cleaned = cleaned.strip()
    parsed = json.loads(cleaned)

    if not isinstance(parsed, dict):
        raise ValueError("Groq response must be a JSON object.")

    factual_summary = parsed.get("factual_summary")
    llm_overview = parsed.get("llm_overview")

    if not isinstance(factual_summary, str) or not isinstance(llm_overview, str):
        raise ValueError("Groq response missing required summary fields.")

    return InfoByteSynthesis(
        factual_summary=factual_summary.strip(),
        llm_overview=llm_overview.strip()
    )


# ==========================================================
# Error Helpers
# ==========================================================

def _is_request_too_large(error_text: str) -> bool:
    text = error_text.lower()
    indicators = ["413", "request too large", "requested", "tokens per minute", "context_length_exceeded"]
    return any(indicator in text for indicator in indicators)


def _is_retryable_error(error_text: str) -> bool:
    if _is_request_too_large(error_text):
        return False

    text = error_text.lower()
    retryable_indicators = [
        "429", "500", "502", "503", "504",
        "timeout", "timed out", "connection error", "connection reset", "temporarily unavailable"
    ]
    return any(indicator in text for indicator in retryable_indicators)


# ==========================================================
# Main Synthesis Function
# ==========================================================

def generate_engine_synthesis(
    query: str,
    intent: str,
    results_dict: dict
) -> InfoByteSynthesis:
    """
    Generate InfoByte's synthesis outputs.
    """
    client = _get_groq_client()

    source_canvas, chunk_count = _build_source_canvas(
        query=query,
        intent=intent,
        results_dict=results_dict
    )

    print(
        f"[SUMMARIZER] Selected {chunk_count} evidence chunks. "
        f"Evidence canvas size: {len(source_canvas):,} characters."
    )

    if chunk_count == 0:
        return InfoByteSynthesis(
            factual_summary="The retrieved sources did not provide enough usable evidence to generate a grounded summary.",
            llm_overview="No sufficiently usable retrieved evidence was available for source-bounded synthesis."
        )

    user_prompt = f"""
Answer the original user query using only the selected retrieved evidence below.

Requirements:
- Use only supplied evidence.
- factual_summary must directly answer the query.
- llm_overview must synthesize the evidence under 250 words.
- Do not introduce external knowledge or invent missing information.
- Return valid JSON only.

SELECTED RETRIEVED EVIDENCE:

{source_canvas}
""".strip()

    active_system_prompt = MEDICINE_SYSTEM_INSTRUCTION if intent == "medicine" else SYSTEM_INSTRUCTION

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = client.chat.completions.create(
                model=GROQ_MODEL,
                messages=[
                    {"role": "system", "content": active_system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.1,
                response_format={"type": "json_object"}
            )

            raw_content = response.choices[0].message.content
            return _parse_groq_response(raw_content)

        except Exception as e:
            error_text = str(e)

            if _is_request_too_large(error_text):
                print(f"[SUMMARIZER SIZE ERROR] Groq rejected request: prompt too large ({len(source_canvas):,} chars).")
                return InfoByteSynthesis(
                    factual_summary="The retrieved source results are available, but evidence was too large to process in one request.",
                    llm_overview="Synthesis could not be generated within processing limit. Source results remain available."
                )

            retryable = _is_retryable_error(error_text)
            if retryable and attempt < MAX_RETRIES:
                wait_time = attempt * 2
                print(f"[SUMMARIZER] Temporary error: {e}. Retrying in {wait_time}s ({attempt}/{MAX_RETRIES})...")
                time.sleep(wait_time)
                continue

            print(f"[SUMMARIZER CORE ERROR] Groq synthesis failed: {e}")
            return InfoByteSynthesis(
                factual_summary="The synthesis engine is currently unavailable. Please review the retrieved source results.",
                llm_overview="Source data is available, but AI synthesis could not be generated at this time."
            )