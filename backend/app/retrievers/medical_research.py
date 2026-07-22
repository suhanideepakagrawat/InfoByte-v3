import asyncio
from typing import Any, Dict, List

from app.retrievers.europe_pmc import (
    handle_europe_pmc_query,
)
from app.retrievers.clinical_trials import (
    handle_clinical_trials_query,
)


DEFAULT_RESULTS_PER_SOURCE = 5


async def handle_medical_research(
    query: str,
    limit: int = DEFAULT_RESULTS_PER_SOURCE,
) -> Dict[str, Any]:
    """
    Aggregate medical research information from:

    1. Europe PMC
       - Biomedical and medical publications

    2. ClinicalTrials.gov
       - Registered clinical studies
    """

    query = query.strip()

    if not query:
        return {
            "status": "error",
            "source": "medical_research",
            "query": query,
            "results": [],
            "successful_sources": [],
            "failed_sources": [
                "europe_pmc",
                "clinical_trials",
            ],
            "error": "Query cannot be empty.",
        }

    europe_pmc_task = (
        handle_europe_pmc_query(
            query=query,
            limit=limit,
        )
    )

    clinical_trials_task = (
        handle_clinical_trials_query(
            query=query,
            limit=limit,
        )
    )

    europe_pmc_response, clinical_trials_response = (
        await asyncio.gather(
            europe_pmc_task,
            clinical_trials_task,
            return_exceptions=True,
        )
    )

    source_responses: Dict[str, Any] = {
        "europe_pmc": europe_pmc_response,
        "clinical_trials": clinical_trials_response,
    }

    successful_sources: List[str] = []
    failed_sources: List[str] = []

    europe_pmc_results: List[Dict[str, Any]] = []
    clinical_trials_results: List[Dict[str, Any]] = []

    source_errors: Dict[str, str] = {}

    for source_name, response in source_responses.items():

        if isinstance(response, Exception):
            failed_sources.append(source_name)

            source_errors[source_name] = str(
                response
            )

            print(
                f"[MEDICAL RESEARCH] "
                f"{source_name} failed:",
                response,
            )

            continue

        if not isinstance(response, dict):
            failed_sources.append(source_name)

            source_errors[source_name] = (
                "Invalid source response."
            )

            continue

        if response.get("status") == "success":
            successful_sources.append(
                source_name
            )

            results = response.get(
                "results",
                [],
            )

            if source_name == "europe_pmc":
                europe_pmc_results = results

            elif source_name == "clinical_trials":
                clinical_trials_results = results

        else:
            failed_sources.append(
                source_name
            )

            source_errors[source_name] = (
                response.get("error")
                or "Unknown source error."
            )

    combined_results = (
        europe_pmc_results
        + clinical_trials_results
    )

    if successful_sources:
        status = "success"
    else:
        status = "error"

    return {
        "status": status,
        "source": "medical_research",
        "query": query,

        "display_payload": {
            "title": "Medical Research",
            "main_text": (
                "Medical literature and clinical "
                "study results retrieved from "
                "Europe PMC and ClinicalTrials.gov."
            ),

            "sections": {
                "europe_pmc": {
                    "title": (
                        "Biomedical Research"
                    ),
                    "source_name": "Europe PMC",
                    "result_type": (
                        "medical_publication"
                    ),
                    "count": len(
                        europe_pmc_results
                    ),
                    "results": (
                        europe_pmc_results
                    ),
                },

                "clinical_trials": {
                    "title": (
                        "Clinical Trials"
                    ),
                    "source_name": (
                        "ClinicalTrials.gov"
                    ),
                    "result_type": (
                        "clinical_trial"
                    ),
                    "count": len(
                        clinical_trials_results
                    ),
                    "results": (
                        clinical_trials_results
                    ),
                },
            },

            "results": combined_results,
        },

        "results": combined_results,

        "source_results": {
            "europe_pmc": (
                europe_pmc_results
            ),
            "clinical_trials": (
                clinical_trials_results
            ),
        },

        "successful_sources": (
            successful_sources
        ),

        "failed_sources": (
            failed_sources
        ),

        "source_errors": (
            source_errors
        ),

        "total_results": len(
            combined_results
        ),
    }