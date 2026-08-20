import shutil

import pytest

from markdown2pdf_base.converter import (
    DEFAULT_CJK_JP_FONT,
    DEFAULT_CJK_KR_FONT,
    DEFAULT_CJK_ZH_CN_FONT,
    DEFAULT_CJK_ZH_HK_FONT,
    DEFAULT_CJK_ZH_TW_FONT,
    DEFAULT_HEAD_FONT,
    DEFAULT_MAIN_FONT,
    DEFAULT_MONO_FONT,
    _default_cjk_font,
    _extract_metadata,
    _font_available,
    _h6_to_bold_italic_para,
    _inject_css,
    _is_full_document,
    _latex_escape,
    _make_hypersetup,
    _make_latex_header,
    _make_running_header,
    _normalize_quotes,
    _process_html,
    _resolve_image_src,
    _ruby_to_span,
    _select_font,
    _strip_footnote_backref,
    _strip_image_titles,
    _strip_metadata_tags,
    _strip_variation_selectors,
    _wrap_html,
    convert,
    convert_file,
)

# ---------------------------------------------------------------------------
# HTML post-processing helpers
# ---------------------------------------------------------------------------


def test_resolve_image_src_relative():
    html = '<p><img src="img/pic.png" alt="x"></p>'
    result = _resolve_image_src(html, "/home/user/docs")
    assert 'src="/home/user/docs/img/pic.png"' in result


def test_resolve_image_src_absolute_and_remote():
    html = '<p><img src="/abs/pic.png"><img src="https://e.com/a.png"></p>'
    result = _resolve_image_src(html, "/home/user/docs")
    assert result == html


def test_strip_footnote_backref():
    html = (
        '<li id="fn:1">Body <a href="#fnref:1" class="footnote-backref">&uarr;</a></li>'
    )
    assert _strip_footnote_backref(html) == '<li id="fn:1">Body</li>'


def test_strip_image_titles():
    assert (
        _strip_image_titles('<img src="a.png" alt="x" title="Title">')
        == '<img src="a.png" alt="x">'
    )
    assert (
        _strip_image_titles('<img title="T" src="a.png" alt="x">')
        == '<img src="a.png" alt="x">'
    )
    assert (
        _strip_image_titles('<img src="a.png" alt="x">') == '<img src="a.png" alt="x">'
    )


def test_normalize_quotes():
    html = "\u201cHello\u201d and \u2018world\u2019"
    assert _normalize_quotes(html) == "\"Hello\" and 'world'"


def test_strip_variation_selectors():
    assert _strip_variation_selectors("ab\ufe0fcd") == "abcd"
    assert _strip_variation_selectors("&#10084;&#65039;") == "&#10084;"
    assert _strip_variation_selectors("&#x2764;&#xFE0F;") == "&#x2764;"


def test_strip_metadata_tags():
    html = (
        '<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8" />\n'
        '<meta name="author" content="nobus-1967" />\n<title>Doc</title>\n'
        "</head>\n<body></body>\n</html>"
    )
    result = _strip_metadata_tags(html)
    assert "<title>" not in result
    assert "<meta" not in result
    assert "<body></body>" in result


def test_latex_escape():
    assert _latex_escape("a_b#c%d&e") == "a\\_b\\#c\\%d\\&e"
    assert _latex_escape("plain") == "plain"


def test_make_hypersetup():
    result = _make_hypersetup({"title": "My & Doc", "author": "Ada", "lang": "en"})
    assert "pdftitle={My \\& Doc}" in result
    assert "pdfauthor={Ada}" in result
    assert "pdflang={en}" in result
    assert _make_hypersetup({}) == ""


def test_make_running_header():
    assert (
        _make_running_header(
            {"title": "Doc", "author": "Ada", "published": "2026-08-09"}
        )
        == "\\textbf{Doc} (\\textit{Ada}: 2026-08-09)"
    )
    assert (
        _make_running_header({"title": "Doc", "author": "Ada"})
        == "\\textbf{Doc} (\\textit{Ada})"
    )
    assert _make_running_header({"title": "Doc"}) == "\\textbf{Doc}"
    assert _make_running_header({}) == ""
    assert _make_running_header({"title": "My & Doc"}) == "\\textbf{My \\& Doc}"


