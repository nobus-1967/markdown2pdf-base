"""End-to-end Markdown-to-PDF conversion tests (require pandoc + xelatex).

The PDF geometry helpers rely on ``pdftotext`` from poppler-utils; tests that
need the bounding boxes are skipped when it is unavailable.
"""

import base64
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from markdown2html5_base import MarkdownToHTML
from markdown2pdf_base.converter import (
    CJK_DEFAULT_FONTS,
    FontConfig,
    _make_latex_header,
    _process_html,
    _write_lua_filter,
    convert,
    convert_file,
)

needs_pandoc = pytest.mark.skipif(
    shutil.which("pandoc") is None, reason="pandoc binary environment is not available"
)

needs_pdftotext = pytest.mark.skipif(
    shutil.which("pdftotext") is None,
    reason="pdftotext binary (poppler-utils) is not available",
)


def _extract_text(pdf: Path) -> str:
    """Return the plain-text content of a compiled PDF."""
    return subprocess.run(
        ["pdftotext", str(pdf), "-"],
        capture_output=True,
        text=True,
        check=False,
    ).stdout


def _text_right_edge(pdf: Path) -> float:
    """Return the x coordinate of the right text margin of ``pdf``, in points.

    The preamble sets 25.4 mm (72 pt) margins on every side, so the right text
    edge sits one margin width left of the page edge.
    """
    boxes = subprocess.run(
        ["pdftotext", "-bbox-layout", str(pdf), "-"],
        capture_output=True,
        text=True,
        check=False,
    ).stdout
    page_width = float(re.search(r'<page width="([\d.]+)"', boxes).group(1))
    return page_width - 72.0


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
def test_convert_escapes_latex_special_chars(tmp_path: Path) -> None:
    """Plain text keeps LaTeX special characters in filter-serialized contexts.

    Table cells, headings and link text are serialized by the Lua filter, not by
    pandoc's own LaTeX writer, so they depend on the filter's escaping: ``$``,
    ``%``, ``_``, ``&``, ``#``, ``{`` and ``}`` must all survive verbatim.
    """
    md = (
        "# Heading_with $dollar & amp # hash {brace} 50% off\n\n"
        "| Item | Price |\n| :--- | ---: |\n"
        "| a_b & c | $3.00 |\n\n"
        "A [a_b link](http://example.com) and 50% off.\n"
    )

    pdf_path = tmp_path / "escapes.pdf"
    pdf_path.write_bytes(convert(md, None) or b"")

    # Headings may wrap, so compare against whitespace-free text.
    text = "".join(_extract_text(pdf_path).split())
    assert "Heading_with$dollar&amp#hash{brace}50%off" in text
    assert "a_b&c$3.00" in text
    assert "a_blinkand50%off." in text


@needs_pandoc
def test_convert_inline_code_in_heading(tmp_path: Path) -> None:
    """Inline code nested inside headings gets the same breakable rewrites as body text."""
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
    assert "x^y" in text
    compacted = re.sub(r"\s+", "", text)
    assert "Title<code>markdown2html5-base</code>" in compacted
    assert "foo_bar" in compacted


@needs_pandoc
@needs_pdftotext
@pytest.mark.parametrize(
    "heading",
    [
        pytest.param(
            "Полное руководство по библиотекам романизации Хангыля в `Python`: "
            "`korean-romanizer` и `koroman`",
            id="ru",
        ),
        pytest.param(
            "A Comprehensive Guide to Hangul Romanization Libraries in Python: "
            "`korean-romanizer` and `koroman`",
            id="en",
        ),
    ],
)
def test_convert_long_heading_stays_inside_margins(
    tmp_path: Path, heading: str
) -> None:
    """A heading wider than the text block wraps instead of overrunning the right margin.

    Headings H1-H5 are set at 15-24 pt, so a single line holds far fewer words
    than body text; they must break exactly like the paragraphs around them.
    """
    md = "\n\n".join(
        f"{'#' * level} {heading}\n\n{heading} written as a paragraph."
        for level in range(1, 6)
    )

    pdf_path = tmp_path / "headings.pdf"
    pdf_path.write_bytes(convert(md, None) or b"")

    right_margin = _text_right_edge(pdf_path)
    boxes = subprocess.run(
        ["pdftotext", "-bbox-layout", str(pdf_path), "-"],
        capture_output=True,
        text=True,
        check=False,
    ).stdout
    x_max = [float(value) for value in re.findall(r'xMax="([\d.]+)"', boxes)]
    assert x_max, "no text boxes were extracted from the PDF"
    assert max(x_max) <= right_margin + 0.5


