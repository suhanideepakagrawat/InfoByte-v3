"""
medicine_formatter.py

Formatter module for normalizing raw medicine data and generating structured
medical knowledge cards for frontend rendering. 
Now utilizes Groq LLM to intelligently extract and format bullet points from 
raw FDA paragraphs for maximum readability, with a regex fallback.
"""

import json
import os
import re
from typing import Any, Dict, List, Optional
from groq import Groq


def _clean_text(text: Optional[str]) -> str:
    """Clean HTML tags, markdown, and redundant whitespace."""
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"[\*\_\#]+", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _stringify_list(val: Any) -> str:
    """Safely combine lists of text into a single string for LLM processing."""
    if not val:
        return ""
    if isinstance(val, list):
        return "\n".join(str(v) for v in val if v)
    return str(val)


def _truncate(text: Optional[str], limit: int = 4000) -> str:
    """Cap large FDA blocks to prevent exceeding the Groq token context window."""
    if not text:
        return ""
    text = str(text)
    if len(text) > limit:
        return text[:limit] + "..."
    return text


def _clean_fda_junk_fallback(text: str) -> str:
    """Fallback regex to remove FDA label artifacts if Groq fails."""
    if not text:
        return ""
    text = re.sub(r"\[\s*see\s+[^\]]+\]", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"\(\s*\d+(\.\d+)*\s*\)", " ", text)
    text = re.sub(r"(?:^|\s)Table\s+\d+:?[^\n.]*", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"(?:^|\s)\b\d+(\.\d+)*\s+[A-Z\s\-/]{5,}(?=\s+[A-Z]|$)", " ", text)
    text = re.sub(r"(?:^|\s)\b\d+(\.\d+)*\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*(?=\s|$)", " ", text)
    return text


def _deduplicate_list(items: List[str]) -> List[str]:
    """Deduplicate string items preserving order and ignoring case."""
    seen = set()
    result = []
    for item in items:
        cleaned = _clean_text(item)
        if cleaned:
            key = cleaned.lower()
            if key not in seen:
                seen.add(key)
                result.append(cleaned)
    return result


def _extract_bullet_points_fallback(text: Optional[str]) -> List[str]:
    """Fallback regex converter for when the LLM is unavailable."""
    if not text:
        return []
    
    text = _clean_fda_junk_fallback(text)
    # Safely split without destroying hyphenated words
    lines = re.split(r"(?:\r?\n|•|\*|^\s*-\s+|\s+-\s+|\b\d+\.\s+)", text)
    
    extracted = []
    for line in lines:
        cleaned = _clean_text(line)
        # Skip statistical tables
        if re.search(r"(\d+\.\d+\s*){2,}", cleaned):
            continue
        if cleaned and len(cleaned) > 10:
            cleaned = cleaned[0].upper() + cleaned[1:]
            extracted.append(cleaned)
            
    if not extracted and text:
        sentences = re.split(r"(?<=[.!?])\s+", text)
        for sentence in sentences:
            cleaned = _clean_text(sentence)
            if cleaned and len(cleaned) > 10 and not re.search(r"(\d+\.\d+\s*){2,}", cleaned):
                cleaned = cleaned[0].upper() + cleaned[1:]
                extracted.append(cleaned)

    return _deduplicate_list(extracted)


