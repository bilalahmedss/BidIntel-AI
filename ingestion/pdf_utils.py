"""
PDF text extraction with automatic OCR fallback for scanned pages.

Strategy per page:
  1. Try PyMuPDF text layer (fast, zero tokens, preserves formatting).
  2. If extracted text is below OCR_THRESHOLD characters, the page is
     likely a scan — render it to an image and run Tesseract OCR.

This keeps LLM token usage low: only real text goes to the model,
not empty strings or garbled glyph data from image-only pages.
"""

from __future__ import annotations

import io
from typing import Any

import fitz  # pymupdf

# Pages with fewer characters than this after text extraction are treated
# as scanned and sent through OCR. Tweak if needed.
OCR_THRESHOLD = 50


def _ocr_page(page: fitz.Page) -> str:
    """Render a page to a 2× image and extract text with Tesseract."""
    try:
        import pytesseract
        from PIL import Image
    except ImportError:
        return ""

    import os
    # Allow overriding tesseract binary path via env var
    custom_path = os.getenv("TESSERACT_CMD")
    if custom_path:
        pytesseract.pytesseract.tesseract_cmd = custom_path

    # 2× zoom gives Tesseract enough resolution for reliable results
    mat = fitz.Matrix(2.0, 2.0)
    pix = page.get_pixmap(matrix=mat)
    img = Image.open(io.BytesIO(pix.tobytes("png")))

    try:
        return pytesseract.image_to_string(img).strip()
    except pytesseract.TesseractNotFoundError:
        # Tesseract binary not installed — silently fall back to empty string.
        # Text-layer extraction already returned sparse/empty text, so the
        # page will be skipped or sent with whatever text was found.
        return ""


def extract_page_text(page: fitz.Page, ocr: bool = True) -> str:
    """
    Return the best-available text for a single fitz Page.

    Args:
        page: An open fitz.Page object.
        ocr:  If True, fall back to Tesseract for pages with sparse text.
              Set to False to skip OCR (text-layer only).
    """
    text = page.get_text().strip()
    if not ocr or len(text) >= OCR_THRESHOLD:
        return text
    ocr_text = _ocr_page(page)
    # Use OCR result only if it found more content than the text layer
    return ocr_text if len(ocr_text) > len(text) else text


def extract_pdf_pages(pdf_path: str, ocr: bool = True) -> list[dict[str, Any]]:
    """
    Extract all pages from a PDF as a list of dicts.

    Returns:
        [{"page_number": int, "text": str}, ...]
    """
    pages: list[dict[str, Any]] = []
    with fitz.open(pdf_path) as doc:
        for i, page in enumerate(doc, start=1):
            pages.append({"page_number": i, "text": extract_page_text(page, ocr=ocr)})
    return pages
