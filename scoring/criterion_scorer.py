import json
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Callable, Dict, List

from backend.groq_client import create_json_completion
from backend.llm_schemas import validate_batch_criterion_payload
from backend.safety import QuerySafetyLayer
from dotenv import load_dotenv

load_dotenv()

DEFAULT_MODEL = "llama-3.3-70b-versatile"
BATCH_SIZE = 5
MAX_BATCH_PAYLOAD_CHARS = 18_000
MAX_BATCH_CONTEXT_CHARS = 12_000
MAX_BATCH_WORKERS = int(os.getenv("SCORING_BATCH_WORKERS", "3"))
_safety = QuerySafetyLayer()

def _normalize_signal(signal: str) -> str:
    return " ".join(signal.strip().lower().split())


def _trim_chunks(chunks: List[str], max_chars: int) -> List[str]:
    trimmed: List[str] = []
    total = 0
    for chunk in chunks:
        remaining = max_chars - total
        if remaining <= 0:
            break
        piece = chunk[:remaining]
        if piece.strip():
            trimmed.append(piece)
            total += len(piece)
    return trimmed


def _compact_snippet(text: str, max_chars: int = 260) -> str:
    compact = " ".join(str(text or "").split())
    if len(compact) <= max_chars:
        return compact
    return compact[: max_chars - 3].rstrip() + "..."


def _normalize_matched_signals(checklist_signals: List[str], matched_signals: List[str]) -> List[str]:
    allowed_by_norm = {_normalize_signal(s): s for s in checklist_signals}
    matched: List[str] = []
    seen = set()
    for item in matched_signals:
        if not isinstance(item, str):
            continue
        canonical = allowed_by_norm.get(_normalize_signal(item))
        if canonical and canonical not in seen:
            matched.append(canonical)
            seen.add(canonical)
    return matched


def _build_batch_payload(
    criteria_batch: List[Dict[str, Any]],
    retriever: Callable[[str, int], List[str]],
    top_k: int,
) -> Dict[str, Any]:
    shared_chunks: List[str] = []
    seen_chunks = set()
    criteria_payload: List[Dict[str, Any]] = []
    evidence_by_id: Dict[str, List[str]] = {}

    for criterion in criteria_batch:
        query = f"{criterion['name']}\n{criterion['description']}".strip()
        retrieved_chunks = retriever(query, top_k=top_k) if query else []
        evidence_by_id[criterion["criterion_id"]] = [_compact_snippet(chunk) for chunk in retrieved_chunks[:3]]
        for chunk in retrieved_chunks:
            if chunk not in seen_chunks:
                seen_chunks.add(chunk)
                shared_chunks.append(chunk)
        criteria_payload.append(
            {
                "criterion_id": criterion["criterion_id"],
                "name": criterion["name"],
                "description": criterion["description"],
                "checklist_signals": criterion["checklist_signals"],
            }
        )

    return {
        "payload": {
            "retrieved_chunks": _trim_chunks(shared_chunks, MAX_BATCH_CONTEXT_CHARS),
            "criteria": criteria_payload,
        },
        "evidence_by_id": evidence_by_id,
    }


def build_scoring_system_prompt() -> str:
    base_prompt = (
        "Given the shared document excerpts and these scoring criteria, return ONLY a JSON object "
        "keyed by criterion_id. Each value must be an object with key 'matched_signals' containing "
        "only the checklist signals clearly present in the excerpts for that criterion. Do not invent "
        "signals and do not include criterion IDs that were not provided."
    )
    return _safety.build_guarded_system_prompt(base_prompt)


def _build_rationale(
    criterion_name: str,
    matched_signals: List[str],
    gap_signals: List[str],
    evidence_snippets: List[str],
) -> str:
    if matched_signals and gap_signals:
        return (
            f"{criterion_name} is partially evidenced: matched {len(matched_signals)} signal(s) but still has "
            f"{len(gap_signals)} gap(s). Review the supporting excerpts before relying on this score."
        )
    if matched_signals:
        return (
            f"{criterion_name} is grounded by retrieved evidence covering {len(matched_signals)} signal(s). "
            "Human review should still confirm completeness against the source documents."
        )
    if evidence_snippets:
        return (
            f"{criterion_name} has retrieved context, but no checklist signals were confidently matched. "
            "This is a low-evidence result and may require manual review."
        )
    return (
        f"{criterion_name} has no retrieved supporting evidence. Treat this as a low-evidence result and verify "
        "manually before acting on it."
    )


