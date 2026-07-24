"""
main.py
FastAPI gateway server for InfoByte v3.
"""

from fastapi import (
    FastAPI,
    HTTPException
)

from fastapi.middleware.cors import (
    CORSMiddleware
)

from pydantic import BaseModel

from typing import (
    Optional,
    Dict,
    Any
)

import csv
from datetime import datetime
import os

from dotenv import load_dotenv

load_dotenv()


from app.router import route_query

from app.api.classifier import (
    intent_classifier
)

from app.pipeline.summarizer import (
    generate_engine_synthesis
)


# ----------------------------------------------------------
# Retrievers
# ----------------------------------------------------------

from app.retrievers.oracle import (
    handle_oracle_query
)

from app.retrievers.weather import (
    handle_weather_query
)

from app.retrievers.wikipedia import (
    handle_wiki_query
)

from app.retrievers.news import (
    handle_news_query
)

from app.retrievers.stackoverflow import (
    handle_stackoverflow_query
)

from app.retrievers.reddit import (
    handle_reddit_query
)

from app.retrievers.google_search import (
    handle_google_search
)

from app.retrievers.academic_research import (
    handle_academic_research
)

from app.retrievers.medical_research import (
    handle_medical_research
)

from app.retrievers.medicine import (
    handle_medicine_query
)

from app.retrievers.nutrition import (
    retrieve_nutrition
)


# ----------------------------------------------------------
# Supabase Initialization
# ----------------------------------------------------------

try:

    from supabase import (
        create_client,
        Client
    )

    SUPABASE_AVAILABLE = True

except ImportError:

    SUPABASE_AVAILABLE = False


SUPABASE_URL = os.environ.get(
    "SUPABASE_URL"
)

SUPABASE_KEY = os.environ.get(
    "SUPABASE_KEY"
)


supabase: Optional[
    "Client"
] = None


if (
    SUPABASE_AVAILABLE
    and SUPABASE_URL
    and SUPABASE_KEY
):

    supabase = create_client(
        SUPABASE_URL,
        SUPABASE_KEY
    )


# ----------------------------------------------------------
# FastAPI Application
# ----------------------------------------------------------

app = FastAPI(
    title="InfoByte v3 API Engine"
)


app.add_middleware(

    CORSMiddleware,

    allow_origins=["*"],

    allow_credentials=True,

    allow_methods=["*"],

    allow_headers=["*"]
)


# ----------------------------------------------------------
# Utility
# ----------------------------------------------------------

def _inject_intent(
    response: dict,
    intent: str
) -> dict:

    if "intent" not in response:

        response[
            "intent"
        ] = intent

    return response


# ----------------------------------------------------------
# Request Models
# ----------------------------------------------------------

class ClassificationRequest(
    BaseModel
):

    query: str


class QueryRequest(
    BaseModel
):

    query: str

    confirmed_intent: (
        Optional[str]
    ) = None

    skip_synthesis: bool = False


class LogRequest(
    BaseModel
):

    query: str

    intent: str

    confidence: str = "1.0"


class SynthesisRequest(
    BaseModel
):

    query: str

    intent: str

    results_dict: (
        Dict[str, Any]
    )


# ----------------------------------------------------------
# Classification Endpoint
# ----------------------------------------------------------

@app.post(
    "/api/classify"
)
def direct_intent_classification(
    payload: ClassificationRequest
):

    try:

        predictions = (
            intent_classifier
            .predict_intents(
                payload.query
                .lower()
                .strip()
            )
        )

        if not predictions:

            raise HTTPException(
                status_code=400,
                detail=(
                    "Classifier returned "
                    "no predictions."
                )
            )

        return {

            "predictions":
                predictions,

            "top_intent":
                predictions[0][
                    "label"
                ],

            "all_intents": [

                prediction[
                    "label"
                ]

                for prediction
                in predictions
            ]
        }

    except HTTPException:

        raise

    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


# ----------------------------------------------------------
# Initial Quick Summary
# ----------------------------------------------------------

@app.post(
    "/api/quick-summary"
)
def quick_summary_endpoint(
    payload: ClassificationRequest
):

    try:

        # Initial summary is grounded in the
        # Google Search retriever output.
        search_data = (
            handle_google_search(
                payload.query
            )
        )

        ai_synthesis = (
            generate_engine_synthesis(

                payload.query
                .lower()
                .strip(),

                "general",

                {
                    "google_search":
                        search_data
                }
            )
        )

        return {

            "summary":
                ai_synthesis
                .factual_summary
        }

    except Exception as e:

        print(
            "[QUICK SUMMARY ERROR] "
            f"{e}"
        )

        return {

            "summary":
                (
                    "The initial AI summary "
                    "is temporarily unavailable."
                )
        }


# ----------------------------------------------------------
# Correction Logging
# ----------------------------------------------------------

