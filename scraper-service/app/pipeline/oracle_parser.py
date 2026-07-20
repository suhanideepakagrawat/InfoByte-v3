"""
oracle_parser.py

Cleans raw scraped Oracle Forums text into a structured shape:
Strips known nav/boilerplate lines and executes a best-effort split
between the original post and subsequent community replies.
"""

import re

BOILERPLATE_PATTERNS = [
    r"^Skip to Main Content$", r"^Forums$", r"^Search$", r"^Sign In$", r"^Go back$",
    r"^Dismiss$", r"^Announcement$", r"^For appeals, questions.*Thank you!$",
    r"^Search Scope$", r"^All Domains$", r"^This Domain$", r"^Install App$",
    r"^Toggle$", r"^Please sign in to comment$", r"^Post Details$", r"^Locked Post$",
    r"^New comments cannot be posted to this locked post\.$", r"^Locked on .+$",
    r"^Added on .+$", r"^\d[\d,]* comments?$", r"^\d[\d,]* views?$", r"^\d+\s*-\s*\d+$",
    r"^#[\w-]+(?:,\s*#[\w-]+)*$", r"^\d+ person(?:s)? found this helpful$",
    r"^Test Email$", r"^Share$", r"^Subscribe$", r"^Community Integrity Policy$",
    r"^Built with love\s*using Oracle APEX$",
    r"^SQL & PL/SQL$", r"^Oracle Database Discussions$", r"^Comments$"
]

BOILERPLATE_RE = re.compile("|".join(BOILERPLATE_PATTERNS), flags=re.IGNORECASE)

# Added \s* to handle Playwright's injected DOM indentation before the date
REPLY_HEADER_RE = re.compile(r"\n+(?=[^\n]{2,50}\n+\s*[A-Z][a-z]{2} \d{1,2} \d{4})")

# Used to verify if a chunk starts directly with an author/date header
AUTHOR_DATE_PATTERN = re.compile(r"^[^\n]{2,50}\n+\s*[A-Z][a-z]{2} \d{1,2} \d{4}")


def strip_boilerplate(raw_text: str) -> str:
    """Remove known navigation/announcement lines from the text stream."""
    lines = raw_text.split("\n")
    kept = [ln for ln in lines if not BOILERPLATE_RE.match(ln.strip())]
    text = "\n".join(kept)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def split_question_and_replies(raw_text: str) -> dict:
    """Splits raw flat text into the thread starter question and a list of replies."""
    cleaned = strip_boilerplate(raw_text)
    
    # Drop leading "Comments" marker if it somehow survives the line-by-line strip
    cleaned = re.sub(r"^Comments\n", "", cleaned, flags=re.MULTILINE | re.IGNORECASE)

    chunks = REPLY_HEADER_RE.split(cleaned)
    chunks = [c.strip() for c in chunks if c.strip()]

    if not chunks:
        return {"question": "", "replies": []}
        
    if len(chunks) == 1:
        return {"question": chunks[0], "replies": []}

    # Dynamically determine if chunks[0] is the question or residual title/nav junk
    if AUTHOR_DATE_PATTERN.match(chunks[0]):
        return {
            "question": chunks[0],
            "replies": chunks[1:]
        }
    else:
        return {
            "question": chunks[1],
            "replies": chunks[2:]
        }


def clean_scrape_result(scrape_result: dict) -> dict:
    """Transforms raw scraped playwright strings into structured payloads."""
    raw_posts = scrape_result.get("posts", [])
    raw_text = "\n".join(raw_posts)
    structured = split_question_and_replies(raw_text)

    return {
        "url": scrape_result.get("url"),
        "title": scrape_result.get("title"),
        "question": structured["question"],
        "replies": structured["replies"],
    }

# Add this to the bottom of app/pipeline/oracle_parser.py

def extract_cause_and_action(raw_text: str) -> dict | None:
    """
    Extracts exact Cause and Action text deterministically using Regex.
    Returns a dictionary if successful, or None if the layout doesn't match.
    """
    # Target the text block specifically between "Cause:" and "Action:"
    cause_match = re.search(r'Cause:\s*(.*?)(?=Action:)', raw_text, re.IGNORECASE | re.DOTALL)
    
    # Target the text after "Action:" until the next error code identifier or end of string
    action_match = re.search(r'Action:\s*(.*?)(?=(ORA-\d{4,5}|FRM-\d{4,5}|OSD-\d{4,5}|$))', raw_text, re.IGNORECASE | re.DOTALL)
    
    if cause_match and action_match:
        return {
            "cause": cause_match.group(1).strip(),
            "action": action_match.group(1).strip()
        }
    return None