def _score_batch_payload(
    criteria_batch: List[Dict[str, Any]],
    retriever: Callable[[str, int], List[str]],
    top_k: int,
    api_key: str | None,
    model: str = DEFAULT_MODEL,
) -> List[Dict[str, Any]]:
    if not criteria_batch:
        return []
    if all(not item["checklist_signals"] for item in criteria_batch):
        return [{**item, "matched_signals": [], "gap_signals": []} for item in criteria_batch]

    system_prompt = build_scoring_system_prompt()
    batch_bundle = _build_batch_payload(criteria_batch, retriever, top_k)
    user_payload = batch_bundle["payload"]
    evidence_by_id = batch_bundle["evidence_by_id"]

    if _safety.detect_prompt_injection(json.dumps(user_payload)):
        _safety.record_event(
            route="analysis",
            context="criterion_scoring_context",
            event_type="prompt_injection_detected",
            action_taken="guarded_prompt_applied",
            metadata={"criteria_in_batch": len(criteria_batch)},
        )

    if len(json.dumps(user_payload)) > MAX_BATCH_PAYLOAD_CHARS:
        if len(criteria_batch) == 1:
            user_payload["retrieved_chunks"] = _trim_chunks(user_payload["retrieved_chunks"], MAX_BATCH_CONTEXT_CHARS // 2)
        else:
            midpoint = max(1, len(criteria_batch) // 2)
            return _score_batch_payload(criteria_batch[:midpoint], retriever, top_k, api_key, model) + _score_batch_payload(
                criteria_batch[midpoint:], retriever, top_k, api_key, model
            )

    raw = create_json_completion(
        api_key=api_key,
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": json.dumps(user_payload)},
        ],
        temperature=0,
        max_tokens=1800,
    )
    parsed = json.loads(raw)
    if not isinstance(parsed, dict):
        raise ValueError("LLM output must be a JSON object keyed by criterion_id.")

    validated = validate_batch_criterion_payload(parsed)
    expected_ids = [item["criterion_id"] for item in criteria_batch]
    actual_ids = list(validated.root.keys())
    if set(actual_ids) != set(expected_ids):
        raise ValueError(
            f"Criterion batch output keys mismatch. Expected {sorted(expected_ids)}, got {sorted(actual_ids)}."
        )

    scored_batch: List[Dict[str, Any]] = []
    for item in criteria_batch:
        evidence_snippets = evidence_by_id.get(item["criterion_id"], [])
        matched_signals = _normalize_matched_signals(
            item["checklist_signals"],
            validated.root[item["criterion_id"]].matched_signals,
        )
        matched_norm = {_normalize_signal(signal) for signal in matched_signals}
        gap_signals = [signal for signal in item["checklist_signals"] if _normalize_signal(signal) not in matched_norm]
        scored_batch.append(
            {
                **item,
                "matched_signals": matched_signals,
                "gap_signals": gap_signals,
                "evidence_snippets": evidence_snippets,
                "evidence_strength": "grounded" if matched_signals else ("limited" if evidence_snippets else "none"),
                "rationale": _build_rationale(item["name"], matched_signals, gap_signals, evidence_snippets),
            }
        )
    return scored_batch


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

    flat_criteria: List[Dict[str, Any]] = []
    for gate in extracted_gates:
        if not isinstance(gate, dict):
            continue
        gate_id = str(gate.get("gate_id", "") or "")
        gate_name = str(gate.get("name", "") or "")
        gate_type = str(gate.get("type", "") or "").lower()
        criteria = gate.get("criteria", [])
        if not isinstance(criteria, list):
            continue
        for criterion in criteria:
            if not isinstance(criterion, dict):
                continue
            flat_criteria.append(
                {
                    "gate_id": gate_id,
                    "gate_name": gate_name,
                    "gate_type": gate_type,
                    "criterion_id": str(criterion.get("id", "") or ""),
                    "name": str(criterion.get("name", "") or ""),
                    "description": str(criterion.get("description", "") or ""),
                    "max_points": float(criterion.get("max_points", 0.0) or 0.0),
                    "checklist_signals": [str(s) for s in criterion.get("checklist_signals", [])] if isinstance(criterion.get("checklist_signals", []), list) else [],
                }
            )

    criterion_results: List[Dict[str, Any]] = []
    gate_results: List[Dict[str, Any]] = []
    binary_gate_failed = False

    total_criteria = len(flat_criteria)

    batches = [flat_criteria[i : i + BATCH_SIZE] for i in range(0, len(flat_criteria), BATCH_SIZE)]
    scored_batches: List[List[Dict[str, Any]]] = [[] for _ in batches]
    if batches:
        worker_count = max(1, min(MAX_BATCH_WORKERS, len(batches)))
        with ThreadPoolExecutor(max_workers=worker_count) as executor:
            future_to_index = {
                executor.submit(_score_batch_payload, batch, retriever, top_k, api_key, model): index
                for index, batch in enumerate(batches)
            }
            for future in as_completed(future_to_index):
                index = future_to_index[future]
                scored_batches[index] = future.result()

    scored_flat = [item for batch in scored_batches for item in batch]
    scored_iter = iter(scored_flat)
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
            max_points = float(criterion.get("max_points", 0.0) or 0.0)

            checklist_signals_raw = criterion.get("checklist_signals", [])
            checklist_signals = [str(s) for s in checklist_signals_raw] if isinstance(checklist_signals_raw, list) else []
            scored_entry = next(scored_iter, None)
            if scored_entry is None:
                raise ValueError("Criterion scoring batch output was incomplete.")
            matched_signals = scored_entry["matched_signals"]
            gap_signals = scored_entry["gap_signals"]

            if on_progress:
                on_progress(scored_so_far, total_criteria, name)

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

            # Equal-weight: criterion is PRESENT if any signal matched, else MISSING.
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
                    "max_points": max_points,
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
            gate_result.update(
                {
                    "met": gate_present_count,
                    "total": gate_checklist_count,
                    "status": "PASSED",
                }
            )
        else:
            gate_result["status"] = "UNKNOWN_TYPE"

        gate_results.append(gate_result)

    verdict = "DO NOT BID" if binary_gate_failed else "QUALIFIED"
    elimination_reason = "At least one binary gate contains FAIL criteria." if binary_gate_failed else ""

    return {
        "criterion_results": criterion_results,
        "gate_results": gate_results,
        "wps_summary": {
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
