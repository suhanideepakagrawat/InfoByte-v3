from typing import Any, Dict, List
from urllib.parse import quote

import httpx


EUROPE_PMC_SEARCH_URL = (
    "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
)

DEFAULT_LIMIT = 5
TIMEOUT = 15.0


def _clean(value: Any, default: Any = None) -> Any:
    if value is None or value == "":
        return default
    return value


def _build_article_url(
    source: str | None,
    article_id: str | None,
    pmid: str | None,
    pmcid: str | None,
) -> str | None:
    if pmcid:
        return f"https://europepmc.org/article/PMC/{quote(str(pmcid))}"

    if source and article_id:
        return (
            f"https://europepmc.org/article/"
            f"{quote(str(source))}/{quote(str(article_id))}"
        )

    if pmid:
        return f"https://europepmc.org/article/MED/{quote(str(pmid))}"

    return None


def _normalize_article(article: Dict[str, Any]) -> Dict[str, Any]:
    source = _clean(article.get("source"))
    article_id = _clean(article.get("id"))
    pmid = _clean(article.get("pmid"))
    pmcid = _clean(article.get("pmcid"))
    doi = _clean(article.get("doi"))

    return {
        "source": "europe_pmc",
        "result_type": "medical_publication",
        "id": article_id or pmid or pmcid,
        "title": _clean(
            article.get("title"),
            "Untitled publication",
        ),
        "authors": _clean(
            article.get("authorString"),
            "Authors not available",
        ),
        "journal": _clean(
            article.get("journalTitle"),
            "Journal not available",
        ),
        "publication_year": _clean(article.get("pubYear")),
        "publication_date": _clean(
            article.get("firstPublicationDate")
            or article.get("journalInfo", {}).get("printPublicationDate")
            if isinstance(article.get("journalInfo"), dict)
            else article.get("firstPublicationDate")
        ),
        "pmid": pmid,
        "pmcid": pmcid,
        "doi": doi,
        "citation_count": article.get("citedByCount", 0),
        "is_open_access": article.get("isOpenAccess") == "Y",
        "has_full_text": article.get("inEPMC") == "Y",
        "url": _build_article_url(
            source=source,
            article_id=article_id,
            pmid=pmid,
            pmcid=pmcid,
        ),
    }


async def search_europe_pmc(
    query: str,
    limit: int = DEFAULT_LIMIT,
) -> Dict[str, Any]:
    """
    Search Europe PMC for biomedical and medical publications.
    """

    query = query.strip()

    if not query:
        return {
            "status": "error",
            "source": "europe_pmc",
            "query": query,
            "results": [],
            "count": 0,
            "error": "Query cannot be empty.",
        }

    limit = max(1, min(limit, 25))

    params = {
        "query": query,
        "format": "json",
        "pageSize": limit,
        "resultType": "core",
    }

    try:
        async with httpx.AsyncClient(
            timeout=TIMEOUT,
            follow_redirects=True,
        ) as client:
            response = await client.get(
                EUROPE_PMC_SEARCH_URL,
                params=params,
            )
            response.raise_for_status()

        data = response.json()

        raw_results = (
            data
            .get("resultList", {})
            .get("result", [])
        )

        results: List[Dict[str, Any]] = []

        for article in raw_results:
            try:
                results.append(_normalize_article(article))
            except Exception as exc:
                print(
                    "[EUROPE PMC] Failed to normalize article:",
                    exc,
                )

        return {
            "status": "success",
            "source": "europe_pmc",
            "query": query,
            "results": results,
            "count": len(results),
            "total_results": data.get("hitCount", len(results)),
        }

    except httpx.TimeoutException:
        print("[EUROPE PMC] Request timed out.")

        return {
            "status": "error",
            "source": "europe_pmc",
            "query": query,
            "results": [],
            "count": 0,
            "error": "Europe PMC request timed out.",
        }

    except httpx.HTTPStatusError as exc:
        print(
            "[EUROPE PMC] HTTP error:",
            exc.response.status_code,
        )

        return {
            "status": "error",
            "source": "europe_pmc",
            "query": query,
            "results": [],
            "count": 0,
            "error": (
                "Europe PMC returned HTTP "
                f"{exc.response.status_code}."
            ),
        }

    except Exception as exc:
        print("[EUROPE PMC] Unexpected error:", exc)

        return {
            "status": "error",
            "source": "europe_pmc",
            "query": query,
            "results": [],
            "count": 0,
            "error": str(exc),
        }


async def handle_europe_pmc_query(
    query: str,
    limit: int = DEFAULT_LIMIT,
) -> Dict[str, Any]:
    return await search_europe_pmc(
        query=query,
        limit=limit,
    )