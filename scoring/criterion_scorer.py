import json
import os
from typing import Any, Callable, Dict, List

from groq import Groq
from dotenv import load_dotenv

load_dotenv()

DEFAULT_MODEL = "llama-3.3-70b-versatile"

def _normalize_signal(signal: str) -> str:
    return " ".join(signal.strip().lower().split())


def _extract_matched_signals_with_llm(
    criterion_name: str,
    criterion_description: str,
    checklist_signals: List[str],
    retrieved_chunks: List[str],
    model: str = DEFAULT_MODEL,
) -> List[str]:
    if not checklist_signals or not retrieved_chunks:
        return []

    system_prompt = (
        "Given these document excerpts and this list of signals, return ONLY a JSON object "
        "with key 'matched_signals' containing an array of strings: the signals clearly present "
        "in the excerpts. Do not invent matches. If nothing matches, return {\"matched_signals\": []}."
    )
    user_payload = {
        "criterion_name": criterion_name,
        "criterion_description": criterion_description,
        "checklist_signals": checklist_signals,
        "retrieved_chunks": retrieved_chunks,
    }

    co = Groq(api_key=os.getenv("GROQ_API_KEY"))
    response = co.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": json.dumps(user_payload)},
        ],
        response_format={"type": "json_object"},
        temperature=0,
        max_tokens=1500,
    )
    raw = response.choices[0].message.content.strip()
    parsed = json.loads(raw)
    if isinstance(parsed, dict) and "matched_signals" in parsed and isinstance(parsed["matched_signals"], list):
        parsed = parsed["matched_signals"]
    elif isinstance(parsed, dict):
        # JSON-object mode can wrap output in arbitrary keys; pick the first list value if present.
        list_value = next((v for v in parsed.values() if isinstance(v, list)), None)
        if list_value is not None:
            parsed = list_value
    elif isinstance(parsed, str):
        # Some models return a JSON-encoded array as a string.
        try:
            parsed = json.loads(parsed)
        except json.JSONDecodeError:
            pass
    if not isinstance(parsed, list):
        raise ValueError("LLM output must be a JSON array of strings.")

    allowed_by_norm = {_normalize_signal(s): s for s in checklist_signals}
    matched: List[str] = []
    seen = set()
    for item in parsed:
        if not isinstance(item, str):
            continue
        canonical = allowed_by_norm.get(_normalize_signal(item))
        if canonical and canonical not in seen:
            matched.append(canonical)
            seen.add(canonical)
    return matched


