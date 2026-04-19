import json
from pathlib import Path

from scoring.wps_calculator import calculate_wps


def main() -> int:
    outputs_dir = Path("data/outputs")
    parsed_path = outputs_dir / "parsed_rfp.json"
    scorer_path = outputs_dir / "scorer_results.json"

    if not parsed_path.exists():
        print(f"ERROR: Parsed RFP file not found: {parsed_path}")
        return 1
    if not scorer_path.exists():
        print(f"ERROR: Scorer results file not found: {scorer_path}")
        return 1

    parsed = json.loads(parsed_path.read_text(encoding="utf-8"))
    scorer = json.loads(scorer_path.read_text(encoding="utf-8"))

    extracted_gates = parsed.get("gates", [])
    criterion_scores = scorer.get("criterion_results", scorer)

    scenarios = ["conservative", "expected", "optimistic"]
    wps_outputs = {}
    for scenario in scenarios:
        print(f"\n=== Scenario: {scenario} ===\n")
        result = calculate_wps(extracted_gates, criterion_scores, financial_scenario=scenario)
        wps_outputs[scenario] = result

        print("Gate results:")
        for gate in result.get("gate_results", []):
            print(
                f"- Gate {gate.get('gate_id', '')} ({gate.get('name', '')}) "
                f"[type={gate.get('gate_type', '')}] status={gate.get('status', '')}"
            )
        print()

        print("Scenarios WPS:")
        for key, data in result.get("scenarios", {}).items():
            print(f"  {key}: WPS={data.get('wps', 0)} phase_a={data.get('phase_a', 0)} "
                  f"phase_b={data.get('phase_b', 0)} financial={data.get('financial_score', 0)}")

        print(f"\nVerdict: {result.get('verdict', '')}")
        print(f"Binding constraint: {result.get('binding_constraint', '')}")
        print("\n" + "=" * 60 + "\n")

    out_path = outputs_dir / "wps_results.json"
    out_path.write_text(json.dumps(wps_outputs, indent=2), encoding="utf-8")
    print(f"Saved WPS results to: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

