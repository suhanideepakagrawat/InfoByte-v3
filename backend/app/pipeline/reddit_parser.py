"""
reddit_parser.py

Formats raw Reddit comments and bodies scraped by Playwright into a 
unified, readable text block for the summarizer.
"""
import re

def format_reddit_threads(threads: list) -> str:
    """
    Combines multiple Reddit threads into a single, structured text entity.
    Uses clear delimiters so downstream AI models can differentiate between topics.
    """
    combined_content = ""
    
    for i, thread in enumerate(threads, 1):
        title = thread.get("title", "Unknown Title")
        combined_content += f"=== THREAD {i}: {title} ===\n"
        
        body = thread.get("body", "")
        if body:
            clean_body = re.sub(r"\s+", " ", body).strip()
            if clean_body:
                combined_content += f"ORIGINAL POST:\n{clean_body}\n\n"
            
        comments = thread.get("comments", [])
        printable_comments = []
        for comment in comments:
            text = re.sub(r"\s+", " ", comment.get("text", "")).strip()
            if not text:
                # Skip empty/deleted comment bodies instead of printing a blank line
                continue
            author = comment.get("author", "[unknown]")
            printable_comments.append((author, text))

        if printable_comments:
            combined_content += "TOP COMMENTS:\n"
            for j, (author, text) in enumerate(printable_comments, 1):
                combined_content += f"{j}. ({author}): {text}\n"
                
        combined_content += "\n"
        
    return combined_content.strip()