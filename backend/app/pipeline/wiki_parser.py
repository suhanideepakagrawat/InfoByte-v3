import re
from bs4 import BeautifulSoup

def parse_article(html: str) -> dict:
    """
    Parses raw Wikipedia HTML into structured text and headings.
    """
    soup = BeautifulSoup(html, 'html.parser')
    
    # Extract the main title
    title_tag = soup.find('h1', {'id': 'firstHeading'})
    title = title_tag.text if title_tag else "Unknown Title"
    
    # Isolate the main content div to avoid scraping sidebars and nav menus
    content_div = soup.find('div', {'id': 'mw-content-text'})
    
    paragraphs = []
    headings = []
    
    if content_div:
        # Iterate through paragraphs and headings
        for element in content_div.find_all(['p', 'h2', 'h3']):
            if element.name == 'p':
                text = element.text.strip()
                if text:
                    paragraphs.append(text)
            elif element.name in ['h2', 'h3']:
                # Wikipedia injects edit buttons into headings. We must remove them first.
                for edit_btn in element.find_all('span', class_='mw-editsection'):
                    edit_btn.decompose()
                
                # Extract the clean text directly from the heading tag
                heading_text = element.text.strip()
                if heading_text:
                    headings.append(heading_text)

    return {
        "title": title,
        "paragraphs": paragraphs,
        "headings": headings
    }

def clean_article(parsed_data: dict) -> dict:
    """
    Cleans the parsed data by removing citation brackets and formatting the text.
    """
    raw_text = "\n".join(parsed_data["paragraphs"])
    
    # Remove citation reference numbers (e.g., [1], [2])
    # Replace the current regex lines in clean_article with this:
    clean_text = re.sub(r'\[[a-zA-Z0-9\s]+\]', '', raw_text)
    clean_text = re.sub(r'\[citation needed\]', '', clean_text)
    
    # Normalize whitespace
    clean_text = re.sub(r'\s+', ' ', clean_text).strip()
    
    return {
        "title": parsed_data["title"],
        "full_text": clean_text,
        "headings": parsed_data["headings"],
        "sections": parsed_data["headings"] 
    }