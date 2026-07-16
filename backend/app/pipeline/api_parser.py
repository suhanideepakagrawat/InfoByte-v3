"""
api_parser.py
Centralized parser for cleaning JSON API responses.
"""
import re

def clean_json_response(data: dict, fields_to_extract: list) -> str:
    """Concatenates specific fields from a JSON object into a clean text string."""
    extracted_parts = []
    for field in fields_to_extract:
        val = data.get(field)
        if val:
            # Strip HTML tags if present in descriptions
            clean_val = re.sub(r'<[^>]+>', '', str(val))
            extracted_parts.append(f"{field.upper()}: {clean_val}")
    
    return "\n\n".join(extracted_parts).strip()