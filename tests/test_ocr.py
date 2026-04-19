"""
Quick diagnostic for PDF extraction + OCR fallback.

Usage:
    python tests/test_ocr.py                          # tests all PDFs in repo root
    python tests/test_ocr.py path/to/your.pdf         # test a specific file
    python tests/test_ocr.py path/to/your.pdf --no-ocr  # text layer only

Output shows, per page:
  - How many characters were extracted
  - Whether OCR was used (scanned page) or text layer was used
  - A short preview of the extracted text
"""

import argparse
import os
import sys
import time
from pathlib import Path

# Force UTF-8 output on Windows so non-ASCII chars in PDFs don't crash the terminal
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

import fitz
from ingestion.pdf_utils import extract_page_text, OCR_THRESHOLD


def test_pdf(pdf_path: str, use_ocr: bool = True):
    path = Path(pdf_path)
    print(f"\n{'='*60}")
    print(f"File : {path.name}")
    print(f"Size : {path.stat().st_size / 1024:.1f} KB")
    print(f"OCR  : {'enabled (fallback for sparse pages)' if use_ocr else 'disabled'}")
    print(f"{'='*60}")

    total_chars = 0
    ocr_pages = 0
    text_pages = 0
    empty_pages = 0

    t0 = time.time()
    with fitz.open(str(path)) as doc:
        print(f"Pages: {len(doc)}\n")
        for i, page in enumerate(doc, start=1):
            raw = page.get_text().strip()
            used_ocr = use_ocr and len(raw) < OCR_THRESHOLD

            extracted = extract_page_text(page, ocr=use_ocr)
            chars = len(extracted)
            total_chars += chars

            if chars == 0:
                status = "EMPTY  "
                empty_pages += 1
            elif used_ocr:
                status = "OCR    "
                ocr_pages += 1
            else:
                status = "TEXT   "
                text_pages += 1

            preview = extracted[:80].replace("\n", " ") if extracted else "(no text)"
            print(f"  Page {i:>3}  [{status}]  {chars:>5} chars  |  {preview}")

    elapsed = time.time() - t0
    print(f"\nSummary")
    print(f"  Text-layer pages : {text_pages}")
    print(f"  OCR pages        : {ocr_pages}")
    print(f"  Empty pages      : {empty_pages}")
    print(f"  Total chars      : {total_chars:,}")
    print(f"  Time             : {elapsed:.1f}s")

    if ocr_pages > 0:
        print(f"\n  [OK] OCR kicked in for {ocr_pages} scanned page(s)")
    elif empty_pages > 0:
        print(f"\n  [!!] {empty_pages} page(s) had no extractable text even after OCR")
    else:
        print(f"\n  [OK] All pages had a text layer - no OCR needed")


def main():
    parser = argparse.ArgumentParser(description="Test PDF text extraction + OCR")
    parser.add_argument("pdfs", nargs="*", help="PDF file(s) to test (defaults to all PDFs in repo root)")
    parser.add_argument("--no-ocr", action="store_true", help="Disable OCR fallback")
    args = parser.parse_args()

    use_ocr = not args.no_ocr

    if args.pdfs:
        pdfs = [Path(p) for p in args.pdfs]
    else:
        pdfs = sorted(ROOT.glob("*.pdf"))
        if not pdfs:
            print("No PDFs found in repo root. Pass a file path as argument.")
            sys.exit(1)

    for pdf in pdfs:
        if not pdf.exists():
            print(f"Not found: {pdf}")
            continue
        test_pdf(str(pdf), use_ocr=use_ocr)

    print()


if __name__ == "__main__":
    main()
