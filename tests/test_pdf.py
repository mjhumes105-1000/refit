import pytest

from refit.pdf import page_count, page_text, render_page_png

PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


def test_reads_text_layer_page_by_page(tmp_path, make_pdf):
    pdf = make_pdf(tmp_path / "two pages.pdf", ["DISTRIBUTION STATEMENT A\nsecond line (with parens)", "page two"])
    assert page_count(pdf) == 2
    first = " ".join(page_text(pdf, 0).split())
    assert "DISTRIBUTION STATEMENT A" in first
    assert "second line (with parens)" in first
    assert "page two" in page_text(pdf, 1)


def test_image_only_page_has_no_text_but_renders(tmp_path, make_pdf):
    pdf = make_pdf(tmp_path / "scan.pdf", [""])
    assert page_text(pdf, 0).strip() == ""
    png = render_page_png(pdf, 0, dpi=72)
    assert png.startswith(PNG_MAGIC)


def test_out_of_range_page_raises(tmp_path, make_pdf):
    pdf = make_pdf(tmp_path / "one.pdf", ["only page"])
    with pytest.raises(IndexError):
        page_text(pdf, 5)