def score_extracted_gates(
    extracted_gates: List[Dict[str, Any]],
    retriever: Callable[[str, int], List[str]],
    top_k: int = 3,
    groq_api_key: str | None = None,
    model: str = DEFAULT_MODEL,
    on_progress: Callable[[int, int, str], None] | None = None,
) -> Dict[str, Any]:
    api_key = groq_api_key or os.getenv("GROQ_API_KEY")
    if not api_key:
        raise ValueError("Groq API key is required. Set GROQ_API_KEY.")

    criterion_results: List[Dict[str, Any]] = []
    gate_results: List[Dict[str, Any]] = []
    binary_gate_failed = False
    eliminated_at_gate = ""
    total_numeric_score = 0.0

    total_criteria = sum(
        len(g.get("criteria", []) or []) for g in extracted_gates if isinstance(g, dict)
    )
    scored_so_far = 0

    for gate in extracted_gates:
        if not isinstance(gate, dict):
            continue

        gate_id = str(gate.get("gate_id", "") or "")
        gate_name = str(gate.get("name", "") or "")
        gate_type = str(gate.get("type", "") or "").lower()
        criteria = gate.get("criteria", [])
        if not isinstance(criteria, list):
            criteria = []

        gate_numeric_score = 0.0
        gate_numeric_max = 0.0
        gate_present_count = 0
        gate_checklist_count = 0
        gate_failed_binary = False

        criteria = gate.get("criteria", [])
        for criterion in criteria:
            if not isinstance(criterion, dict):
                continue

            scored_so_far += 1
            criterion_id = str(criterion.get("id", "") or "")
            name = str(criterion.get("name", "") or "")
            description = str(criterion.get("description", "") or "")
            max_points_raw = criterion.get("max_points", 0.0)
            max_points = float(max_points_raw or 0.0)

            checklist_signals_raw = criterion.get("checklist_signals", [])
            checklist_signals = [str(s) for s in checklist_signals_raw] if isinstance(checklist_signals_raw, list) else []

            query = f"{name}\n{description}".strip()
            retrieved_chunks = retriever(query, top_k=top_k) if query else []

            matched_signals = _extract_matched_signals_with_llm(
                criterion_name=name,
                criterion_description=description,
                checklist_signals=checklist_signals,
                retrieved_chunks=retrieved_chunks,
                model=model,
            )

            if on_progress:
                on_progress(scored_so_far, total_criteria, name)

            matched_norm = {_normalize_signal(s) for s in matched_signals}
            gap_signals = [s for s in checklist_signals if _normalize_signal(s) not in matched_norm]
            total_signals = len(checklist_signals)
            has_gaps = len(gap_signals) > 0

            if gate_type == "binary":
                status = "PASS" if not has_gaps else "FAIL"
                if status == "FAIL":
                    gate_failed_binary = True
                    binary_gate_failed = True
                criterion_results.append(
                    {
                        "gate_id": gate_id,
                        "gate_name": gate_name,
                        "gate_type": "binary",
                        "criterion_id": criterion_id,
                        "name": name,
                        "status": status,
                        "matched_signals": matched_signals,
                        "gap_signals": gap_signals,
                    }
                )
                continue

            if gate_type == "scored" and max_points <= 0:
                status = "PRESENT" if len(matched_signals) > 0 else "MISSING"
                if status == "PRESENT":
                    gate_present_count += 1
                gate_checklist_count += 1
                criterion_results.append(
                    {
                        "gate_id": gate_id,
                        "gate_name": gate_name,
                        "gate_type": "scored",
                        "criterion_id": criterion_id,
                        "name": name,
                        "status": status,
                        "matched_signals": matched_signals,
                        "gap_signals": gap_signals,
                        "max_points": 0.0,
                    }
                )
                continue

            # Default numeric scoring path for scored criteria with points.
            score = (len(matched_signals) / total_signals) * max_points if total_signals > 0 else 0.0
            score = round(score, 2)
            gate_numeric_score += score
            gate_numeric_max += max_points
            criterion_results.append(
                {
                    "gate_id": gate_id,
                    "gate_name": gate_name,
                    "gate_type": "scored",
                    "criterion_id": criterion_id,
                    "name": name,
                    "score": score,
                    "max_points": max_points,
                    "matched_signals": matched_signals,
                    "gap_signals": gap_signals,
                }
            )

        gate_result: Dict[str, Any] = {
            "gate_id": gate_id,
            "gate_name": gate_name,
            "gate_type": gate_type,
        }

        if gate_type == "binary":
            gate_result["status"] = "FAIL" if gate_failed_binary else "PASS"
        elif gate_type == "scored":
            threshold = gate.get("advancement_threshold", None)
            threshold_val = float(threshold) if isinstance(threshold, (int, float, str)) and str(threshold).strip() else None
            gate_result.update(
                {
                    "score": round(gate_numeric_score, 2),
                    "max_points": round(gate_numeric_max, 2),
                    "checklist_present_count": gate_present_count,
                    "checklist_total_count": gate_checklist_count,
                    "advancement_threshold": threshold_val,
                }
            )
            if threshold_val is not None and gate_numeric_score < threshold_val and not eliminated_at_gate:
                eliminated_at_gate = gate_id or gate_name or "unknown_gate"
                gate_result["status"] = "ELIMINATED"
            else:
                gate_result["status"] = "PASSED"
            total_numeric_score += gate_numeric_score
        else:
            gate_result["status"] = "UNKNOWN_TYPE"

        gate_results.append(gate_result)

    if binary_gate_failed:
        wps = 0.0
        verdict = "DO NOT BID"
        elimination_reason = "At least one binary gate contains FAIL criteria."
    else:
        wps = round(total_numeric_score, 2)
        if eliminated_at_gate:
            verdict = "ELIMINATED"
            elimination_reason = f"Threshold not met at gate: {eliminated_at_gate}"
        else:
            verdict = "QUALIFIED"
            elimination_reason = ""

    return {
        "criterion_results": criterion_results,
        "gate_results": gate_results,
        "wps_summary": {
            "wps": wps,
            "verdict": verdict,
            "elimination_reason": elimination_reason,
        },
    }


def score_criterion(
    criterion: Dict[str, Any],
    retriever: Callable[[str, int], List[str]],
    top_k: int = 3,
    groq_api_key: str | None = None,
    model: str = DEFAULT_MODEL,
) -> Dict[str, Any]:
    gate_stub = {"criteria": [criterion]}
    payload = score_extracted_gates(
        extracted_gates=[gate_stub],
        retriever=retriever,
        top_k=top_k,
        groq_api_key=groq_api_key,
        model=model,
    )
    results = payload.get("criterion_results", [])
    if results:
        item = results[0]
        if "score" not in item:
            item = {**item, "score": 0.0}
        if "max_points" not in item:
            item = {**item, "max_points": float(criterion.get("max_points", 0.0) or 0.0)}
        return item
    return {
        "criterion_id": str(criterion.get("id", "") or ""),
        "name": str(criterion.get("name", "") or ""),
        "score": 0.0,
        "max_points": float(criterion.get("max_points", 0.0) or 0.0),
        "matched_signals": [],
        "gap_signals": [],
    }