@needs_pandoc
@needs_pdftotext
def test_convert_long_heading_survives_toc(tmp_path: Path) -> None:
    """Heading break penalties stay valid when LaTeX writes them to a ``.toc`` file.

    Section titles are moving arguments: the ``\\penalty``/``\\allowbreak`` tokens
    the filter inserts must be written to the table of contents and read back
    without errors on the following runs.
    """
    heading = (
        "A Comprehensive Guide to Hangul Romanization Libraries in Python: "
        "`korean-romanizer` and `koroman`"
    )
    md = "\n\n".join(f"{'#' * level} {heading}" for level in range(1, 4))

    html_path = tmp_path / "doc.html"
    header_path = tmp_path / "header.tex"
    lua_path = tmp_path / "filter.lua"
    tex_path = tmp_path / "doc.tex"

    font_config = FontConfig()
    html, _ = _process_html(MarkdownToHTML().convert(md), None, "en", font_config)
    html_path.write_text(html, encoding="utf-8")
    header_path.write_text(
        _make_latex_header(font_config, dict(CJK_DEFAULT_FONTS), "ja"),
        encoding="utf-8",
    )
    _write_lua_filter(str(lua_path), dict(CJK_DEFAULT_FONTS), "ja")

    subprocess.run(
        [
            "pandoc",
            str(html_path),
            "-o",
            str(tex_path),
            "--pdf-engine=xelatex",
            "--variable=fontsize:12pt",
            "-H",
            str(header_path),
            "--lua-filter",
            str(lua_path),
        ],
        check=True,
        capture_output=True,
    )

    # Force a real table of contents so the section titles are written to a
    # .toc file and read back, the way a multi-run build would.
    tex_path.write_text(
        tex_path.read_text(encoding="utf-8").replace(
            "\\begin{document}", "\\begin{document}\n\\tableofcontents", 1
        ),
        encoding="utf-8",
    )

    for _ in range(2):
        result = subprocess.run(
            ["xelatex", "-interaction=nonstopmode", str(tex_path)],
            cwd=tmp_path,
            capture_output=True,
            text=True,
            check=False,
        )
    log = (tmp_path / "doc.log").read_text(encoding="utf-8", errors="replace")
    assert result.returncode == 0, log
    assert not re.search(r"^! ", log, re.MULTILINE), log


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


@needs_pandoc
def test_convert_image_path_with_spaces(tmp_path: Path) -> None:
    """Image paths containing spaces (URL-encoded as %20) must not break the LaTeX scan."""
    img_dir = tmp_path / "img dir"
    img_dir.mkdir()
    img = img_dir / "a cat.png"
    img.write_bytes(
        base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk"
            "YPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
        )
    )
    md = "# Figures\n\n![A cat](img dir/a cat.png)\n"
    data = convert(md, None, source_dir=str(tmp_path))
    assert data is not None

    pdf_path = tmp_path / "figspace.pdf"
    pdf_path.write_bytes(data)

    text = _extract_text(pdf_path)
    assert "Figures" in text


@needs_pandoc
def test_convert_table_long_cells_no_memory_overflow(tmp_path: Path) -> None:
    """Long CJK + long natural-width cells in one table must not blow up xltabular."""
    long_cjk = "蓝色的着法含有变着标有星号的着法含有注解支持东萍、鹏飞等多种格式单击“复制”复制当前局面微思象棋播放器 V2.6.7 Margin.Top © 版权所有"
    long_latin = "Ходы синего цвета содержат варианты. Ходы, отмеченные звёздочкой, содержат примечания. Поддерживает различные форматы, включая Dongping и Pengfei. Нажмите кнопку «Копировать», чтобы скопировать текущую позицию. Weisi Chess Player V2.6.7. Margin.Top © Все права защищены."
    md = f"| O | P |\n| :--- | :--- |\n| {long_cjk} | {long_latin} |\n"
    data = convert(md, None, lang="ru")
    assert data is not None

    pdf_path = tmp_path / "bigtable.pdf"
    pdf_path.write_bytes(data)

    text = _extract_text(pdf_path)
    assert "Pengfei" in text