def test_ruby_to_span():
    html = "<ruby>\u6f22<rp>(</rp><rt>\u304b\u3093</rt><rp>)</rp></ruby>"
    assert _ruby_to_span(html) == ('<span class="ruby" rt="\u304b\u3093">\u6f22</span>')


def test_h6_to_bold_italic_para():
    assert _h6_to_bold_italic_para("<h6>Note</h6>") == (
        "<p><strong><em>Note</em></strong></p>"
    )


def test_h6_to_bold_italic_para_keeps_anchor():
    result = _h6_to_bold_italic_para('<h6 id="others">Others</h6>')
    assert result == '<a id="others"></a><p><strong><em>Others</em></strong></p>'


# ---------------------------------------------------------------------------
# Document assembly
# ---------------------------------------------------------------------------


def test_is_full_document():
    assert _is_full_document("<!doctype html>\n<html>")
    assert _is_full_document('<html lang="en">')
    assert not _is_full_document("<h1>Title</h1>")


def test_extract_metadata():
    html = """<!doctype html>
<html lang="ja">
<head>
<meta charset="utf-8" />
<meta name="author" content="nobus-1967" />
<meta name="keywords" content="a, b" />
<title>My Doc</title>
</head>
<body></body>
</html>"""
    metadata = _extract_metadata(html)
    assert metadata["title"] == "My Doc"
    assert metadata["author"] == "nobus-1967"
    assert metadata["keywords"] == "a, b"
    assert "lang" not in metadata


def test_wrap_html_fragment():
    html = _wrap_html("<p>Hello</p>", "en", DEFAULT_MAIN_FONT, DEFAULT_MONO_FONT)
    assert html.startswith("<!DOCTYPE html>")
    assert '<html lang="en">' in html
    assert "<p>Hello</p>" in html


def test_inject_css_into_full_document():
    html = '<!doctype html>\n<html lang="en">\n<head>\n</head>\n<body></body>\n</html>'
    result = _inject_css(html, DEFAULT_MAIN_FONT, DEFAULT_MONO_FONT)
    assert "<style>" in result
    assert result.count("<head>") == 1
    assert result.count("<html") == 1


def test_process_html_full_document_no_nesting():
    full = (
        '<!doctype html>\n<html lang="en">\n<head>\n<title>Doc</title>\n'
        "</head>\n<body>\n<p>Body</p>\n</body>\n</html>"
    )
    processed, metadata = _process_html(
        full, None, "en", DEFAULT_MAIN_FONT, DEFAULT_MONO_FONT
    )
    assert metadata["title"] == "Doc"
    assert processed.count("<html") == 1
    assert "<p>Body</p>" in processed
    assert "<title>" not in processed


def test_process_html_strips_metadata_keeps_body():
    full = (
        '<!doctype html>\n<html lang="en">\n<head>\n'
        '<meta name="author" content="nobus-1967" />\n<title>Doc</title>\n'
        "</head>\n<body>\n<p>Body</p>\n</body>\n</html>"
    )
    processed, metadata = _process_html(
        full, None, "en", DEFAULT_MAIN_FONT, DEFAULT_MONO_FONT
    )
    assert metadata["author"] == "nobus-1967"
    assert metadata["title"] == "Doc"
    assert "<title>" not in processed
    assert "<meta" not in processed
    assert "<p>Body</p>" in processed


def test_process_html_fragment_wrapped():
    fragment = "<h1>Hi</h1>"
    processed, metadata = _process_html(
        fragment, None, "ja", DEFAULT_MAIN_FONT, DEFAULT_MONO_FONT
    )
    assert metadata == {}
    assert '<html lang="ja">' in processed
    assert "<h1>Hi</h1>" in processed


# ---------------------------------------------------------------------------
# Font selection
# ---------------------------------------------------------------------------


def test_default_cjk_font_by_lang():
    assert _default_cjk_font("ja") == DEFAULT_CJK_JP_FONT
    assert _default_cjk_font("zh-CN") == DEFAULT_CJK_ZH_CN_FONT
    assert _default_cjk_font("zh-Hans") == DEFAULT_CJK_ZH_CN_FONT
    assert _default_cjk_font("zh-TW") == DEFAULT_CJK_ZH_TW_FONT
    assert _default_cjk_font("zh-Hant") == DEFAULT_CJK_ZH_TW_FONT
    assert _default_cjk_font("zh-HK") == DEFAULT_CJK_ZH_HK_FONT
    assert _default_cjk_font("ko") == DEFAULT_CJK_KR_FONT
    assert _default_cjk_font("en") == DEFAULT_CJK_JP_FONT
    assert _default_cjk_font(None) == DEFAULT_CJK_JP_FONT


