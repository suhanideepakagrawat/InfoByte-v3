"""
arXiv academic paper retriever.

Retrieves research papers from the public arXiv API.
No API key is required.
"""

import xml.etree.ElementTree as ET
from urllib.parse import urlencode

import requests

from app.pipeline.academic_parser import parse_arxiv_results


ARXIV_API_URL = "https://export.arxiv.org/api/query"

ATOM_NAMESPACE = {
    "atom": "http://www.w3.org/2005/Atom"
}


def _get_text(element, path: str) -> str:
    child = element.find(path, ATOM_NAMESPACE)

    if child is None or child.text is None:
        return ""

    return child.text.strip()


def handle_arxiv_query(
    query: str,
    max_results: int = 5
) -> dict:

    if not query or not query.strip():
        return {
            "status": "error",
            "source": "arxiv",
            "error": "Empty academic research query."
        }

    max_results = max(1, min(max_results, 10))

    params = {
        "search_query": f"all:{query.strip()}",
        "start": 0,
        "max_results": max_results,
        "sortBy": "relevance",
        "sortOrder": "descending",
    }

    url = f"{ARXIV_API_URL}?{urlencode(params)}"

    try:

        response = requests.get(
            url,
            timeout=20,
            headers={
                "User-Agent": "InfoByte/1.0 Academic Research Engine"
            },
        )

        response.raise_for_status()

        root = ET.fromstring(response.content)

        papers = []

        for entry in root.findall("atom:entry", ATOM_NAMESPACE):

            paper_id = _get_text(
                entry,
                "atom:id"
            )

            title = _get_text(
                entry,
                "atom:title"
            )

            abstract = _get_text(
                entry,
                "atom:summary"
            )

            published = _get_text(
                entry,
                "atom:published"
            )

            updated = _get_text(
                entry,
                "atom:updated"
            )

            authors = []

            for author in entry.findall(
                "atom:author",
                ATOM_NAMESPACE
            ):

                name = _get_text(
                    author,
                    "atom:name"
                )

                if name:
                    authors.append(name)

            categories = []

            for category in entry.findall(
                "atom:category",
                ATOM_NAMESPACE
            ):

                term = category.attrib.get("term")

                if term:
                    categories.append(term)

            article_url = paper_id

            pdf_url = ""

            for link in entry.findall(
                "atom:link",
                ATOM_NAMESPACE
            ):

                if link.attrib.get("title") == "pdf":
                    pdf_url = link.attrib.get("href", "")
                    break

            papers.append({
                "paper_id": paper_id,
                "title": title,
                "authors": authors,
                "abstract": abstract,
                "published": published,
                "updated": updated,
                "categories": categories,
                "url": article_url,
                "pdf_url": pdf_url,
            })

        parsed_results = parse_arxiv_results(papers)

        return {
            "status": "success",
            "source": "arxiv",
            "display_payload": {
                "title": "arXiv Research Papers",
                "main_text": (
                    f"Found {len(parsed_results)} relevant "
                    f"arXiv papers for '{query}'."
                ),
                "results": parsed_results,
            },
            "results": parsed_results,
        }

    except requests.RequestException as exc:

        return {
            "status": "error",
            "source": "arxiv",
            "error": f"arXiv request failed: {str(exc)}",
        }

    except ET.ParseError as exc:

        return {
            "status": "error",
            "source": "arxiv",
            "error": f"Unable to parse arXiv response: {str(exc)}",
        }

    except Exception as exc:

        return {
            "status": "error",
            "source": "arxiv",
            "error": str(exc),
        }