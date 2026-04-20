import argparse
import json
import os
import re
from typing import Any, Callable, Dict, List, Optional

from backend.groq_client import create_json_completion
from backend.llm_schemas import validate_rfp_extraction_payload
from backend.safety import QuerySafetyLayer
from ingestion.pdf_utils import extract_pdf_as_markdown
from dotenv import load_dotenv

load_dotenv()
_safety = QuerySafetyLayer()

DEFAULT_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"
MAX_CHUNK_TOKENS = 8000
CHARS_PER_TOKEN_ESTIMATE = 4
CHUNK_OVERLAP_PAGES = 1
MAX_COMPLETION_TOKENS = 2000

BASE_SYSTEM_PROMPT = """You are an RFP analysis engine. Extract the complete evaluation structure
from this tender document. Return ONLY valid JSON with this exact schema:

{
  rfp_id: string,
  issuer: string,
  gates: [
    {
      gate_id: string,
      name: string,
      type: 'binary' | 'scored',
      max_points: number or null,
      advancement_threshold: number or null,
      criteria: [
        {
          id: string,
          name: string,
          max_points: number,
          checklist_signals: [list of specific things an evaluator looks for],
          evidence_required: [list of document types needed]
        }
      ]
    }
  ],
  poison_pill_clauses: [
    {
      id: string,
      clause_text: string,
      page_number: number,
      trigger_condition: string,
      severity: 'CRITICAL' | 'HIGH' | 'MEDIUM'
    }
  ],
  submission_rules: [string],
  wps_formula: string
}

Do not invent information. Only extract what is explicitly stated in the document.
Return ONLY valid JSON, no markdown, no explanation."""
SYSTEM_PROMPT = _safety.build_guarded_system_prompt(BASE_SYSTEM_PROMPT)


def _extract_rfp_id_from_filename(pdf_path: str) -> str:
    filename = os.path.basename(pdf_path)
    stem = os.path.splitext(filename)[0]
    match = re.search(r"(RFP[-_\s]?\d+)", stem, flags=re.IGNORECASE)
    return match.group(1).replace("_", "-").replace(" ", "-") if match else stem


