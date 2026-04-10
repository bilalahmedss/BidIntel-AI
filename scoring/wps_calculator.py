from typing import Any, Dict, List


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _criterion_score_map(criterion_scores: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    return {
        str(item.get("criterion_id", "") or ""): item
        for item in criterion_scores
        if isinstance(item, dict) and str(item.get("criterion_id", "") or "")
    }


def _is_financial_gate(gate: Dict[str, Any]) -> bool:
    gate_name = str(gate.get("name", "") or "").lower()
    if any(token in gate_name for token in ["financial", "price", "cost", "commercial"]):
        return True
    for c in gate.get("criteria", []) or []:
        cname = str(c.get("name", "") or "").lower()
        if any(token in cname for token in ["financial", "price", "cost", "commercial"]):
            return True
    return False


def _derive_threshold_bands(extracted_gates: List[Dict[str, Any]], default_max: float) -> Dict[str, float]:
    thresholds = []
    for gate in extracted_gates:
        t = gate.get("advancement_threshold")
        if t is not None:
            thresholds.append(_to_float(t, 0.0))
    thresholds = sorted({x for x in thresholds if x > 0}, reverse=True)

    # Derive bands from document thresholds. If fewer than 3 thresholds are available,
    # extend using relative reductions from the strongest threshold rather than fixed values.
    if not thresholds:
        top = max(default_max * 0.7, 1.0)
        thresholds = [top, top * 0.85, top * 0.75]
    elif len(thresholds) == 1:
        top = thresholds[0]
        thresholds = [top, top * 0.85, top * 0.75]
    elif len(thresholds) == 2:
        thresholds.append(thresholds[1] * 0.85)

    return {
        "strong": thresholds[0],
        "competitive": thresholds[1],
        "borderline": thresholds[2],
    }


def _verdict_from_bands(score_value: float, bands: Dict[str, float]) -> str:
    if score_value >= bands["strong"]:
        return "Strong"
    if score_value >= bands["competitive"]:
        return "Competitive"
    if score_value >= bands["borderline"]:
        return "Borderline"
    return "Weak"


def calculate_wps(
    extracted_gates: List[Dict[str, Any]],
    criterion_scores: List[Dict[str, Any]],
    financial_scenario: str,
) -> Dict[str, Any]:
    scenario_key = (financial_scenario or "expected").strip().lower()
    if scenario_key not in {"conservative", "expected", "optimistic"}:
        raise ValueError("financial_scenario must be one of: conservative, expected, optimistic")

    score_map = _criterion_score_map(criterion_scores)
    gate_results: List[Dict[str, Any]] = []

    # 1) Binary gates are hard PQ gates.
    for gate in extracted_gates:
        gate_type = str(gate.get("type", "") or "").lower()
        if gate_type != "binary":
            continue
        gate_id = str(gate.get("gate_id", "") or "")
        gate_name = str(gate.get("name", "") or "")
        failed = False
        for criterion in gate.get("criteria", []) or []:
            cid = str(criterion.get("id", "") or "")
            cscore = _to_float(score_map.get(cid, {}).get("score", 0.0), 0.0)
            if cscore <= 0:
                failed = True
                break
        gate_results.append({"gate_id": gate_id, "name": gate_name, "type": "binary", "passed": not failed})
        if failed:
            return {
                "pq_gate": 0,
                "gate_results": gate_results,
                "scenarios": {
                    "conservative": {"wps": 0.0, "phase_a": 0.0, "phase_b": 0.0, "financial_score": 0.0},
                    "expected": {"wps": 0.0, "phase_a": 0.0, "phase_b": 0.0, "financial_score": 0.0},
                    "optimistic": {"wps": 0.0, "phase_a": 0.0, "phase_b": 0.0, "financial_score": 0.0},
                },
                "binding_constraint": f"Failed binary gate {gate_id or gate_name}.",
                "verdict": "DO NOT BID",
            }

    pq_gate = 1

    # 2) Scored gates totals and threshold checks.
    phase_a_total = 0.0
    eliminated_at = ""
    financial_max_points = 0.0
    for gate in extracted_gates:
        gate_type = str(gate.get("type", "") or "").lower()
        if gate_type != "scored":
            continue
        gate_id = str(gate.get("gate_id", "") or "")
        gate_name = str(gate.get("name", "") or "")
        criteria = gate.get("criteria", []) or []
        gate_score = 0.0
        gate_max = 0.0
        for criterion in criteria:
            cid = str(criterion.get("id", "") or "")
            gate_score += _to_float(score_map.get(cid, {}).get("score", 0.0), 0.0)
            gate_max += _to_float(criterion.get("max_points", 0.0), 0.0)
        threshold = gate.get("advancement_threshold")
        threshold_val = _to_float(threshold, 0.0) if threshold is not None else None
        passed = True if threshold_val is None else gate_score >= threshold_val
        if not passed and not eliminated_at:
            eliminated_at = gate_id or gate_name
        gate_results.append(
            {
                "gate_id": gate_id,
                "name": gate_name,
                "type": "scored",
                "score": round(gate_score, 2),
                "max_points": round(gate_max, 2),
                "advancement_threshold": threshold_val,
                "passed": passed,
            }
        )
        phase_a_total += gate_score
        if _is_financial_gate(gate):
            financial_max_points += gate_max

    if eliminated_at:
        pq_gate = 0

    # 3,4,5) Scenario calculations.
    phase_b_map = {
        "conservative": phase_a_total * 0.85,
        "expected": phase_a_total * ((0.85 + 1.0) / 2.0),
        "optimistic": phase_a_total * 1.0,
    }
    # Using ratio form requested: lowest / (lowest * multiplier) * max = (1/multiplier)*max
    financial_map = {
        "conservative": (1.0 / 1.30) * financial_max_points if financial_max_points > 0 else 0.0,
        "expected": (1.0 / 1.10) * financial_max_points if financial_max_points > 0 else 0.0,
        "optimistic": financial_max_points,
    }

    scenarios: Dict[str, Dict[str, Any]] = {}
    for key in ("conservative", "expected", "optimistic"):
        wps = pq_gate * (phase_a_total + phase_b_map[key] + financial_map[key])
        scenarios[key] = {
            "wps": round(wps, 2),
            "phase_a": round(phase_a_total, 2),
            "phase_b": round(phase_b_map[key], 2),
            "financial_score": round(financial_map[key], 2),
        }

    # 6) Verdict from derived gate thresholds.
    bands = _derive_threshold_bands(extracted_gates, default_max=max(phase_a_total + financial_max_points, 1.0))
    selected_wps = scenarios[scenario_key]["wps"]
    verdict = "DO NOT BID" if pq_gate == 0 else _verdict_from_bands(selected_wps, bands)

    if pq_gate == 0 and eliminated_at:
        binding_constraint = f"eliminated at gate {eliminated_at}"
    elif financial_max_points <= 0:
        binding_constraint = "no financial scoring gate found in extracted_gates"
    else:
        binding_constraint = f"scenario={scenario_key}, derived thresholds={bands}"

    return {
        "pq_gate": pq_gate,
        "gate_results": gate_results,
        "scenarios": scenarios,
        "binding_constraint": binding_constraint,
        "verdict": verdict,
    }
