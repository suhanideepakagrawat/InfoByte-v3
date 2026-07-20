"""
summarizer.py

Responsible for generating the final Gemini synthesis
from the bounded source results collected by InfoByte.
"""

import os
import time
import traceback

from google import genai
from google.genai import types

from app.models.summary import InfoByteSynthesis


# ----------------------------------------------------------
# Configuration
# ----------------------------------------------------------

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Keep your currently configured model here.
# If Render logs report a 404 / model-not-found error,
# replace this with a model available to your Gemini API account.
GEMINI_MODEL = "gemini-3.5-flash"

MAX_RETRIES = 3


# ----------------------------------------------------------
# Helper: fallback response
# ----------------------------------------------------------

def build_fallback_response(
    factual_message: str = (
        "Synthesis engine currently unavailable. "
        "Please try again in a moment."
    ),
) -> InfoByteSynthesis:
    """
    Returns a safe fallback response when Gemini synthesis fails.
    """

    return InfoByteSynthesis(
        factual_summary=factual_message,
        llm_overview="",
    )


# ----------------------------------------------------------
# Main synthesis function
# ----------------------------------------------------------

def generate_engine_synthesis(
    query: str,
    intent: str,
    results_dict: dict,
) -> InfoByteSynthesis:
    """
    Builds a bounded source canvas, sends it to Gemini,
    retries temporary failures, and returns a structured
    InfoByteSynthesis response.

    Detailed diagnostic information is printed to the
    deployment logs without exposing the Gemini API key.
    """

    # ======================================================
    # 1. Validate Gemini API key
    # ======================================================

    print(
        "\n[SUMMARIZER] Starting synthesis request",
        flush=True,
    )

    print(
        f"[SUMMARIZER] Gemini API key configured: "
        f"{bool(GEMINI_API_KEY)}",
        flush=True,
    )

    print(
        f"[SUMMARIZER] Model: {GEMINI_MODEL}",
        flush=True,
    )

    print(
        f"[SUMMARIZER] Query: {query}",
        flush=True,
    )

    print(
        f"[SUMMARIZER] Intent: {intent}",
        flush=True,
    )

    if not GEMINI_API_KEY:
        print(
            "[SUMMARIZER CONFIG ERROR] "
            "GEMINI_API_KEY is missing.",
            flush=True,
        )

        return build_fallback_response(
            "Synthesis is unavailable because the "
            "Gemini API configuration is missing."
        )

    # ======================================================
    # 2. Create Gemini client
    # ======================================================

    try:
        client = genai.Client(
            api_key=GEMINI_API_KEY
        )

        print(
            "[SUMMARIZER] Gemini client created successfully.",
            flush=True,
        )

    except Exception as e:
        print(
            "[SUMMARIZER CLIENT ERROR] "
            "Failed to create Gemini client.",
            flush=True,
        )

        print(
            f"[SUMMARIZER CLIENT ERROR] "
            f"Type: {type(e).__name__}",
            flush=True,
        )

        print(
            f"[SUMMARIZER CLIENT ERROR] "
            f"Message: {str(e)}",
            flush=True,
        )

        traceback.print_exc()

        return build_fallback_response(
            "Synthesis engine could not initialize."
        )

    # ======================================================
    # 3. Build bounded source canvas
    # ======================================================

    source_canvas = (
        f"USER QUERY: {query}\n"
        f"INTENT SCOPE: {intent}\n\n"
    )

    valid_sources = 0

    for source_name, source_data in results_dict.items():

        # Defensive validation
        if not isinstance(source_data, dict):
            print(
                f"[SUMMARIZER WARNING] "
                f"Skipping source '{source_name}' because "
                f"its data is not a dictionary.",
                flush=True,
            )
            continue

        payload = source_data.get(
            "display_payload",
            {}
        )

        if not isinstance(payload, dict):
            print(
                f"[SUMMARIZER WARNING] "
                f"Skipping source '{source_name}' because "
                f"display_payload is invalid.",
                flush=True,
            )
            continue

        main_text = payload.get(
            "main_text",
            ""
        )

        source_url = payload.get(
            "source_url",
            "No direct link",
        )

        # Convert safely to strings
        main_text = str(main_text or "")
        source_url = str(
            source_url or "No direct link"
        )

        if not main_text.strip():
            print(
                f"[SUMMARIZER WARNING] "
                f"Source '{source_name}' has no main_text.",
                flush=True,
            )

        source_canvas += (
            "=========================================\n"
            f"SOURCE: {source_name.upper()}\n"
            f"URL: {source_url}\n"
            "-----------------------------------------\n"
            f"{main_text}\n"
            "=========================================\n\n"
        )

        valid_sources += 1

    print(
        f"[SUMMARIZER] Valid sources added: "
        f"{valid_sources}",
        flush=True,
    )

    print(
        f"[SUMMARIZER] Source canvas length: "
        f"{len(source_canvas)} characters",
        flush=True,
    )

    if valid_sources == 0:
        print(
            "[SUMMARIZER WARNING] "
            "No valid sources were supplied.",
            flush=True,
        )

    # ======================================================
    # 4. System instruction
    # ======================================================

    system_instruction = """
You are the core synthesis and reasoning layer of the
InfoByte architecture.

You must populate exactly two fields:

1. factual_summary:
Condense the provided context blocks.
Do not add outside knowledge.
Only use information contained in the supplied sources.

2. llm_overview:
Provide your own comprehensive expert engineering overview.

Return the response using the required structured schema.
"""

    # ======================================================
    # 5. Gemini request with retry logic
    # ======================================================

    for attempt in range(MAX_RETRIES):

        attempt_number = attempt + 1

        print(
            "\n"
            + "=" * 70,
            flush=True,
        )

        print(
            f"[SUMMARIZER] Gemini request attempt "
            f"{attempt_number}/{MAX_RETRIES}",
            flush=True,
        )

        print(
            f"[SUMMARIZER] Sending "
            f"{len(source_canvas)} characters to Gemini.",
            flush=True,
        )

        try:

            # --------------------------------------------------
            # Gemini API call
            # --------------------------------------------------

            response = client.models.generate_content(
                model=GEMINI_MODEL,
                contents=(
                    "Please analyze these components and "
                    "generate the engine contract response:"
                    "\n\n"
                    f"{source_canvas}"
                ),
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    response_mime_type="application/json",
                    response_schema=InfoByteSynthesis,
                    temperature=0.2,
                ),
            )

            print(
                "[SUMMARIZER] Gemini API call completed.",
                flush=True,
            )

            # --------------------------------------------------
            # Check response object
            # --------------------------------------------------

            if response is None:
                print(
                    "[SUMMARIZER RESPONSE ERROR] "
                    "Gemini returned None.",
                    flush=True,
                )

                return build_fallback_response(
                    "Synthesis failed because Gemini "
                    "returned an empty response."
                )

            print(
                f"[SUMMARIZER] Response type: "
                f"{type(response).__name__}",
                flush=True,
            )

            # --------------------------------------------------
            # Check parsed structured output
            # --------------------------------------------------

            parsed_response = getattr(
                response,
                "parsed",
                None,
            )

            print(
                f"[SUMMARIZER] Parsed response available: "
                f"{parsed_response is not None}",
                flush=True,
            )

            if parsed_response is not None:

                print(
                    "[SUMMARIZER SUCCESS] "
                    "Structured Gemini synthesis generated "
                    "successfully.",
                    flush=True,
                )

                print(
                    "=" * 70,
                    flush=True,
                )

                return parsed_response

            # --------------------------------------------------
            # Structured parsing failed
            # --------------------------------------------------

            print(
                "[SUMMARIZER PARSE ERROR] "
                "Gemini returned a response but "
                "response.parsed is None.",
                flush=True,
            )

            # Log raw response text if available.
            # This helps identify schema mismatches.
            try:
                raw_text = getattr(
                    response,
                    "text",
                    None,
                )

                if raw_text:
                    print(
                        "[SUMMARIZER RAW RESPONSE]",
                        flush=True,
                    )

                    print(
                        raw_text[:2000],
                        flush=True,
                    )

                else:
                    print(
                        "[SUMMARIZER] "
                        "No response.text available.",
                        flush=True,
                    )

            except Exception as raw_error:

                print(
                    "[SUMMARIZER] "
                    "Could not inspect raw response.",
                    flush=True,
                )

                print(
                    f"[SUMMARIZER] "
                    f"{type(raw_error).__name__}: "
                    f"{raw_error}",
                    flush=True,
                )

            return build_fallback_response(
                "Synthesis response was received but "
                "could not be parsed."
            )

        # ==================================================
        # 6. Exception handling
        # ==================================================

        except Exception as e:

            error_text = str(e)
            error_lower = error_text.lower()

            print(
                "\n"
                + "!" * 70,
                flush=True,
            )

            print(
                "[SUMMARIZER CORE ERROR]",
                flush=True,
            )

            print(
                f"Attempt: "
                f"{attempt_number}/{MAX_RETRIES}",
                flush=True,
            )

            print(
                f"Exception type: "
                f"{type(e).__name__}",
                flush=True,
            )

            print(
                f"Exception repr: "
                f"{repr(e)}",
                flush=True,
            )

            print(
                f"Exception message: "
                f"{error_text}",
                flush=True,
            )

            print(
                f"Query: {query}",
                flush=True,
            )

            print(
                f"Intent: {intent}",
                flush=True,
            )

            print(
                f"Source canvas length: "
                f"{len(source_canvas)}",
                flush=True,
            )

            print(
                "Full traceback:",
                flush=True,
            )

            traceback.print_exc()

            print(
                "!" * 70,
                flush=True,
            )

            # ==================================================
            # Identify likely error category
            # ==================================================

            is_rate_limit = (
                "429" in error_text
                or "resource_exhausted" in error_lower
                or "resource exhausted" in error_lower
                or "rate limit" in error_lower
                or "quota" in error_lower
            )

            is_service_unavailable = (
                "503" in error_text
                or "unavailable" in error_lower
            )

            is_model_not_found = (
                "404" in error_text
                or "not found" in error_lower
                or "model not found" in error_lower
            )

            is_auth_error = (
                "401" in error_text
                or "403" in error_text
                or "api key" in error_lower
                or "permission denied" in error_lower
                or "unauthenticated" in error_lower
            )

            # --------------------------------------------------
            # Log diagnosis
            # --------------------------------------------------

            if is_rate_limit:

                print(
                    "[SUMMARIZER DIAGNOSIS] "
                    "Gemini rate limit or quota exhaustion "
                    "detected.",
                    flush=True,
                )

            elif is_service_unavailable:

                print(
                    "[SUMMARIZER DIAGNOSIS] "
                    "Gemini service is temporarily "
                    "unavailable.",
                    flush=True,
                )

            elif is_model_not_found:

                print(
                    "[SUMMARIZER DIAGNOSIS] "
                    "The configured Gemini model may not "
                    "exist or may not be available to this "
                    "API account.",
                    flush=True,
                )

                print(
                    f"[SUMMARIZER DIAGNOSIS] "
                    f"Current model: {GEMINI_MODEL}",
                    flush=True,
                )

            elif is_auth_error:

                print(
                    "[SUMMARIZER DIAGNOSIS] "
                    "Gemini authentication or API-key "
                    "permission problem detected.",
                    flush=True,
                )

            else:

                print(
                    "[SUMMARIZER DIAGNOSIS] "
                    "Unexpected Gemini error. "
                    "Inspect the exception and traceback "
                    "above.",
                    flush=True,
                )

            # ==================================================
            # Retry only temporary errors
            # ==================================================

            temporary_error = (
                is_rate_limit
                or is_service_unavailable
            )

            if (
                temporary_error
                and attempt < MAX_RETRIES - 1
            ):

                wait_time = (
                    attempt_number * 2
                )

                print(
                    f"[SUMMARIZER RETRY] "
                    f"Waiting {wait_time} seconds before "
                    f"retrying...",
                    flush=True,
                )

                time.sleep(
                    wait_time
                )

                continue

            # ==================================================
            # Permanent failure
            # ==================================================

            print(
                "[SUMMARIZER FAILURE] "
                "Synthesis failed permanently.",
                flush=True,
            )

            if is_rate_limit:

                return build_fallback_response(
                    "Gemini API rate limit or quota has "
                    "been reached. Please try again later."
                )

            if is_service_unavailable:

                return build_fallback_response(
                    "Gemini is temporarily unavailable. "
                    "Please try again shortly."
                )

            if is_model_not_found:

                return build_fallback_response(
                    "The configured Gemini model is "
                    "currently unavailable."
                )

            if is_auth_error:

                return build_fallback_response(
                    "Gemini API authentication failed."
                )

            return build_fallback_response(
                "Synthesis failed due to an unexpected "
                "Gemini API error."
            )

    # ======================================================
    # 7. Final safety fallback
    # ======================================================

    print(
        "[SUMMARIZER FAILURE] "
        "Maximum retry count reached.",
        flush=True,
    )

    return build_fallback_response(
        "Synthesis could not be completed after "
        "multiple attempts."
    )
