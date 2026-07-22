from typing import Any, Dict, List
from urllib.parse import quote

import httpx


CLINICAL_TRIALS_URL = (
    "https://clinicaltrials.gov/api/v2/studies"
)

DEFAULT_LIMIT = 5
TIMEOUT = 15.0


def _safe_dict(
    value: Any,
) -> Dict[str, Any]:
    if isinstance(value, dict):
        return value
    return {}


def _safe_list(
    value: Any,
) -> List[Any]:
    if isinstance(value, list):
        return value
    return []


def _extract_interventions(
    protocol: Dict[str, Any],
) -> List[Dict[str, str]]:
    module = _safe_dict(
        protocol.get("armsInterventionsModule")
    )

    interventions = []

    for intervention in _safe_list(
        module.get("interventions")
    ):
        if not isinstance(intervention, dict):
            continue

        name = intervention.get("name")
        intervention_type = intervention.get("type")

        if not name:
            continue

        interventions.append(
            {
                "name": name,
                "type": intervention_type or "OTHER",
            }
        )

    return interventions


def _extract_locations(
    protocol: Dict[str, Any],
    max_locations: int = 5,
) -> List[Dict[str, Any]]:
    module = _safe_dict(
        protocol.get("contactsLocationsModule")
    )

    locations = []

    for location in _safe_list(
        module.get("locations")
    )[:max_locations]:
        if not isinstance(location, dict):
            continue

        locations.append(
            {
                "facility": location.get("facility"),
                "city": location.get("city"),
                "state": location.get("state"),
                "country": location.get("country"),
            }
        )

    return locations


def _extract_sponsor(
    protocol: Dict[str, Any],
) -> str | None:
    module = _safe_dict(
        protocol.get("sponsorCollaboratorsModule")
    )

    lead_sponsor = _safe_dict(
        module.get("leadSponsor")
    )

    return lead_sponsor.get("name")


def _extract_enrollment(
    protocol: Dict[str, Any],
) -> Any:
    design_module = _safe_dict(
        protocol.get("designModule")
    )

    enrollment_info = _safe_dict(
        design_module.get("enrollmentInfo")
    )

    return enrollment_info.get("count")


def _extract_dates(
    protocol: Dict[str, Any],
) -> Dict[str, Any]:
    status_module = _safe_dict(
        protocol.get("statusModule")
    )

    start = _safe_dict(
        status_module.get("startDateStruct")
    )

    completion = _safe_dict(
        status_module.get("completionDateStruct")
    )

    return {
        "start_date": start.get("date"),
        "completion_date": completion.get("date"),
    }


def _normalize_study(
    study: Dict[str, Any],
) -> Dict[str, Any]:
    protocol = _safe_dict(
        study.get("protocolSection")
    )

    identification = _safe_dict(
        protocol.get("identificationModule")
    )

    status_module = _safe_dict(
        protocol.get("statusModule")
    )

    conditions_module = _safe_dict(
        protocol.get("conditionsModule")
    )

    design_module = _safe_dict(
        protocol.get("designModule")
    )

    description_module = _safe_dict(
        protocol.get("descriptionModule")
    )

    nct_id = identification.get("nctId")

    phases = _safe_list(
        design_module.get("phases")
    )

    dates = _extract_dates(protocol)

    return {
        "source": "clinical_trials",
        "result_type": "clinical_trial",
        "nct_id": nct_id,
        "title": (
            identification.get("briefTitle")
            or identification.get("officialTitle")
            or "Untitled clinical study"
        ),
        "official_title": (
            identification.get("officialTitle")
        ),
        "summary": (
            description_module.get("briefSummary")
        ),
        "status": (
            status_module.get("overallStatus")
        ),
        "study_type": (
            design_module.get("studyType")
        ),
        "phases": phases,
        "conditions": _safe_list(
            conditions_module.get("conditions")
        ),
        "interventions": (
            _extract_interventions(protocol)
        ),
        "sponsor": _extract_sponsor(protocol),
        "enrollment": (
            _extract_enrollment(protocol)
        ),
        "locations": (
            _extract_locations(protocol)
        ),
        "start_date": dates["start_date"],
        "completion_date": (
            dates["completion_date"]
        ),
        "url": (
            f"https://clinicaltrials.gov/study/"
            f"{quote(str(nct_id))}"
            if nct_id
            else None
        ),
    }


async def search_clinical_trials(
    query: str,
    limit: int = DEFAULT_LIMIT,
) -> Dict[str, Any]:
    """
    Search ClinicalTrials.gov API v2 for
    clinical studies matching a query.
    """

    query = query.strip()

    if not query:
        return {
            "status": "error",
            "source": "clinical_trials",
            "query": query,
            "results": [],
            "count": 0,
            "error": "Query cannot be empty.",
        }

    limit = max(1, min(limit, 25))

    params = {
        "query.term": query,
        "pageSize": limit,
        "format": "json",
    }

    try:
        async with httpx.AsyncClient(
            timeout=TIMEOUT,
            follow_redirects=True,
        ) as client:
            response = await client.get(
                CLINICAL_TRIALS_URL,
                params=params,
            )

            response.raise_for_status()

        data = response.json()

        raw_studies = data.get("studies", [])

        results: List[Dict[str, Any]] = []

        for study in raw_studies:
            try:
                results.append(
                    _normalize_study(study)
                )
            except Exception as exc:
                print(
                    "[CLINICAL TRIALS] "
                    "Failed to normalize study:",
                    exc,
                )

        return {
            "status": "success",
            "source": "clinical_trials",
            "query": query,
            "results": results,
            "count": len(results),
            "total_results": data.get(
                "totalCount"
            ),
            "next_page_token": data.get(
                "nextPageToken"
            ),
        }

    except httpx.TimeoutException:
        print(
            "[CLINICAL TRIALS] Request timed out."
        )

        return {
            "status": "error",
            "source": "clinical_trials",
            "query": query,
            "results": [],
            "count": 0,
            "error": (
                "ClinicalTrials.gov request "
                "timed out."
            ),
        }

    except httpx.HTTPStatusError as exc:
        print(
            "[CLINICAL TRIALS] HTTP error:",
            exc.response.status_code,
        )

        return {
            "status": "error",
            "source": "clinical_trials",
            "query": query,
            "results": [],
            "count": 0,
            "error": (
                "ClinicalTrials.gov returned HTTP "
                f"{exc.response.status_code}."
            ),
        }

    except Exception as exc:
        print(
            "[CLINICAL TRIALS] Unexpected error:",
            exc,
        )

        return {
            "status": "error",
            "source": "clinical_trials",
            "query": query,
            "results": [],
            "count": 0,
            "error": str(exc),
        }


async def handle_clinical_trials_query(
    query: str,
    limit: int = DEFAULT_LIMIT,
) -> Dict[str, Any]:
    return await search_clinical_trials(
        query=query,
        limit=limit,
    )