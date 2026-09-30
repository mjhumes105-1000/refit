"""The only module that touches a PDF engine.

Backed by pypdfium2 (PDFium, Chrome's PDF engine; Apache-2.0/BSD). Keeping every
PDF call behind these three functions lets the engine be swapped without touching
any stage.
"""

import io
from pathlib import Path

import pypdfium2 as pdfium


def _open(path: Path) -> pdfium.PdfDocument:
    return pdfium.PdfDocument(str(path))


def page_count(path: Path) -> int:
    pdf = _open(path)
    try:
        return len(pdf)
    finally:
        pdf.close()


def _page(pdf: pdfium.PdfDocument, index: int) -> pdfium.PdfPage:
    if not 0 <= index < len(pdf):
        raise IndexError(f"page {index} out of range (document has {len(pdf)} pages)")
    return pdf[index]


def page_text(path: Path, index: int) -> str:
    pdf = _open(path)
    try:
        return _page(pdf, index).get_textpage().get_text_range()
    finally:
        pdf.close()


def render_page_png(path: Path, index: int, dpi: int = 200) -> bytes:
    pdf = _open(path)
    try:
        image = _page(pdf, index).render(scale=dpi / 72).to_pil()
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        return buffer.getvalue()
    finally:
        pdf.close()
