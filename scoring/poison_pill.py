import json
import os
from typing import Any, Dict, List

import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

DEFAULT_MODEL = "gemini-2.0-flash"


def _normalize_clause_text(text: str) -> str:
    return " ".join(str(text or "").strip().lower().split())


def _normalize_severity(value: Any) -> str:
    sev = str(value or "").upper()
    if sev in {"CRITICAL", "HIGH", "MEDIUM"}:
        return sev
    return "MEDIUM"


def _find_clause_page(clause_text: str, raw_pages: List[Dict[str, Any]]) -> tuple[int, bool]:
    needle = _normalize_clause_text(clause_text)
    if not needle:
        return 0, False
    for page in raw_pages:
        page_number = int(page.get("page_number", 0) or 0)
        page_text = _normalize_clause_text(page.get("text", ""))
        if needle and needle in page_text:
            return page_number, True
    return 0, False


def _sweep_page_for_risks(page_text: str, model: str = DEFAULT_MODEL) -> Dict[str, Any]:
    system_prompt = (
        "Does this page contain any clause that could automatically disqualify a bidder, "
        "impose unlimited liability, restrict nationality, ban subcontracting, or impose "
        "unfair sole discretion on the client? Return ONLY a JSON object: "
        "{\"found\": bool, \"clause_text\": string, \"reason\": string, \"severity\": \"CRITICAL\"|\"HIGH\"|\"MEDIUM\"}. "
        "If nothing found return {\"found\": false}."
    )
    m = genai.GenerativeModel(
        model,
        system_instruction=system_prompt,
        generation_config=genai.GenerationConfig(
            temperature=0,
            max_output_tokens=800,
            response_mime_type="application/json",
        ),
    )
    response = m.generate_content(json.dumps({"page_text": page_text[:12000]}))
    raw = response.text.strip()
    parsed = json.loads(raw)
    if not isinstance(parsed, dict):
        return {"found": False}
    return {
        "found": bool(parsed.get("found", False)),
        "clause_text": str(parsed.get("clause_text", "") or ""),
        "reason": str(parsed.get("reason", "") or ""),
        "severity": _normalize_severity(parsed.get("severity", "MEDIUM")),
    }


def detect_poison_pills(
    extracted_poison_pills: List[Dict[str, Any]],
    raw_pages: List[Dict[str, Any]],
    groq_api_key: str | None = None,
    model: str = DEFAULT_MODEL,
) -> List[Dict[str, Any]]:
    api_key = groq_api_key or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("Google API key is required. Set GOOGLE_API_KEY.")
    genai.configure(api_key=api_key)

    combined: List[Dict[str, Any]] = []
    seen_clauses = set()

    # Pass 1: confirm parser extracted clauses by locating clause_text in raw pages.
    for item in extracted_poison_pills:
        if not isinstance(item, dict):
            continue
        clause_text = str(item.get("clause_text", "") or "")
        if not clause_text.strip():
            continue
        parser_page = int(item.get("page_number", 0) or 0)
        found_page, confirmed = _find_clause_page(clause_text, raw_pages)
        page_number = found_page if confirmed else parser_page
        row = {
            "clause_text": clause_text,
            "page_number": page_number,
            "severity": _normalize_severity(item.get("severity", "MEDIUM")),
            "reason": str(item.get("trigger_condition", "") or ""),
            "source": "parser",
            "confirmed": confirmed,
        }
        key = _normalize_clause_text(clause_text)
        if key and key not in seen_clauses:
            combined.append(row)
            seen_clauses.add(key)

    # Pass 2: sweep pages for missed risky clauses.
    for page in raw_pages:
        page_number = int(page.get("page_number", 0) or 0)
        page_text = str(page.get("text", "") or "")
        if not page_text.strip():
            continue

        sweep = _sweep_page_for_risks(page_text=page_text, model=model)
        if not sweep.get("found", False):
            continue

        clause_text = str(sweep.get("clause_text", "") or "").strip()
        if not clause_text:
            continue
        key = _normalize_clause_text(clause_text)
        if key in seen_clauses:
            continue
        seen_clauses.add(key)

        combined.append(
            {
                "clause_text": clause_text,
                "page_number": page_number,
                "severity": _normalize_severity(sweep.get("severity", "MEDIUM")),
                "reason": str(sweep.get("reason", "") or ""),
                "source": "sweep",
            }
        )

    return [
        {
            "clause_text": item.get("clause_text", ""),
            "page_number": int(item.get("page_number", 0) or 0),
            "severity": _normalize_severity(item.get("severity", "MEDIUM")),
            "reason": str(item.get("reason", "") or ""),
            "source": "parser" if str(item.get("source", "")).lower() == "parser" else "sweep",
        }
        for item in combined
    ]
