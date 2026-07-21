"""
Academic research aggregation retriever.

Runs arXiv and OpenAlex retrieval concurrently and returns
the results in a common response structure.
"""

import concurrent.futures

from app.retrievers.arxiv import handle_arxiv_query
from app.retrievers.openalex import handle_openalex_query


def handle_academic_research(
    query: str,
    max_results_per_source: int = 5
) -> dict:

    if not query or not query.strip():

        return {
            "status": "error",
            "source": "academic_research",
            "error": "Empty academic research query.",
        }

    retrievers = {
        "arxiv": handle_arxiv_query,
        "openalex": handle_openalex_query,
    }

    source_results = {}

    with concurrent.futures.ThreadPoolExecutor(
        max_workers=len(retrievers)
    ) as executor:

        future_to_source = {
            executor.submit(
                retriever,
                query,
                max_results_per_source
            ): source

            for source, retriever in retrievers.items()
        }

        for future in concurrent.futures.as_completed(
            future_to_source
        ):

            source = future_to_source[future]

            try:

                source_results[source] = future.result()

            except Exception as exc:

                source_results[source] = {
                    "status": "error",
                    "source": source,
                    "error": str(exc),
                }

    combined_results = []

    for source in [
        "arxiv",
        "openalex"
    ]:

        result = source_results.get(source, {})

        if result.get("status") == "success":

            combined_results.extend(
                result.get("results", [])
            )

    successful_sources = [
        source
        for source, result in source_results.items()
        if result.get("status") == "success"
    ]

    failed_sources = [
        source
        for source, result in source_results.items()
        if result.get("status") != "success"
    ]

    return {
        "status": (
            "success"
            if successful_sources
            else "error"
        ),

        "source": "academic_research",

        "display_payload": {
            "title": "Academic Research",
            "main_text": (
                f"Retrieved {len(combined_results)} academic "
                f"results from "
                f"{', '.join(successful_sources) or 'no sources'}."
            ),
            "results": combined_results,
        },

        "results": combined_results,

        "sources": source_results,

        "metadata": {
            "total_results": len(combined_results),
            "successful_sources": successful_sources,
            "failed_sources": failed_sources,
        },
    }