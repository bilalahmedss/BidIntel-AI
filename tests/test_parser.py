import json
import sys
from pathlib import Path

from ingestion.rfp_parser import parse_rfp_pdf


def main() -> int:
    tenders_dir = Path("data/tenders")
    pdfs = sorted(tenders_dir.glob("*.pdf"))

    if not pdfs:
        print("ERROR: No PDF found in data/tenders. Please add an RFP PDF and re-run.")
        return 1

    pdf_file = pdfs[0]
    pdf_path = str(pdf_file)
    print(f"Using PDF from {tenders_dir}: {pdf_path}")

    parsed = parse_rfp_pdf(pdf_path)
    print(json.dumps(parsed, indent=2))

    outputs_dir = Path("data/outputs")
    output_path = outputs_dir / "parsed_rfp.json"

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(parsed, indent=2), encoding="utf-8")
    print(f"Saved parsed JSON to: {output_path}")

    required_non_empty_fields = ["gates", "poison_pill_clauses", "submission_rules"]
    failures = []
    for field in required_non_empty_fields:
        value = parsed.get(field, [])
        if not isinstance(value, list) or len(value) == 0:
            failures.append(field)

    if failures:
        print(f"FAIL: Required fields are empty or missing: {', '.join(failures)}")
        return 2

    print("PASS: gates, poison_pill_clauses, and submission_rules are all non-empty.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())