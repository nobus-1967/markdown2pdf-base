"""End-to-end Markdown-to-PDF conversion tests (require pandoc + xelatex)."""

import base64
import shutil
import subprocess
from pathlib import Path

import pytest

from markdown2pdf_base.converter import convert, convert_file

needs_pandoc = pytest.mark.skipif(
    shutil.which("pandoc") is None, reason="pandoc binary environment is not available"
)


def _extract_text(pdf: Path) -> str:
    """Return the plain-text content of a compiled PDF."""
    return subprocess.run(
        ["pdftotext", str(pdf), "-"],
        capture_output=True,
        text=True,
        check=False,
    ).stdout


@needs_pandoc
def test_convert_file_produces_pdf(tmp_path: Path) -> None:
    """convert_file writes a valid binary %PDF payload to disk."""
    md_path = tmp_path / "doc.md"
    md_path.write_text(
        "---\nlang: en\ntitle: Test Doc\nauthor: Jane\n---\n# Hello\n\nBody text.\n",
        encoding="utf-8",
    )

    pdf_path = tmp_path / "doc.pdf"
    result = convert_file(str(md_path), str(pdf_path))

    assert result is None
    assert pdf_path.exists()
    assert pdf_path.stat().st_size > 1000
    assert pdf_path.read_bytes().startswith(b"%PDF")


@needs_pandoc
def test_convert_returns_pdf_bytes() -> None:
    """convert returns raw compiled PDF bytes when no output path is given."""
    data = convert("# Hello\n\nSome **bold** text.", None)

    assert data is not None
    assert data.startswith(b"%PDF")
    assert len(data) > 1000


@needs_pandoc
def test_convert_front_matter_metadata_in_pdf(tmp_path: Path) -> None:
    """Front-matter metadata surfaces in the running header and PDF info."""
    md = (
        "---\ntitle: Front Matter Doc\nauthor: Ada\ndescription: D\n"
        "published: 2026-08-09\n---\n# Body\n\nText.\n"
    )
    data = convert(md, None)
    assert data is not None

    pdf_path = tmp_path / "out.pdf"
    pdf_path.write_bytes(data)

    text = _extract_text(pdf_path)
    assert "Front Matter Doc (Ada: 2026-08-09)" in text
    assert text.strip().startswith("Front Matter Doc (Ada: 2026-08-09)")

    info = subprocess.run(
        ["pdfinfo", str(pdf_path)],
        capture_output=True,
        text=True,
        check=False,
    ).stdout
    assert "Title:           Front Matter Doc" in info
    assert "Author:          Ada" in info


@needs_pandoc
def test_convert_japanese_ruby() -> None:
    """A Japanese document with ruby annotations compiles without crashing."""
    md = "# \u30bf\u30a4\u30c8\u30eb\n\n{\u6f22|\u304b\u3093}\n"
    data = convert(md, None, lang="ja")

    assert data is not None
    assert data.startswith(b"%PDF")


@needs_pandoc
def test_convert_inline_code_special_chars(tmp_path: Path) -> None:
    """Special characters and long runs inside inline code survive escaping."""
    md = (
        "Code `a_b.c%#d&$` caret `x^y` tilde `a~b` "
        "backslash `foo\\bar` long "
        "`aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
        "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
        "aaaaaaaaaaaaaaaaaaaaaaaaaaaaafoo_bar.baz` end.\n"
    )
    data = convert(md, None)
    assert data is not None

    pdf_path = tmp_path / "code.pdf"
    pdf_path.write_bytes(data)

    text = _extract_text(pdf_path)
    assert "a_b.c%#d&$" in text
    assert "x^y" in text
    assert "a~b" in text
    assert r"foo\bar" in text
    assert "foo_bar.baz" in text


@needs_pandoc
def test_convert_inline_code_in_heading(tmp_path: Path) -> None:
    """Inline code nested inside headings skips breakable_code rewrites."""
    md = (
        "# Title `<code>markdown2html5-base</code>`\n\n"
        "Body with `x^y` and long "
        "`aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
        "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
        "aaaaaaaaaaaaaaaaaaaaaaaaaaaaafoo_bar` end.\n"
    )
    data = convert(md, None)
    assert data is not None

    pdf_path = tmp_path / "head.pdf"
    pdf_path.write_bytes(data)

    text = _extract_text(pdf_path)
    assert "Title <code>markdown2html5-base</code>" in text
    assert "x^y" in text
    assert "foo_bar" in text


@needs_pandoc
def test_convert_code_lang_label(tmp_path: Path) -> None:
    """Fenced code blocks keep their language tag as a label above the block."""
    md = '```python\nprint("Hello")\n```\n'
    data = convert(md, None)
    assert data is not None

    pdf_path = tmp_path / "codelang.pdf"
    pdf_path.write_bytes(data)

    text = _extract_text(pdf_path)
    assert "/python/" in text
    assert 'print("Hello")' in text


@needs_pandoc
def test_convert_image_figure_caption(tmp_path: Path) -> None:
    """Captioned images emit a native caption; unlabelled images get no figure number."""
    img = tmp_path / "cat.png"
    img.write_bytes(
        base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk"
            "YPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
        )
    )
    md = (
        '# Figures\n\n![A cat](cat.png "My Picture of a Cat")\n\n![Alt Only](cat.png)\n'
    )
    data = convert(md, None, source_dir=str(tmp_path))
    assert data is not None

    pdf_path = tmp_path / "fig.pdf"
    pdf_path.write_bytes(data)

    text = _extract_text(pdf_path)
    assert "My Picture of a Cat" in text
    assert "Figure 1" not in text
    assert "Figure 2" not in text