@app.post(
    "/api/log-correction"
)
def log_user_correction(
    payload: LogRequest
):

    try:

        timestamp = (
            datetime
            .now()
            .isoformat()
        )

        if supabase:

            supabase.table(
                "intent_dataset_augmented"
            ).insert(
                {
                    "query":
                        payload.query,

                    "intent":
                        payload.intent
                }
            ).execute()

            supabase.table(
                "all_queries_log"
            ).insert(
                {
                    "timestamp":
                        timestamp,

                    "query":
                        payload.query,

                    "intent":
                        payload.intent,

                    "confidence":
                        float(
                            payload.confidence
                        )
                }
            ).execute()

        else:

            base_dir = (
                os.path.dirname(
                    os.path.dirname(
                        os.path.dirname(
                            os.path.abspath(
                                __file__
                            )
                        )
                    )
                )
            )

            master_dataset = (
                os.path.join(
                    base_dir,
                    "nlp",
                    "datasets",
                    "intent_dataset_augmented.csv"
                )
            )

            temp_log = (
                os.path.join(
                    base_dir,
                    "backend",
                    "all_queries_log.csv"
                )
            )

            with open(
                master_dataset,
                mode="a",
                encoding="utf-8",
                newline=""
            ) as f:

                csv.writer(
                    f
                ).writerow(
                    [
                        payload.query,
                        payload.intent
                    ]
                )

            with open(
                temp_log,
                mode="a",
                encoding="utf-8",
                newline=""
            ) as f:

                csv.writer(
                    f
                ).writerow(
                    [
                        timestamp,
                        payload.query,
                        payload.intent,
                        payload.confidence
                    ]
                )

        return {
            "status":
                "success"
        }

    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


# ----------------------------------------------------------
# Smart Router
# ----------------------------------------------------------

@app.post(
    "/api/query"
)
def smart_router_endpoint(
    payload: QueryRequest
):

    try:

        return route_query(

            payload.query,

            confirmed_intent=(
                payload
                .confirmed_intent
            ),

            skip_synthesis=(
                payload
                .skip_synthesis
            )
        )

    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


# ----------------------------------------------------------
# Standalone Bounded Synthesis
# ----------------------------------------------------------

@app.post(
    "/api/synthesize"
)
def synthesize_endpoint(
    payload: SynthesisRequest
):

    try:

        ai_synthesis = (
            generate_engine_synthesis(

                payload.query
                .lower()
                .strip(),

                payload.intent,

                payload.results_dict
            )
        )

        return {

            "factual_summary":
                ai_synthesis
                .factual_summary,

            "llm_overview":
                ai_synthesis
                .llm_overview
        }

    except Exception as e:

        print(
            "[SYNTHESIS ERROR] "
            f"{e}"
        )

        return {

            "factual_summary":
                (
                    "The AI synthesis engine "
                    "is temporarily unavailable. "
                    "Please review the retrieved "
                    "source results."
                ),

            "llm_overview":
                (
                    "Source retrieval may have "
                    "completed successfully, but "
                    "the synthesis request failed."
                )
        }


# ----------------------------------------------------------
# Direct Retriever Endpoints
# ----------------------------------------------------------

@app.get(
    "/api/retriever/oracle"
)
def direct_oracle(
    q: str
):

    return _inject_intent(
        handle_oracle_query(q),
        "technical_oracle"
    )


@app.get(
    "/api/retriever/weather"
)
def direct_weather(
    q: str
):

    return _inject_intent(
        handle_weather_query(q),
        "weather"
    )


@app.get(
    "/api/retriever/stackoverflow"
)
def direct_stack(
    q: str
):

    return _inject_intent(
        handle_stackoverflow_query(q),
        "technical_code"
    )


@app.get(
    "/api/retriever/reddit"
)
def direct_reddit(

    q: str,

    intent: str = (
        "discussion_social"
    )
):

    return _inject_intent(

        handle_reddit_query(
            q,
            intent
        ),

        intent
    )


@app.get(
    "/api/retriever/wiki"
)
def direct_wiki(

    q: str,

    url: Optional[str] = None
):

    return _inject_intent(

        handle_wiki_query(
            q,
            url=url
        ),

        "general_wiki"
    )


@app.get(
    "/api/retriever/news"
)
def direct_news(
    q: str
):

    return _inject_intent(
        handle_news_query(q),
        "discussion_social"
    )


@app.get(
    "/api/retriever/google_search"
)
def direct_google(
    q: str
):

    return _inject_intent(
        handle_google_search(q),
        "google_search"
    )


@app.get(
    "/api/retriever/academic_research"
)
def direct_academic_research(
    q: str
):

    return _inject_intent(
        handle_academic_research(q),
        "academic_research"
    )


@app.get(
    "/api/retriever/medical_research"
)
async def direct_medical_research(
    q: str
):

    result = (
        await handle_medical_research(
            q
        )
    )

    return _inject_intent(
        result,
        "medical_research"
    )


@app.get(
    "/api/retriever/medicine"
)
async def direct_medicine(
    q: str
):

    result = (
        await handle_medicine_query(
            q
        )
    )

    return _inject_intent(
        result,
        "medicine"
    )


@app.get(
    "/api/retriever/nutrition"
)
async def direct_nutrition(

    q: str,

    fdc_id: Optional[int] = None,

    grams: Optional[
        float
    ] = None
):

    result = (
        await retrieve_nutrition(

            q,

            fdc_id=fdc_id,

            requested_grams=grams
        )
    )

    return _inject_intent(
        result,
        "food_nutrition"
    )