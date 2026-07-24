"""
dailymed.py

Retriever for DailyMed Structured Product Label information.

DailyMed is used as a supporting official-label source for the
InfoByte medicine retriever.

Matching can be guided by an already-resolved openFDA product using:
- Brand names
- Generic name
- Active ingredients
"""

import re
from typing import Any, Dict, List, Optional
from urllib.parse import quote

import httpx


DAILYMED_DRUG_NAMES_URL = (
    "https://dailymed.nlm.nih.gov/dailymed/services/v2/drugnames.json"
)

DAILYMED_SPLS_URL = (
    "https://dailymed.nlm.nih.gov/dailymed/services/v2/spls.json"
)

DAILYMED_LABEL_BASE_URL = (
    "https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm"
)

REQUEST_TIMEOUT = 20.0


# ============================================================
# NORMALIZATION HELPERS
# ============================================================

def _normalize_name(value: str) -> str:
    """
    Normalize medicine/product names for comparison.
    """
    if not value:
        return ""

    return re.sub(
        r"[^a-z0-9]+",
        " ",
        str(value).lower(),
    ).strip()


def _extract_data_list(
    payload: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """
    Safely extract the `data` list returned by DailyMed.
    """
    data = payload.get("data", [])

    if isinstance(data, list):
        return data

    return []


def _extract_ingredient_names(
    active_ingredients: Optional[List[Any]]
) -> List[str]:
    """
    Extract normalized ingredient names from openFDA's
    active_ingredients structure.
    """
    ingredients = []

    for ingredient in active_ingredients or []:

        if isinstance(ingredient, dict):
            name = ingredient.get("name")

        else:
            name = str(ingredient)

        normalized = _normalize_name(name)

        if normalized and normalized not in ingredients:
            ingredients.append(normalized)

    return ingredients


def _get_candidate_name(
    item: Dict[str, Any]
) -> str:
    """
    Extract the best available display name from
    a DailyMed result.
    """
    return str(
        item.get("title")
        or item.get("drug_name")
        or item.get("name")
        or ""
    ).strip()


# ============================================================
# MATCHING
# ============================================================


def _build_expected_identities(
    query: str,
    brand_names: Optional[List[str]] = None,
    generic_name: Optional[str] = None,
    active_ingredients: Optional[List[Any]] = None,
) -> List[str]:
    """Build normalized trusted identities used to validate a label."""
    values: List[str] = [
        query,
        *(brand_names or []),
    ]

    if generic_name:
        values.append(generic_name)

    values.extend(
        _extract_ingredient_names(
            active_ingredients
        )
    )

    output = []
    seen = set()

    for value in values:
        normalized = _normalize_name(value)

        if normalized and normalized not in seen:
            seen.add(normalized)
            output.append(normalized)

    return output


def _has_identity_match(
    candidate: str,
    query: str,
    brand_names: Optional[List[str]] = None,
    generic_name: Optional[str] = None,
    active_ingredients: Optional[List[Any]] = None,
) -> bool:
    """
    Require a DailyMed candidate title/name to match at least one
    trusted identity. Incidental word overlap is not enough.
    """
    candidate_normalized = _normalize_name(candidate)

    if not candidate_normalized:
        return False

    candidate_tokens = set(
        candidate_normalized.split()
    )

    for expected in _build_expected_identities(
        query=query,
        brand_names=brand_names,
        generic_name=generic_name,
        active_ingredients=active_ingredients,
    ):
        if candidate_normalized == expected:
            return True

        if (
            expected in candidate_normalized
            or candidate_normalized in expected
        ):
            return True

        expected_tokens = set(expected.split())

        if (
            expected_tokens
            and expected_tokens.issubset(
                candidate_tokens
            )
        ):
            return True

    return False


def _calculate_match_score(
    candidate: str,
    query: str,
    brand_names: Optional[List[str]] = None,
    generic_name: Optional[str] = None,
    active_ingredients: Optional[List[Any]] = None,
) -> int:
    """
    Calculate how closely a DailyMed candidate matches
    the medicine resolved by openFDA.

    Priority:
    1. Exact brand match
    2. Exact user query match
    3. Generic-name match
    4. Active-ingredient match
    5. Partial matches
    """

    candidate_normalized = _normalize_name(candidate)
    query_normalized = _normalize_name(query)

    score = 0

    # --------------------------------------------------------
    # User query matching
    # --------------------------------------------------------

    if candidate_normalized == query_normalized:
        score += 150

    elif (
        query_normalized
        and candidate_normalized.startswith(
            query_normalized + " "
        )
    ):
        score += 70

    elif (
        query_normalized
        and query_normalized in candidate_normalized
    ):
        score += 40

    # --------------------------------------------------------
    # Brand matching
    # --------------------------------------------------------

    for brand in brand_names or []:

        brand_normalized = _normalize_name(brand)

        if not brand_normalized:
            continue

        if candidate_normalized == brand_normalized:
            score += 200

        elif brand_normalized in candidate_normalized:
            score += 90

    # --------------------------------------------------------
    # Generic-name matching
    # --------------------------------------------------------

    if generic_name:

        generic_normalized = _normalize_name(
            generic_name
        )

        if candidate_normalized == generic_normalized:
            score += 180

        elif (
            generic_normalized
            and generic_normalized
            in candidate_normalized
        ):
            score += 100

    # --------------------------------------------------------
    # Active ingredient matching
    # --------------------------------------------------------

    ingredient_names = (
        _extract_ingredient_names(
            active_ingredients
        )
    )

    for ingredient in ingredient_names:

        if ingredient in candidate_normalized:
            score += 100

    # --------------------------------------------------------
    # Word overlap
    # --------------------------------------------------------

    query_words = set(
        query_normalized.split()
    )

    candidate_words = set(
        candidate_normalized.split()
    )

    overlap = len(
        query_words.intersection(
            candidate_words
        )
    )

    score += overlap * 10

    return score


def _has_ingredient_conflict(
    candidate: str,
    active_ingredients: Optional[List[Any]],
) -> bool:
    """
    Detect obvious mismatches where openFDA resolved a
    single-ingredient medicine but DailyMed returned a
    combination product containing unrelated ingredients.

    This prevents cases such as:

        Query: Tylenol
        Expected: Acetaminophen

        Wrong DailyMed result:
        Acetaminophen + Diphenhydramine

    The list is intentionally conservative.
    """

    expected_ingredients = (
        _extract_ingredient_names(
            active_ingredients
        )
    )

    # Only apply strict combination filtering when
    # openFDA resolved exactly one active ingredient.
    if len(expected_ingredients) != 1:
        return False

    expected = expected_ingredients[0]

    candidate_normalized = (
        _normalize_name(candidate)
    )

    # If the expected ingredient is not even present,
    # this function does not make assumptions.
    if expected not in candidate_normalized:
        return False

    common_active_ingredients = {
        "acetaminophen",
        "ibuprofen",
        "aspirin",
        "naproxen",
        "diphenhydramine",
        "doxylamine",
        "phenylephrine",
        "pseudoephedrine",
        "dextromethorphan",
        "guaifenesin",
        "chlorpheniramine",
        "caffeine",
    }

    additional_ingredients = {
        ingredient
        for ingredient
        in common_active_ingredients
        if (
            ingredient != expected
            and ingredient
            in candidate_normalized
        )
    }

    return bool(
        additional_ingredients
    )


# ============================================================
# DAILYMED API CALLS
# ============================================================

async def _search_drug_names(
    client: httpx.AsyncClient,
    query: str,
) -> List[Dict[str, Any]]:
    """
    Search DailyMed's drug-name endpoint.
    """

    response = await client.get(
        DAILYMED_DRUG_NAMES_URL,
        params={
            "drug_name": query,
        },
    )

    if response.status_code == 404:
        return []

    response.raise_for_status()

    return _extract_data_list(
        response.json()
    )


async def _search_spls(
    client: httpx.AsyncClient,
    drug_name: str,
) -> List[Dict[str, Any]]:
    """
    Search DailyMed SPL records.
    """

    response = await client.get(
        DAILYMED_SPLS_URL,
        params={
            "drug_name": drug_name,
            "pagesize": 100,
            "page": 1,
        },
    )

    if response.status_code == 404:
        return []

    response.raise_for_status()

    return _extract_data_list(
        response.json()
    )


# ============================================================
# RESULT SELECTION
# ============================================================

def _select_best_drug_name(
    results: List[Dict[str, Any]],
    query: str,
    brand_names: Optional[List[str]] = None,
    generic_name: Optional[str] = None,
    active_ingredients: Optional[List[Any]] = None,
) -> Optional[str]:
    """
    Select the best DailyMed drug-name result.
    """

    if not results:
        return None

    scored_candidates = []

    for item in results:

        name = _get_candidate_name(
            item
        )

        if not name:
            continue

        if not _has_identity_match(
            candidate=name,
            query=query,
            brand_names=brand_names,
            generic_name=generic_name,
            active_ingredients=active_ingredients,
        ):
            continue

        score = _calculate_match_score(
            candidate=name,
            query=query,
            brand_names=brand_names,
            generic_name=generic_name,
            active_ingredients=active_ingredients,
        )

        scored_candidates.append(
            (
                score,
                name,
            )
        )

    if not scored_candidates:
        return None

    scored_candidates.sort(
        key=lambda item: item[0],
        reverse=True,
    )

    return scored_candidates[0][1]


def _select_best_spl(
    results: List[Dict[str, Any]],
    query: str,
    brand_names: Optional[List[str]] = None,
    generic_name: Optional[str] = None,
    active_ingredients: Optional[List[Any]] = None,
) -> Optional[Dict[str, Any]]:
    """
    Select the most appropriate SPL record.

    Obvious ingredient conflicts receive a very large penalty.
    """

    if not results:
        return None

    scored_results = []

    for item in results:

        title = _get_candidate_name(
            item
        )

        if not title:
            continue

        if not _has_identity_match(
            candidate=title,
            query=query,
            brand_names=brand_names,
            generic_name=generic_name,
            active_ingredients=active_ingredients,
        ):
            continue

        score = _calculate_match_score(
            candidate=title,
            query=query,
            brand_names=brand_names,
            generic_name=generic_name,
            active_ingredients=active_ingredients,
        )

        if _has_ingredient_conflict(
            title,
            active_ingredients,
        ):
            score -= 1000

        scored_results.append(
            (
                score,
                item,
            )
        )

    if not scored_results:
        return None

    scored_results.sort(
        key=lambda item: item[0],
        reverse=True,
    )

    best_score, best_result = (
        scored_results[0]
    )

    # Avoid returning a completely unrelated label.
    if best_score <= 0:
        return None

    return best_result


# ============================================================
# NORMALIZE RESULT
# ============================================================

def _normalize_spl(
    spl: Dict[str, Any],
    query: str,
) -> Dict[str, Any]:
    """
    Convert a DailyMed SPL result into InfoByte format.
    """

    set_id = (
        spl.get("setid")
        or spl.get("set_id")
        or spl.get("setId")
    )

    spl_version = (
        spl.get("spl_version")
        or spl.get("version")
    )

    title = (
        spl.get("title")
        or spl.get("drug_name")
        or query
    )

    published_date = (
        spl.get("published_date")
        or spl.get("publication_date")
    )

    source_url = None

    if set_id:

        source_url = (
            f"{DAILYMED_LABEL_BASE_URL}"
            f"?setid={quote(str(set_id))}"
        )

    return {
        "source": "dailymed",

        "result_type":
            "official_drug_label",

        "medicine_name":
            title,

        "label_title":
            title,

        "set_id":
            set_id,

        "spl_version":
            spl_version,

        "published_date":
            published_date,

        "source_name":
            "DailyMed",

        "source_url":
            source_url,

        # This retriever currently resolves the correct DailyMed SPL and
        # returns its official label URL/metadata. Label sections such as
        # PRECAUTIONS are supplied by the openFDA label result in medicine.py.
        "precautions":
            None,

        "raw_metadata":
            spl,
    }


# ============================================================
# MAIN DAILYMED SEARCH
# ============================================================

async def search_dailymed(
    query: str,
    brand_names: Optional[List[str]] = None,
    generic_name: Optional[str] = None,
    active_ingredients: Optional[List[Any]] = None,
) -> Optional[Dict[str, Any]]:
    """
    Search DailyMed using all known identities of the medicine.

    Search terms may include:
    - Original query
    - openFDA brand names
    - openFDA generic name
    - openFDA active ingredients
    """

    query = query.strip()

    if not query:
        return None

    search_terms = []

    # Original query first.
    possible_terms = [
        query,
        *(brand_names or []),
        generic_name,
    ]

    # Add active ingredient names.
    possible_terms.extend(
        _extract_ingredient_names(
            active_ingredients
        )
    )

    # Deduplicate search terms.
    seen_terms = set()

    for term in possible_terms:

        if not term:
            continue

        normalized = _normalize_name(
            term
        )

        if (
            normalized
            and normalized
            not in seen_terms
        ):
            seen_terms.add(
                normalized
            )

            search_terms.append(
                str(term).strip()
            )

    all_spl_results = []

    seen_spls = set()

    async with httpx.AsyncClient(
        timeout=REQUEST_TIMEOUT
    ) as client:

        for search_term in search_terms:

            # ----------------------------------------
            # Resolve DailyMed drug name
            # ----------------------------------------

            try:

                drug_name_results = (
                    await _search_drug_names(
                        client,
                        search_term,
                    )
                )

            except httpx.HTTPStatusError:

                drug_name_results = []

            matched_name = (
                _select_best_drug_name(
                    results=drug_name_results,
                    query=query,
                    brand_names=brand_names,
                    generic_name=generic_name,
                    active_ingredients=active_ingredients,
                )
            )

            if not matched_name:
                matched_name = search_term

            # ----------------------------------------
            # Retrieve SPL candidates
            # ----------------------------------------

            try:

                spl_results = (
                    await _search_spls(
                        client,
                        matched_name,
                    )
                )

            except httpx.HTTPStatusError:

                spl_results = []

            # ----------------------------------------
            # Deduplicate SPL candidates
            # ----------------------------------------

            for spl in spl_results:

                spl_id = (
                    spl.get("setid")
                    or spl.get("set_id")
                    or spl.get("setId")
                )

                if spl_id:

                    if spl_id in seen_spls:
                        continue

                    seen_spls.add(
                        spl_id
                    )

                all_spl_results.append(
                    spl
                )

    if not all_spl_results:
        return None

    # ------------------------------------------------
    # Rank every candidate globally.
    # ------------------------------------------------

    best_spl = _select_best_spl(
        results=all_spl_results,
        query=query,
        brand_names=brand_names,
        generic_name=generic_name,
        active_ingredients=active_ingredients,
    )

    if not best_spl:
        return None

    return _normalize_spl(
        best_spl,
        query,
    )


# ============================================================
# PUBLIC HANDLER
# ============================================================

async def handle_dailymed(
    query: str,
    brand_names: Optional[List[str]] = None,
    generic_name: Optional[str] = None,
    active_ingredients: Optional[List[Any]] = None,
) -> Dict[str, Any]:
    """
    Public DailyMed retriever wrapper.
    """

    try:

        result = await search_dailymed(
            query=query,
            brand_names=brand_names,
            generic_name=generic_name,
            active_ingredients=active_ingredients,
        )

        if not result:

            return {
                "success": False,
                "source": "dailymed",
                "query": query,
                "result": None,
                "error": (
                    "No sufficiently matching "
                    "DailyMed label found."
                ),
            }

        return {
            "success": True,
            "source": "dailymed",
            "query": query,
            "result": result,
            "error": None,
        }

    except Exception as exc:

        return {
            "success": False,
            "source": "dailymed",
            "query": query,
            "result": None,
            "error": str(exc),
        }