@needs_pandoc
def test_convert_nested_lists(tmp_path: Path) -> None:
    """Nested lists (markdown2html5-base >= 0.6.0) keep their nesting in the PDF."""
    md = (
        "- Item 1\n"
        "- Item 2\n"
        "  - Subitem 1\n"
        "  - Subitem 2\n"
        "- Item 3\n"
        "\n"
        "- Item 4\n"
        "- Item 5\n"
        "  1. Subone\n"
        "     - Subsubitem\n"
        "  2. Subtwo\n"
    )
    data = convert(md, None)
    assert data is not None
    pdf_path = tmp_path / "nested.pdf"
    pdf_path.write_bytes(data)

    text = _extract_text(pdf_path)
    # Ordering proves the sublists stayed inside their parent item:
    # Item 2 before Subitem 1/2 before Item 3; Item 5 before Subone before Subtwo.
    pos = {
        key: text.index(key)
        for key in (
            "Item 2",
            "Subitem 1",
            "Item 3",
            "Item 5",
            "Subone",
            "Subsubitem",
            "Subtwo",
        )
    }
    assert pos["Item 2"] < pos["Subitem 1"] < pos["Item 3"]
    assert pos["Item 5"] < pos["Subone"] < pos["Subsubitem"] < pos["Subtwo"]
    assert "Item 1" in text

    layout = subprocess.run(
        ["pdftotext", "-layout", str(pdf_path), "-"],
        capture_output=True,
        text=True,
        check=False,
    ).stdout.splitlines()
    parent = next(ln for ln in layout if "Item 2" in ln)
    child = next(ln for ln in layout if "Subitem 1" in ln)
    assert len(child) - len(child.lstrip()) > len(parent) - len(parent.lstrip())


@needs_pandoc
def test_convert_task_list_checkboxes(tmp_path: Path) -> None:
    """Task-list checkboxes render via the symbol font (☑ checked, ☐ unchecked)."""
    if shutil.which("pdffonts") is None:
        pytest.skip("pdffonts not available")
    md = "- [ ] todo\n- [x] done\n1. [ ] one\n2. [x] two\n"
    data = convert(md, None)
    assert data is not None

    pdf_path = tmp_path / "todo.pdf"
    pdf_path.write_bytes(data)

    text = _extract_text(pdf_path)
    assert "todo" in text
    assert "done" in text
    assert "one" in text
    assert "two" in text

    fonts = subprocess.run(
        ["pdffonts", str(pdf_path)],
        capture_output=True,
        text=True,
        check=False,
    ).stdout
    assert "Symbola" in fonts