def test_select_font_keeps_available_font():
    if not _font_available(DEFAULT_MAIN_FONT):
        pytest.skip("Noto Sans not installed")
    assert _select_font(DEFAULT_MAIN_FONT, []) == DEFAULT_MAIN_FONT


def test_make_latex_header_uses_head_font():
    header = _make_latex_header(
        "Noto Serif",
        "Noto Sans CJK JP",
        "Noto Sans Mono",
        "Symbola",
        head_font=DEFAULT_HEAD_FONT,
    )
    assert r"\newfontfamily{\headfont}{Noto Sans}" in header
    assert r"\titleformat{\section}" in header


def test_select_font_falls_back_on_missing():
    with pytest.warns(UserWarning):
        chosen = _select_font("Definitely Not A Font 12345", ["Arial"])
    assert chosen in ("Definitely Not A Font 12345", "Arial")


# ---------------------------------------------------------------------------
# Full conversion (requires pandoc + xelatex)
# ---------------------------------------------------------------------------

needs_pandoc = pytest.mark.skipif(
    shutil.which("pandoc") is None, reason="pandoc not installed"
)


@needs_pandoc
def test_convert_file_produces_pdf(tmp_path):
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
def test_convert_returns_pdf_bytes(tmp_path):
    md = "# Hello\n\nSome **bold** text."
    data = convert(md, None)
    assert data is not None
    assert data.startswith(b"%PDF")
    assert len(data) > 1000


@needs_pandoc
def test_convert_front_matter_metadata_in_pdf(tmp_path):
    import subprocess

    md = "---\ntitle: Front Matter Doc\nauthor: Ada\ndescription: D\npublished: 2026-08-09\n---\n# Body\n\nText.\n"
    data = convert(md, None)
    assert data is not None
    pdf_path = tmp_path / "out.pdf"
    pdf_path.write_bytes(data)
    text = subprocess.run(
        ["pdftotext", str(pdf_path), "-"],
        capture_output=True,
        text=True,
        check=False,
    ).stdout
    assert "Front Matter Doc (Ada: 2026-08-09)" in text
    assert text.startswith("Front Matter Doc (Ada: 2026-08-09)")
    info = subprocess.run(
        ["pdfinfo", str(pdf_path)],
        capture_output=True,
        text=True,
        check=False,
    ).stdout
    assert "Title:           Front Matter Doc" in info
    assert "Author:          Ada" in info


@needs_pandoc
def test_convert_japanese_ruby(tmp_path):
    md = "# \u30bf\u30a4\u30c8\u30eb\n\n{\u6f22|\u304b\u3093}\n"
    data = convert(md, None, lang="ja")
    assert data is not None
    assert data.startswith(b"%PDF")


@needs_pandoc
def test_convert_inline_code_special_chars(tmp_path):
    import subprocess

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
    text = subprocess.run(
        ["pdftotext", str(pdf_path), "-"],
        capture_output=True,
        text=True,
        check=False,
    ).stdout
    assert "a_b.c%#d&$" in text
    assert "x^y" in text
    assert "a~b" in text
    assert "foo\\bar" in text
    assert "foo_bar.baz" in text


@needs_pandoc
def test_convert_inline_code_in_heading(tmp_path):
    import subprocess

    # seqsplit is unsafe in moving arguments (bookmarks/toc); heading code
    # must render as plain texttt without seqsplit.
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
    text = subprocess.run(
        ["pdftotext", str(pdf_path), "-"],
        capture_output=True,
        text=True,
        check=False,
    ).stdout
    assert "Title <code>markdown2html5-base</code>" in text
    assert "x^y" in text
    assert "foo_bar" in text


@needs_pandoc
def test_convert_code_lang_label(tmp_path):
    import subprocess

    md = '```python\nprint("Hello")\n```\n'
    data = convert(md, None)
    assert data is not None
    pdf_path = tmp_path / "codelang.pdf"
    pdf_path.write_bytes(data)
    text = subprocess.run(
        ["pdftotext", str(pdf_path), "-"],
        capture_output=True,
        text=True,
        check=False,
    ).stdout
    assert "/python/" in text
    assert 'print("Hello")' in text
