"""
Normalizes academic research results from arXiv and OpenAlex
into a common structure.
"""

import re
from typing import Any, Dict, List


def clean_text(text: Any) -> str:
    if text is None:
        return ""

    text = str(text)
    return re.sub(r"\s+", " ", text).strip()


def reconstruct_openalex_abstract(
    inverted_index: Dict[str, List[int]] | None
) -> str:
    """
    OpenAlex may provide abstracts as an inverted index:

    {
        "machine": [0],
        "learning": [1]
    }

    Converts this back into:
    "machine learning"
    """

    if not inverted_index:
        return ""

    words = []

    for word, positions in inverted_index.items():
        for position in positions:
            words.append((position, word))

    words.sort(key=lambda item: item[0])

    return clean_text(" ".join(word for _, word in words))


def parse_arxiv_paper(paper: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "source": "arxiv",
        "paper_id": paper.get("paper_id", ""),
        "title": clean_text(paper.get("title")),
        "authors": paper.get("authors", []),
        "abstract": clean_text(paper.get("abstract")),
        "published": paper.get("published", ""),
        "updated": paper.get("updated", ""),
        "categories": paper.get("categories", []),
        "url": paper.get("url", ""),
        "pdf_url": paper.get("pdf_url", ""),
        "citation_count": None,
        "publication_year": (
            paper.get("published", "")[:4]
            if paper.get("published")
            else None
        ),
    }


def parse_openalex_work(work: Dict[str, Any]) -> Dict[str, Any]:
    authors = []

    for authorship in work.get("authorships", []):
        author = authorship.get("author", {})
        name = author.get("display_name")

        if name:
            authors.append(name)

    primary_location = work.get("primary_location") or {}

    landing_page_url = primary_location.get("landing_page_url")

    if not landing_page_url:
        landing_page_url = work.get("doi") or work.get("id", "")

    open_access = work.get("open_access") or {}

    return {
        "source": "openalex",
        "paper_id": work.get("id", ""),
        "title": clean_text(work.get("display_name")),
        "authors": authors,
        "abstract": reconstruct_openalex_abstract(
            work.get("abstract_inverted_index")
        ),
        "published": work.get("publication_date", ""),
        "updated": work.get("updated_date", ""),
        "categories": [
            topic.get("display_name")
            for topic in work.get("topics", [])
            if topic.get("display_name")
        ],
        "url": landing_page_url,
        "pdf_url": open_access.get("oa_url", ""),
        "citation_count": work.get("cited_by_count", 0),
        "publication_year": work.get("publication_year"),
    }


def parse_arxiv_results(
    papers: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    return [parse_arxiv_paper(paper) for paper in papers]


def parse_openalex_results(
    works: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    return [parse_openalex_work(work) for work in works]