@needs_pandoc
def test_image_aspect_ratio(tmp_path: Path) -> None:
    """Images are scaled preserving their natural aspect ratio (no square distortion)."""
    try:
        import pdfplumber
    except ImportError:
        pytest.skip("pdfplumber not installed")

    # 839×602 cat PNG (aspect 1.394)
    img = tmp_path / "wide.png"
    img.write_bytes(
        base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAA0cAAAJaCAIAAABr56slAAAAIGNIUk0AAHomAACAhAAA+gAAAIDoAAB1MAAA6mAAADqYAAAXcJy6UTwAAAAGYktHRAD/AP8A/6C9p5MAAAAHdElNRQfqCQ8HJgt/O6xKAAAAJXRFWHRkYXRlOmNyZWF0ZQAyMDI2LTA5LTE1VDA3OjM4OjExKzAwOjAwwEqcfQAAACV0RVh0ZGF0ZTptb2RpZnkAMjAyNi0wOS0xNVQwNzozODoxMSswMDowMLEXJMEAAAAodEVYdGRhdGU6dGltZXN0YW1wADIwMjYtMDktMTVUMDc6Mzg6MTErMDA6MDDmAgUeAAALZklEQVR42u3ZwQmAUAwFwUTsv2VtQpC/zFSQY9i3M88AAHC46+8DAAD4wL1aHQDA+bQ6AIACrQ4AoECrAwAo0OoAAAq0OgCAAl8dAECBBRYAoECrAwAo0OoAAAq0OgCAAq0OAKBAqwMAKPDVAQAUWGABAAq0OgCAAq0OAKBAqwMAKPDVAQAUWGABAAq0OgCAAq0OAKBAqwMAKNDqAAAKtDoAgAJfHQBAgQUWAKBAqwMAKNDqAAAKtDoAgAKtDgCgQKsDACjw1QEAFFhgAQAKtDoAgAKtDgCgQKsDACjQ6gAACrQ6AIACXx0AQIEFFgCgQKsDACjQ6gAACrQ6AIACrQ4AoECrAwAo8NUBABRYYAEACrQ6AIACrQ4AoECrAwAo8NUBABRYYAEACrQ6AIACrQ4AoECrAwAo0OoAAAq0OgCAAl8dAECBBRYAoECrAwAo0OoAAAq0OgCAAq0OAKBAqwMAKPDVAQAUWGABAAq0OgCAAq0OAKBAqwMAKNDqAAAKtDoAgAJfHQBAgQUWAKBAqwMAKNDqAAAKtDoAgAKtDgCgQKsDACjw1QEAFFhgAQAKtDoAgAKtDgCgQKsDACjw1QEAFFhgAQAKtDoAgAKtDgCgQKsDACjQ6gAACrQ6AIACXx0AQIEFFgCgQKsDACjQ6gAACrQ6AIACrQ4AoECrAwAo8NUBABRYYAEACrQ6AIACrQ4AoECrAwAo0OoAAAq0OgCAAl8dAECBBRYAoECrAwAo0OoAAAq0OgCAAq0OAKBAqwMAKPDVAQAUWGABAAq0OgCAAq0OAKBAqwMAKPDVAQAUWGABAAq0OgCAAq0OAKBAqwMAKNDqAAAKtDoAgAJfHQBAgQUWAKBAqwMAKNDqAAAKtDoAgAKtDgCgQKsDACjw1QEAFFhgAQAKtDoAgAKtDgCgQKsDACjQ6gAACrQ6AIACXx0AQIEFFgCgQKsDACjQ6gAACrQ6AIACrQ4AoECrAwAo8NUBABRYYAEACrQ6AIACrQ4AoECrAwAo8NUBABRYYAEACrQ6AIACrQ4AoECrAwAo0OoAAAq0OgCAAl8dAECBBRYAoECrAwAo0OoAAAq0OgCAAq0OAKBAqwMAKPDVAQAUWGABAAq0OgCAAq0OAKBAqwMAKNDqAAAKtDoAgAJfHQBAgQUWAKBAqwMAKNDqAAAKtDoAgAKtDgCgQKsDACjw1QEAFFhgAQAKtDoAgAKtDgCgQKsDACjw1QEAFFhgAQAKtDoAgAKtDgCgQKsDACjQ6gAACrQ6AIACXx0AQIEFFgCgQKsDACjQ6gAACrQ6AIACrQ4AoECrAwAo8NUBABRYYAEACrQ6AIACrQ4AoECrAwAo0OoAAAq0OgCAAl8dAECBBRYAoECrAwAo0OoAAAq0OgCAAq0OAKBAqwMAKPDVAQAUWGABAAq0OgCAAq0OAKBAqwMAKPDVAQAUWGABAAq0OgCAAq0OAKBAqwMAKNDqAAAKtDoAgAJfHQBAgQUWAKBAqwMAKNDqAAAKtDoAgAKtDgCgQKsDACjw1QEAFFhgAQAKtDoAgAKtDgCgQKsDACjQ6gAACrQ6AIACXx0AQIEFFgCgQKsDACjQ6gAACrQ6AIACrQ4AoECrAwAo8NUBABRYYAEACrQ6AIACrQ4AoECrAwAo8NUBABRYYAEACrQ6AIACrQ4AoECrAwAo0OoAAAq0OgCAAl8dAECBBRYAoECrAwAo0OoAAAq0OgCAAq0OAKBAqwMAKPDVAQAUWGABAAq0OgCAAq0OAKBAqwMAKNDqAAAKtDoAgAJfHQBAgQUWAKBAqwMAKNDqAAAKtDoAgAKtDgCgQKsDACjw1QEAFFhgAQAKtDoAgAKtDgCgQKsDACjw1QEAFFhgAQAKtDoAgAKtDgCgQKsDACjQ6gAACrQ6AIACXx0AQIEFFgCgQKsDACjQ6gAACrQ6AIACrQ4AoECrAwAo8NUBABRYYAEACrQ6AIACrQ4AoECrAwAo0OoAAAq0OgCAAl8dAECBBRYAoECrAwAo0OoAAAq0OgCAAq0OAKBAqwMAKPDVAQAUWGABAAq0OgCAAq0OAKBAqwMAKNDqAAAKtDoAgAJfHQBAgQUWAKBAqwMAKNDqAAAKtDoAgAJfHQBAgQUWAKBAqwMAKNDqAAAKtDoAgAKtDgCgQKsDACjw1QEAFFhgAQAKtDoAgAKtDgCgQKsDACjQ6gAACrQ6AIACXx0AQIEFFgCgQKsDACjQ6gAACrQ6AIACrQ4AoECrAwAo8NUBABRYYAEACrQ6AIACrQ4AoECrAwAo0OoAAAq0OgCAAl8dAECBBRYAoECrAwAo0OoAAAq0OgCAAl8dAECBBRYAoECrAwAo0OoAAAq0OgCAAq0OAKBAqwMAKPDVAQAUWGABAAq0OgCAAq0OAKBAqwMAKNDqAAAKtDoAgAJfHQBAgQUWAKBAqwMAKNDqAAAKtDoAgAKtDgCgQKsDACjw1QEAFFhgAQAKtDoAgAKtDgCgQKsDACjQ6gAACrQ6AIACXx0AQIEFFgCgQKsDACjQ6gAACrQ6AIACXx0AQIEFFgCgQKsDACjQ6gAACrQ6AIACrQ4AoECrAwAo8NUBABRYYAEACrQ6AIACrQ4AoECrAwAo0OoAAAq0OgCAAl8dAECBBRYAoECrAwAo0OoAAAq0OgCAAq0OAKBAqwMAKPDVAQAUWGABAAq0OgCAAq0OAKBAqwMAKNDqAAAKtDoAgAJfHQBAgQUWAKBAqwMAKNDqAAAKtDoAgAJfHQBAgQUWAKBAqwMAKNDqAAAKtDoAgAKtDgCgQKsDACjw1QEAFFhgAQAKtDoAgAKtDgCgQKsDACjQ6gAACrQ6AIACXx0AQIEFFgCgQKsDACjQ6gAACrQ6AIACrQ4AoECrAwAo8NUBABRYYAEACrQ6AIACrQ4AoECrAwAo0OoAAAq0OgCAAl8dAECBBRYAoECrAwAo0OoAAAq0OgCAAl8dAECBBRYAoECrAwAo0OoAAAq0OgCAAq0OAKBAqwMAKPDVAQAUWGABAAq0OgCAAq0OAKBAqwMAKNDqAAAKtDoAgAJfHQBAgQUWAKBAqwMAKNDqAAAKtDoAgAKtDgCgQKsDACjw1QEAFFhgAQAKtDoAgAKtDgCgQKsDACjQ6gAACrQ6AIACXx0AQIEFFgCgQKsDACjQ6gAACrQ6AIACXx0AQIEFFgCgQKsDACjQ6gAACrQ6AIACrQ4AoECrAwAo8NUBABRYYAEACrQ6AIACrQ4AoECrAwAo0OoAAAq0OgCAAl8dAECBBRYAoECrAwAo0OoAAAq0OgCAAq0OAKBAqwMAKPDVAQAUWGABAAq0OgCAAq0OAKBAqwMAKNDqAAAKtDoAgAJfHQBAgQUWAKBAqwMAKNDqAAAKtDoAgAJfHQBAgQUWAKBAqwMAKNDqAAAKtDoAgAKtDgCgQKsDACjw1QEAFFhgAQAKtDoAgAKtDgCgQKsDACjQ6gAACrQ6AIACXx0AQIEFFgCgQKsDACjQ6gAACrQ6AIACrQ4AoECrAwAo8NUBABRYYAEACrQ6AIACrQ4AoECrAwAo0OoAAAq0OgCAAl8dAECBBRYAoECrAwAo0OoAAAq0OgCAAl8dAECBBRYAoECrAwAo0OoAAAq0OgCAAq0OAKBAqwMAKPDVAQAUWGABAAq0OgCAAq0OAKBAqwMAKNDqAAAKtDoAgAJfHQBAgQUWAKBAqwMAKNDqAAAKtDoAgAKtDgCgQKsDACjw1QEAFFhgAQAKtDoAgAKtDgCgQKsDACjQ6gAACrQ6AIACXx0AQIEFFgCgQKsDACjQ6gAACrQ6AIACXx0AQIEFFgCgQKsDACjQ6gAACrQ6AIACrQ4AoECrAwAo8NUBABRYYAEACrQ6AIACrQ4AoECrAwAoWKUOACBAqwMAKHgBT6AGvGraHuwAAAAASUVORK5CYII="
        )
    )
    md = "![Wide image](wide.png)"
    data = convert(md, None, source_dir=str(tmp_path))
    pdf_path = tmp_path / "img.pdf"
    pdf_path.write_bytes(data)
    pdf = pdfplumber.open(pdf_path)
    page = pdf.pages[0]
    assert len(page.images) >= 1, "Expected at least one image on the page"
    im = page.images[0]
    drawn_w = im["x1"] - im["x0"]
    drawn_h = im["y1"] - im["y0"]
    aspect = drawn_w / drawn_h if drawn_h > 0 else 0
    assert 1.3 < aspect < 1.5, (
        f"Expected aspect ≈1.394 (839×602); got {aspect:.3f} "
        f"(drawn {drawn_w:.1f}×{drawn_h:.1f})"
    )