def _format_clinical_text_with_groq(blocks: Dict[str, str]) -> Dict[str, List[str]]:
    """
    Passes a dictionary of raw FDA text blocks to Groq for intelligent 
    bullet-point extraction and formatting in a single batched call.
    """
    valid_blocks = {k: v for k, v in blocks.items() if v and len(v.strip()) > 10}
    
    if not valid_blocks:
        return {k: [] for k in blocks.keys()}
        
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        return {k: _extract_bullet_points_fallback(v) for k, v in blocks.items()}
        
    client = Groq(api_key=api_key)
    model = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
    
    prompt = f"""You are an expert medical data formatter.
I am providing a JSON dictionary where the keys are section identifiers and the values are raw text from FDA drug labels.

Your task is to clean and format the text for each section into an array of concise, easy-to-read bullet points.

RULES:
1. Remove all FDA section numbers (e.g., "1 INDICATIONS AND USAGE", "1.1 Asthma", "12.3").
2. Remove parenthetical cross-references (e.g., "(see Warnings)", "( 1.2 )").
3. Remove statistical reporting, percentages, and clinical trial data tables.
4. Fix capitalization and punctuation so the points read naturally.
5. Do NOT split words on hyphens (e.g., keep "exercise-induced").
6. Split distinct clinical points into separate string elements in the array.
7. Do NOT hallucinate, infer, or add outside information.
8. Output strictly a valid JSON object matching the exact input keys, where each value is a JSON array of formatted strings.

INPUT JSON:
{json.dumps(valid_blocks, ensure_ascii=False)}
"""
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            response_format={"type": "json_object"}
        )
        result_text = response.choices[0].message.content.strip()
        
        if result_text.startswith("```json"):
            result_text = result_text[7:-3].strip()
        elif result_text.startswith("```"):
            result_text = result_text[3:-3].strip()
            
        parsed = json.loads(result_text)
        
        out = {}
        for k in blocks.keys():
            val = parsed.get(k, [])
            if isinstance(val, str):
                out[k] = [val]
            elif isinstance(val, list):
                out[k] = val
            else:
                out[k] = []
        return out
        
    except Exception as e:
        print(f"[FORMATTER LLM ERROR] {e}")
        return {k: _extract_bullet_points_fallback(v) for k, v in blocks.items()}


def _filter_keyword_statements(bullets: List[str], keywords: List[str]) -> List[str]:
    """Extract statements matching specific medical risk/clinical keywords from a list of bullets."""
    matched = []
    for bullet in bullets:
        bullet_lower = bullet.lower()
        if any(kw.lower() in bullet_lower for kw in keywords):
            matched.append(bullet)
    return _deduplicate_list(matched)


def _build_cards(
    medicine: Dict[str, Any],
    uses: List[str],
    dosage: Dict[str, Any],
    side_effects: Dict[str, Any],
    warnings: List[str],
    contraindications: List[str],
    interactions: Dict[str, Any],
    pregnancy: str,
    breastfeeding: str
) -> List[Dict[str, Any]]:
    """Build standardized frontend card representations."""
    cards = []

    if uses:
        cards.append({
            "title": "Uses",
            "icon": "pill",
            "type": "list",
            "items": uses
        })

    adult_dosage = dosage.get("adult", [])
    if adult_dosage:
        cards.append({
            "title": "Dosage",
            "icon": "schedule",
            "type": "list",
            "items": adult_dosage
        })

    common_side = side_effects.get("common", [])
    serious_side = side_effects.get("serious", [])
    if common_side or serious_side:
        all_side = []
        if common_side:
            all_side.extend([f"Common: {s}" for s in common_side])
        if serious_side:
            all_side.extend([f"Serious: {s}" for s in serious_side])
        cards.append({
            "title": "Side Effects",
            "icon": "activity",
            "type": "list",
            "items": all_side
        })

    if warnings:
        cards.append({
            "title": "Warnings & Precautions",
            "icon": "alert-triangle",
            "type": "warning",
            "items": warnings
        })

    if contraindications:
        cards.append({
            "title": "Contraindications",
            "icon": "x-circle",
            "type": "warning",
            "items": contraindications
        })

    preg_breast = []
    if pregnancy:
        preg_breast.append(f"Pregnancy: {pregnancy}")
    if breastfeeding:
        preg_breast.append(f"Breastfeeding: {breastfeeding}")
    if preg_breast:
        cards.append({
            "title": "Pregnancy & Lactation",
            "icon": "info",
            "type": "info",
            "items": preg_breast
        })

    return cards


