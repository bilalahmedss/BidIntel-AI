import json
from pathlib import Path

import pdfplumber

from bidintel.ingestion.rfp_parser import parse_rfp_pdf
from bidintel.scoring.poison_pill import detect_poison_pills


def _extract_raw_pages(pdf_path: str):
    pages = []
    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages, start=1):
            pages.append({"page_number": i, "text": page.extract_text() or ""})
    return pages


def main() -> int:
    tenders_dir = Path("bidintel/data/tenders")
    pdfs = sorted(tenders_dir.glob("*.pdf"))
    if not pdfs:
        print("ERROR: No PDF found in bidintel/data/tenders.")
        return 1

    pdf_path = str(pdfs[0])
    print(f"Using PDF: {pdf_path}")

    parsed_json_path = Path("bidintel/data/outputs/parsed_rfp.json")
    if parsed_json_path.exists():
        parsed = json.loads(parsed_json_path.read_text(encoding="utf-8"))
        print(f"Loaded parsed JSON from: {parsed_json_path}")
    else:
        parsed = parse_rfp_pdf(pdf_path)
    extracted_poison_pills = parsed.get("poison_pill_clauses", [])
    raw_pages = _extract_raw_pages(pdf_path)

    findings = detect_poison_pills(extracted_poison_pills=extracted_poison_pills, raw_pages=raw_pages)

    for item in findings:
        print(f"Page {item.get('page_number', 0)} | {item.get('severity', 'MEDIUM')}")
        print(item.get("clause_text", ""))
        print()

    outputs_dir = Path("bidintel/data/outputs")
    outputs_dir.mkdir(parents=True, exist_ok=True)
    output_path = outputs_dir / "poison_pill_results.json"
    output_path.write_text(json.dumps(findings, indent=2), encoding="utf-8")
    print(f"Saved poison pill output to: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