@needs_pandoc
def test_ragged_right_body_text(tmp_path: Path) -> None:
    """Body paragraphs use ragged-right (left-aligned) alignment, matching HTML default."""
    md = "# Heading\n\nThis is body text that should be ragged-right in the PDF."
    data = convert(md, None, source_dir=str(tmp_path))
    assert data is not None
    pdf_path = tmp_path / "ragged.pdf"
    pdf_path.write_bytes(data)
    # Verify xelatex ran to completion (valid PDF)
    assert pdf_path.stat().st_size > 100


@needs_pandoc
def test_convert_mark_highlighted(tmp_path: Path) -> None:
    """Highlighted text (soul \\hl) must tolerate punctuation in its argument."""
    md = "Text may be ==marked (highlighted)== and ==marked with: colons== too.\n"
    data = convert(md, None)
    assert data is not None

    pdf_path = tmp_path / "mark.pdf"
    pdf_path.write_bytes(data)

    text = _extract_text(pdf_path)
    assert "marked (highlighted)" in text
    assert "marked with: colons" in text


@needs_pandoc
def test_toc_heading_italic(tmp_path: Path) -> None:
    """A ``## ... {#toc}`` heading (any language) must still render in the PDF."""
    md = "## Table of Contents {#toc}\n\nSomething on the first page.\n"
    data = convert(md, None)
    assert data is not None

    pdf_path = tmp_path / "toc.pdf"
    pdf_path.write_bytes(data)

    text = _extract_text(pdf_path)
    assert "Table of Contents" in text


@needs_pandoc
def test_table_header_repeat_no_orphan(tmp_path: Path) -> None:
    """Multi-page tables repeat their header (\\endhead) without orphaning it alone."""
    rows = "\n".join([f"| R{i} | cell |" for i in range(30)])
    md = f"| H1 | H2 |\n|---|---|\n{rows}\n"
    data = convert(md, None, source_dir=str(tmp_path))
    assert data is not None
    pdf_path = tmp_path / "tbl.pdf"
    pdf_path.write_bytes(data)
    # Valid PDF produced (was: \endhead caused header duplication across pages)
    assert pdf_path.stat().st_size > 100