def format_medicine_payload(raw_payload: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Format raw medicine retrieval payload into the target structured JSON.
    Uses Groq LLM to properly clean up and format the FDA label text blobs.
    """
    if not isinstance(raw_payload, dict):
        raw_payload = {}

    med = raw_payload.get("medicine") or {}
    openfda = raw_payload.get("openfda") or {}
    dailymed = raw_payload.get("dailymed") or {}

    name = _clean_text(med.get("medicine_name") or "")
    generic_name = _clean_text(med.get("generic_name") or "")
    
    raw_brand_names = med.get("brand_names") or []
    if isinstance(raw_brand_names, str):
        raw_brand_names = [raw_brand_names]
    brand_names = _deduplicate_list(raw_brand_names)

    manufacturer = _clean_text(med.get("manufacturer") or "")

    raw_route = med.get("route") or []
    if isinstance(raw_route, list):
        route = ", ".join([_clean_text(r) for r in raw_route if _clean_text(r)])
    else:
        route = _clean_text(str(raw_route))

    raw_ingredients = med.get("active_ingredients") or []
    ingredients = []
    strength_parts = []
    for ing in raw_ingredients:
        if isinstance(ing, dict):
            ing_name = _clean_text(ing.get("name") or "")
            ing_str = _clean_text(ing.get("strength") or "")
            if ing_name:
                ingredients.append({"name": ing_name, "strength": ing_str})
                if ing_str:
                    strength_parts.append(f"{ing_name} {ing_str}")
        elif isinstance(ing, str) and _clean_text(ing):
            ingredients.append({"name": _clean_text(ing), "strength": ""})

    strength = ", ".join(strength_parts) if strength_parts else ""

    # --- 1. Gather all raw texts for LLM processing safely avoiding 'None' evaluations ---
    raw_uses = _stringify_list(med.get("uses"))
    
    dosage_info = med.get("dosage") or {}
    raw_dosage = (dosage_info.get("label_instructions") or "") if isinstance(dosage_info, dict) else str(dosage_info or "")
    
    raw_side_effects = _stringify_list(med.get("side_effects"))
    
    w = med.get("warnings") or ""
    p = med.get("precautions") or ""
    raw_warnings = f"{w}\n{p}".strip()

    blocks_to_format = {
        "main_uses": _truncate(raw_uses),
        "main_dosage": _truncate(raw_dosage),
        "main_side_effects": _truncate(raw_side_effects),
        "main_warnings": _truncate(raw_warnings)
    }

    ingredient_labels = raw_payload.get("ingredient_labels") or []
    for i, label in enumerate(ingredient_labels):
        if not isinstance(label, dict):
            continue
        clinical_med = label.get("medicine") or {}
        
        ing_uses = _stringify_list(clinical_med.get("uses"))
        ing_dosage = clinical_med.get("dosage", {}).get("label_instructions") or ""
        ing_side_effects = _stringify_list(clinical_med.get("side_effects"))
        
        iw = clinical_med.get("warnings") or ""
        ip = clinical_med.get("precautions") or ""
        ing_warnings = f"{iw}\n{ip}".strip()
        
        blocks_to_format[f"ing_{i}_uses"] = _truncate(ing_uses)
        blocks_to_format[f"ing_{i}_dosage"] = _truncate(ing_dosage)
        blocks_to_format[f"ing_{i}_side_effects"] = _truncate(ing_side_effects)
        blocks_to_format[f"ing_{i}_warnings"] = _truncate(ing_warnings)

    # --- 2. Call Groq LLM to format everything simultaneously ---
    formatted_blocks = _format_clinical_text_with_groq(blocks_to_format)

    # --- 3. Reassign formatted outputs ---
    uses = formatted_blocks.get("main_uses", [])
    dosage_bullets = formatted_blocks.get("main_dosage", [])
    side_effects_bullets = formatted_blocks.get("main_side_effects", [])
    warnings = formatted_blocks.get("main_warnings", [])

    # --- 4. Sub-filter interactions from the cleaned warnings ---
    serious_side_effects = _filter_keyword_statements(
        warnings, ["severe", "fatal", "life-threatening", "hospitalization", "cardiac"]
    )
    contraindications = _filter_keyword_statements(
        warnings, ["contraindicated", "do not use", "hypersensitivity", "allergic"]
    )
    
    drug_interactions = _filter_keyword_statements(warnings, ["drug interaction", "co-administration", "inhibit"])
    food_interactions = _filter_keyword_statements(warnings, ["food", "meal", "grapefruit", "diet"])
    alcohol_interactions = _filter_keyword_statements(warnings, ["alcohol", "ethanol", "liquor"])

    pregnancy = " ".join(_filter_keyword_statements(warnings, ["pregnancy", "pregnant", "teratogenic"]))
    breastfeeding = " ".join(_filter_keyword_statements(warnings, ["breastfeeding", "nursing", "lactation", "excreted in human milk"]))
    kidney = " ".join(_filter_keyword_statements(warnings, ["kidney", "renal", "creatinine"]))
    liver = " ".join(_filter_keyword_statements(warnings, ["liver", "hepatic", "alt", "ast"]))
    
    storage = " ".join(_filter_keyword_statements(warnings, ["store at", "temperature", "keep out of reach"]))
    missed_dose = " ".join(_filter_keyword_statements(warnings, ["missed dose", "forget to take", "skip"]))
    overdose = " ".join(_filter_keyword_statements(warnings, ["overdose", "poison control", "toxicity"]))
    monitoring = " ".join(_filter_keyword_statements(warnings, ["blood test", "monitor", "check"]))

    # --- 5. Assemble standard properties ---
    sources = []
    official_label = med.get("official_label") or {}
    if official_label.get("url"):
        sources.append({
            "name": official_label.get("source") or "Official Drug Label",
            "url": official_label.get("url")
        })
    elif openfda.get("source_url"):
        sources.append({
            "name": openfda.get("source_name") or "openFDA",
            "url": openfda.get("source_url")
        })
    elif dailymed.get("source_url"):
        sources.append({
            "name": "DailyMed",
            "url": dailymed.get("source_url")
        })

    structured_medicine = {
        "name": name,
        "generic_name": generic_name,
        "brand_names": brand_names,
        "manufacturer": manufacturer,
        "strength": strength,
        "route": route
    }

    structured_dosage = {
        "adult": dosage_bullets,
        "children": [],
        "elderly": []
    }

    structured_side_effects = {
        "common": side_effects_bullets,
        "serious": serious_side_effects
    }

    structured_interactions = {
        "drug": drug_interactions,
        "food": food_interactions,
        "alcohol": alcohol_interactions
    }

    cards = _build_cards(
        medicine=structured_medicine,
        uses=uses,
        dosage=structured_dosage,
        side_effects=structured_side_effects,
        warnings=warnings,
        contraindications=contraindications,
        interactions=structured_interactions,
        pregnancy=pregnancy,
        breastfeeding=breastfeeding
    )

    # --- 6. Append Combination Medicine Cards ---
    if ingredient_labels:
        for index, label in enumerate(ingredient_labels):
            if not isinstance(label, dict):
                continue
                
            clinical_med = label.get("medicine") or {}
            ing_name = label.get("ingredient") or clinical_med.get("generic_name") or f"Ingredient {index + 1}"
            ing_name = _clean_text(ing_name).upper()
            
            ing_uses = formatted_blocks.get(f"ing_{index}_uses", [])
            ing_dosage = formatted_blocks.get(f"ing_{index}_dosage", [])
            ing_side_effects = formatted_blocks.get(f"ing_{index}_side_effects", [])
            ing_warnings = formatted_blocks.get(f"ing_{index}_warnings", [])
            
            if ing_uses:
                cards.append({"title": f"{ing_name} - Uses", "icon": "pill", "type": "list", "items": ing_uses})
            if ing_dosage:
                cards.append({"title": f"{ing_name} - Dosage", "icon": "schedule", "type": "list", "items": ing_dosage})
            if ing_side_effects:
                cards.append({"title": f"{ing_name} - Side Effects", "icon": "activity", "type": "list", "items": ing_side_effects})
            if ing_warnings:
                cards.append({"title": f"{ing_name} - Warnings", "icon": "alert-triangle", "type": "warning", "items": ing_warnings})

    return {
        "medicine": structured_medicine,
        "uses": uses,
        "dosage": structured_dosage,
        "ingredients": ingredients,
        "side_effects": structured_side_effects,
        "warnings": warnings,
        "contraindications": contraindications,
        "interactions": structured_interactions,
        "pregnancy": pregnancy,
        "breastfeeding": breastfeeding,
        "kidney": kidney,
        "liver": liver,
        "storage": storage,
        "missed_dose": missed_dose,
        "overdose": overdose,
        "monitoring": monitoring,
        "sources": sources,
        "cards": cards
    }