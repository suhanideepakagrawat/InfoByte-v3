"""
stackoverflow_parser.py
Cleans raw HTML bodies into formatted text.
"""
from bs4 import BeautifulSoup
import re

def clean_stackoverflow_body(html: str) -> str:
    """Strips HTML while preserving structure and code block readability."""
    if not html:
        return ""
    
    soup = BeautifulSoup(html, "html.parser")
    
    # Preserve code block markers (pre tags)
    for pre in soup.find_all("pre"):
        pre.insert(0, "```\n")
        pre.append("\n```")
    
    # Extract text with newlines to keep blocks separated
    text = soup.get_text(separator="\n")
    
    # Normalize excessive newlines
    clean_text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return clean_text