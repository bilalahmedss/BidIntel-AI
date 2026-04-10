import json
from pathlib import Path

from bidintel.rag.retriever import retrieve
from bidintel.scoring.criterion_scorer import score_extracted_gates


def main() -> int:
    outputs_dir = Path("bidintel/data/outputs")
    outputs_dir.mkdir(parents=True, exist_ok=True)

    parsed_path = outputs_dir / "parsed_rfp.json"
    if not parsed_path.exists():
        print(f"ERROR: Parsed RFP file not found: {parsed_path}")
        return 1

    parsed = json.loads(parsed_path.read_text(encoding="utf-8"))
    gates = parsed.get("gates", [])
    if not isinstance(gates, list) or not gates:
        print("ERROR: No gates found in parsed_rfp.json")
        return 2

    payload = score_extracted_gates(gates, retrieve, top_k=3)
    results = payload.get("criterion_results", [])
    gate_results = payload.get("gate_results", [])
    wps_summary = payload.get("wps_summary", {})

    for item in results:
        print(f"Criterion: {item.get('name', '')}")
        if "score" in item:
            print(f"Score: {item.get('score', 0)} / {item.get('max_points', 0)}")
        else:
            print(f"Status: {item.get('status', '')}")
        print(f"Matched signals: {item.get('matched_signals', [])}")
        print(f"Gap signals: {item.get('gap_signals', [])}")
        print()

    out_json = outputs_dir / "scorer_results.json"
    out_json.write_text(
        json.dumps(
            {
                "criterion_results": results,
                "gate_results": gate_results,
                "wps_summary": wps_summary,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"Saved scoring output to: {out_json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