def _coerce_float_or_none(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        cleaned = value.strip().replace(",", "")
        if not cleaned:
            return None
        try:
            return float(cleaned)
        except ValueError:
            return None
    return None


class RFPParser:
    def __init__(self, api_key: str | None = None, model: str = DEFAULT_MODEL) -> None:
        self.api_key = api_key or os.getenv("GROQ_API_KEY")
        if not self.api_key:
            raise ValueError("Groq API key is required. Set GROQ_API_KEY.")
        self.model = model

    def _extract_pdf_markdown(self, pdf_path: str) -> str:
        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"PDF file not found: {pdf_path}")
        return extract_pdf_as_markdown(pdf_path)

    def parse_pdf(
        self,
        pdf_path: str,
        on_chunk_progress: Optional[Callable[[int, int], None]] = None,
        on_chunk_start: Optional[Callable[[int, int], None]] = None,
    ) -> Dict[str, Any]:
        md = self._extract_pdf_markdown(pdf_path)
        chunks = self._split_markdown_by_sections(md)
        if not chunks:
            chunks = ["(No extractable text found in PDF.)"]

        merged: Dict[str, Any] = {
            "rfp_id": "",
            "issuer": "",
            "gates": [],
            "poison_pill_clauses": [],
            "submission_rules": [],
            "wps_formula": "",
        }
        seen_gate_ids = set()
        seen_clause_texts = set()
        seen_rules = set()

        for chunk_idx, chunk_text in enumerate(chunks, start=1):
            if on_chunk_start:
                on_chunk_start(chunk_idx, len(chunks))
            normalized_partial = self._extract_structured_from_chunk(chunk_text)
            if on_chunk_progress:
                on_chunk_progress(chunk_idx, len(chunks))

            if not merged["rfp_id"] and normalized_partial.get("rfp_id"):
                merged["rfp_id"] = normalized_partial["rfp_id"]
            if not merged["issuer"] and normalized_partial.get("issuer"):
                merged["issuer"] = normalized_partial["issuer"]
            if not merged["wps_formula"] and normalized_partial.get("wps_formula"):
                merged["wps_formula"] = normalized_partial["wps_formula"]

            for gate in normalized_partial.get("gates", []):
                gate_id = str(gate.get("gate_id", "") or "").strip().lower()
                dedupe_key = gate_id if gate_id else json.dumps(gate, sort_keys=True)
                if dedupe_key in seen_gate_ids:
                    continue
                seen_gate_ids.add(dedupe_key)
                merged["gates"].append(gate)

            for clause in normalized_partial.get("poison_pill_clauses", []):
                clause_text = str(clause.get("clause_text", "") or "").strip().lower()
                if not clause_text or clause_text in seen_clause_texts:
                    continue
                seen_clause_texts.add(clause_text)
                merged["poison_pill_clauses"].append(clause)

            for rule in normalized_partial.get("submission_rules", []):
                rule_norm = str(rule).strip().lower()
                if not rule_norm or rule_norm in seen_rules:
                    continue
                seen_rules.add(rule_norm)
                merged["submission_rules"].append(str(rule))

        normalized = self._normalize_schema(merged)
        if not normalized["rfp_id"]:
            normalized["rfp_id"] = _extract_rfp_id_from_filename(pdf_path)
        return normalized

    def _extract_structured_from_chunk(self, chunk_text: str) -> Dict[str, Any]:
        if _safety.detect_prompt_injection(chunk_text):
            _safety.record_event(
                route="analysis",
                context="rfp_chunk",
                event_type="prompt_injection_detected",
                action_taken="guarded_prompt_applied",
                metadata={"chunk_length": len(chunk_text)},
            )
        try:
            raw = create_json_completion(
                api_key=self.api_key,
                model=self.model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": chunk_text},
                ],
                temperature=0,
                max_tokens=MAX_COMPLETION_TOKENS,
            )
        except Exception as e:
            raise RuntimeError(str(e)) from e
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Model returned invalid JSON: {exc}\nRaw output:\n{raw}") from exc
        if not isinstance(parsed, dict):
            raise ValueError("Model output must be a JSON object.")
        normalized = self._normalize_schema(parsed)
        validated = validate_rfp_extraction_payload(normalized)
        return validated.model_dump()

    def _split_markdown_by_sections(self, md: str) -> List[str]:
        """
        Split a Markdown document at heading boundaries (# or ##).

        Keeping table rows inside the same chunk as their column headers is the
        whole point of layout-aware parsing: a compliance matrix like
          | Requirement | Mandatory |
          | ISO 27001   | YES       |
        must not be split so that only the data rows reach the LLM without the
        header context that gives them meaning.

        Falls back to page-break markers (--- PAGE N ---) when no Markdown
        headings are present (OCR fallback path in extract_pdf_as_markdown).
        """
        max_chars = min(MAX_CHUNK_TOKENS * CHARS_PER_TOKEN_ESTIMATE, 20000)

        # Primary split: Markdown section headings
        heading_re = re.compile(r"^#{1,2} ", re.MULTILINE)
        positions = [m.start() for m in heading_re.finditer(md)]

        if positions:
            sections: List[str] = []
            for i, pos in enumerate(positions):
                end = positions[i + 1] if i + 1 < len(positions) else len(md)
                section = md[pos:end].strip()
                if section:
                    sections.append(section)
            return self._pack_sections(sections, max_chars)

        # Fallback: page-break markers produced by the OCR path
        page_sections = [s.strip() for s in re.split(r"--- PAGE \d+ ---", md) if s.strip()]
        if page_sections:
            return self._pack_sections(page_sections, max_chars)

        # Last resort: raw character chunking with overlap
        chunks: List[str] = []
        i = 0
        while i < len(md):
            chunks.append(md[i : i + max_chars])
            i += max_chars - 500  # 500-char overlap
        return [c for c in chunks if c.strip()]

    def _pack_sections(self, sections: List[str], max_chars: int) -> List[str]:
        """
        Greedily pack sections into LLM-sized chunks with 1-section overlap so
        context near chunk boundaries is not lost (mirrors the old 1-page overlap).
        """
        chunks: List[str] = []
        i = 0
        while i < len(sections):
            parts: List[str] = []
            total = 0
            j = i
            while j < len(sections):
                s = sections[j]
                if parts and total + len(s) + 2 > max_chars:
                    break
                parts.append(s)
                total += len(s) + 2
                j += 1
            if not parts:
                # Single oversized section — truncate it
                parts = [sections[i][:max_chars]]
                j = i + 1
            chunks.append("\n\n".join(parts))
            if j >= len(sections):
                break
            i = max(j - 1, i + 1)  # 1-section overlap
        return chunks

    def _normalize_schema(self, data: Dict[str, Any]) -> Dict[str, Any]:
        result: Dict[str, Any] = {
            "rfp_id": str(data.get("rfp_id", "") or ""),
            "issuer": str(data.get("issuer", "") or ""),
            "gates": [],
            "poison_pill_clauses": [],
            "submission_rules": [],
            "wps_formula": str(data.get("wps_formula", "") or ""),
        }

        gates = data.get("gates", [])
        if isinstance(gates, list):
            for gate in gates:
                if not isinstance(gate, dict):
                    continue
                gate_type = str(gate.get("type", "") or "").lower()
                if gate_type not in {"binary", "scored"}:
                    gate_type = "binary"

                gate_obj: Dict[str, Any] = {
                    "gate_id": str(gate.get("gate_id", "") or ""),
                    "name": str(gate.get("name", "") or ""),
                    "type": gate_type,
                    "max_points": _coerce_float_or_none(gate.get("max_points")),
                    "advancement_threshold": _coerce_float_or_none(gate.get("advancement_threshold")),
                    "criteria": [],
                }

                criteria = gate.get("criteria", [])
                if isinstance(criteria, list):
                    for criterion in criteria:
                        if not isinstance(criterion, dict):
                            continue
                        signals = criterion.get("checklist_signals", [])
                        evidence = criterion.get("evidence_required", [])
                        gate_obj["criteria"].append(
                            {
                                "id": str(criterion.get("id", "") or ""),
                                "name": str(criterion.get("name", "") or ""),
                                "max_points": float(_coerce_float_or_none(criterion.get("max_points")) or 0.0),
                                "checklist_signals": [str(x) for x in signals] if isinstance(signals, list) else [],
                                "evidence_required": [str(x) for x in evidence] if isinstance(evidence, list) else [],
                            }
                        )
                result["gates"].append(gate_obj)

        pills = data.get("poison_pill_clauses", [])
        if isinstance(pills, list):
            for clause in pills:
                if not isinstance(clause, dict):
                    continue
                severity = str(clause.get("severity", "") or "").upper()
                if severity not in {"CRITICAL", "HIGH", "MEDIUM"}:
                    severity = "MEDIUM"
                page_number = clause.get("page_number", 0)
                if isinstance(page_number, str) and page_number.strip().isdigit():
                    page_number = int(page_number.strip())
                elif not isinstance(page_number, int):
                    page_number = int(_coerce_float_or_none(page_number) or 0)
                result["poison_pill_clauses"].append(
                    {
                        "id": str(clause.get("id", "") or ""),
                        "clause_text": str(clause.get("clause_text", "") or ""),
                        "page_number": page_number,
                        "trigger_condition": str(clause.get("trigger_condition", "") or ""),
                        "severity": severity,
                    }
                )

        rules = data.get("submission_rules", [])
        if isinstance(rules, list):
            result["submission_rules"] = [str(x) for x in rules if isinstance(x, (str, int, float))]
        return result


def parse_rfp_pdf(
    pdf_path: str,
    api_key: str | None = None,
    on_chunk_progress: Optional[Callable[[int, int], None]] = None,
    on_chunk_start: Optional[Callable[[int, int], None]] = None,
) -> Dict[str, Any]:
    return RFPParser(api_key=api_key).parse_pdf(
        pdf_path, on_chunk_progress=on_chunk_progress, on_chunk_start=on_chunk_start
    )


def main() -> None:
    arg_parser = argparse.ArgumentParser(description="Parse RFP PDF into structured JSON.")
    arg_parser.add_argument("pdf_path", help="Path to RFP PDF file")
    arg_parser.add_argument("--api-key", dest="api_key", default=None, help="Groq API key (optional)")
    args = arg_parser.parse_args()
    print(json.dumps(parse_rfp_pdf(args.pdf_path, api_key=args.api_key), indent=2))


if __name__ == "__main__":
    main()
