from __future__ import annotations

import os
import re
import subprocess
import sys
import tempfile
import warnings

from markdown2html5_base import MarkdownToHTML

DEFAULT_MAIN_FONT = "Noto Sans"
DEFAULT_MONO_FONT = "Noto Sans Mono"
DEFAULT_CJK_JP_FONT = "Noto Sans CJK JP"
DEFAULT_CJK_SC_FONT = "Noto Sans CJK SC"
DEFAULT_CJK_TC_FONT = "Noto Sans CJK TC"
DEFAULT_SYMBOL_FONT = "Symbola"

MAIN_FONT_FALLBACKS = [
    "Noto Sans",
    "DejaVu Sans",
    "Liberation Sans",
    "FreeSans",
]

MONO_FONT_FALLBACKS = [
    "Noto Sans Mono",
    "DejaVu Sans Mono",
    "Liberation Mono",
    "FreeMono",
]

CJK_JP_FALLBACKS = [
    "Noto Sans CJK JP",
    "Source Han Sans JP",
    "Sarasa Gothic",
    "IPAPGothic",
]

CJK_SC_FALLBACKS = [
    "Noto Sans CJK SC",
    "Source Han Sans SC",
    "Sarasa Gothic SC",
    "I.Ming",
]

CJK_TC_FALLBACKS = [
    "Noto Sans CJK TC",
    "Source Han Sans TC",
    "Sarasa Gothic TC",
    "I.Ming",
]

SYMBOL_FONT_FALLBACKS = [
    "Symbola",
    "Noto Sans Symbols",
    "DejaVu Sans",
]

_CSS = """\
  body {{ font-family: "{main}", sans-serif; font-size: 11pt; line-height: 1.6; max-width: 42em; margin: 2em auto; padding: 0 1em; }}
  pre, code {{ font-family: "{mono}", monospace; font-size: 9.5pt; }}
  pre {{ background: #f5f5f5; padding: 0.8em; border-radius: 4px; overflow-x: auto; }}
  code {{ background: #f0f0f0; padding: 0.15em 0.3em; border-radius: 3px; }}
  pre code {{ background: none; padding: 0; }}
  table {{ border-collapse: collapse; width: 100%; margin: 1em 0; }}
  th, td {{ border: 1px solid #ccc; padding: 0.4em 0.6em; text-align: left; }}
  th {{ background: #eee; }}
  blockquote {{ margin: 0.5em 0; padding: 0.2em 1em; border-left: 4px solid #ccc; color: #555; }}
  hr {{ border: none; border-top: 2px solid #ccc; margin: 1.5em 0; }}
  img {{ max-width: 100%; }}
  .footnotes {{ margin-top: 2em; font-size: 0.9em; color: #666; }}
  mark {{ background: #ffec8b; padding: 0.1em 0.2em; }}
  s {{ color: #999; }}
  sub {{ font-size: 0.75em; }}
  sup {{ font-size: 0.75em; }}
  ins {{ text-decoration: underline; }}
  dl {{ margin: 0.5em 0; }}
  dt {{ font-weight: bold; margin-top: 0.3em; }}
  dd {{ margin-left: 1.5em; }}
  a {{ text-decoration: underline; font-style: italic; }}
  ruby {{ ruby-align: center; }}
  rp {{ display: none; }}
"""

_LATEX_PREAMBLE = r"""\usepackage[margin=25.4mm]{geometry}
\usepackage{fancyhdr}
\usepackage{fontspec}
\usepackage{xeCJK}
\usepackage{newunicodechar}
\usepackage{ruby}
\usepackage{framed}
\usepackage{fancyvrb}
\definecolor{shadecolor}{RGB}{245,245,245}
\definecolor{codegray}{RGB}{245,245,245}
\definecolor{codeframe}{RGB}{180,180,180}
\definecolor{headgray}{RGB}{90,90,90}
\makeatletter
\newenvironment{ShadedVerbatim}{%%
  \VerbatimEnvironment
  \begin{Verbatim}[frame=single, rulecolor=\color{codeframe}]%%
}{%%
  \end{Verbatim}%%
}
\let\verbatim\ShadedVerbatim
\let\endverbatim\endShadedVerbatim
\makeatother
\let\oldtexttt\texttt
\renewcommand{\texttt}[1]{\colorbox{codegray}{\oldtexttt{#1}}}
\renewcommand{\rubysep}{0.3ex}
\newunicodechar{^^^^2026}{\ldots}
\newunicodechar{^^^^22ef}{\ldots}
%s
%s
%s
\newfontfamily{\symbolfont}{%s}
\pagestyle{fancy}
\fancyhf{}
\fancyhead[C]{%s}
\fancyfoot[C]{\thepage}
\renewcommand{\headrulewidth}{0pt}
\AtBeginDocument{%%
\ifcsname Shaded\endcsname
  \renewenvironment{Shaded}{\begin{snugshade}}{\end{snugshade}}%%
\fi
%s
\let\oldhref\href
\renewcommand{\href}[2]{\oldhref{#1}{\underline{\textcolor{blue}{{#2}}}}}%%
}
"""


def _latex_escape(value: str) -> str:
    replacements = {
        "\\": r"\textbackslash{}",
        "{": r"\{",
        "}": r"\}",
        "%": r"\%",
        "#": r"\#",
        "&": r"\&",
        "_": r"\_",
        "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
    }
    return "".join(replacements.get(ch, ch) for ch in value)


def _make_hypersetup(metadata: dict[str, str]) -> str:
    mapping = {
        "title": "pdftitle",
        "author": "pdfauthor",
        "description": "pdfsubject",
        "keywords": "pdfkeywords",
        "lang": "pdflang",
    }
    fields = []
    for key, option in mapping.items():
        value = metadata.get(key)
        if value:
            fields.append(f"{option}={{{_latex_escape(value)}}}")
    if not fields:
        return ""
    return "\\hypersetup{" + ", ".join(fields) + "}"


def _make_running_header(metadata: dict[str, str]) -> str:
    title = metadata.get("title")
    author = metadata.get("author")
    published = metadata.get("published")
    if not (title or author or published):
        return ""
    parts = []
    if title:
        parts.append(r"\textbf{" + _latex_escape(title) + "}")
    suffix = []
    if author:
        suffix.append(r"\textit{" + _latex_escape(author) + "}")
    if published:
        suffix.append(_latex_escape(published))
    if suffix:
        parts.append("(" + ": ".join(suffix) + ")")
    return r"\textcolor{headgray}{" + " ".join(parts) + "}"


def _guard_font_set(set_command: str, chain: list[str]) -> str:
    chain = list(dict.fromkeys(chain))
    if len(chain) == 1:
        return f"\\{set_command}{{{chain[0]}}}"
    head = "".join(
        f"\\IfFontExistsTF{{{name}}}{{\\{set_command}{{{name}}}}}{{"
        for name in chain[:-1]
    )
    tail = f"\\{set_command}{{{chain[-1]}}}"
    return head + tail + "}" * (len(chain) - 1)


_LUA_FILTER_CODE = """local symbol_blocks = {
  {0x2190, 0x21FF}, -- Arrows
  {0x2200, 0x22FF}, -- Mathematical Operators
  {0x2300, 0x23FF}, -- Miscellaneous Technical
  {0x25A0, 0x25FF}, -- Geometric Shapes
  {0x2600, 0x26FF}, -- Miscellaneous Symbols
  {0x2700, 0x27BF}, -- Dingbats
  {0x2B00, 0x2BFF}, -- Misc Symbols and Arrows
  {0x1F300, 0x1F5FF}, -- Misc Symbols and Pictographs
  {0x1F600, 0x1F64F}, -- Emoticons
  {0x1F680, 0x1F6FF}, -- Transport
  {0x1F700, 0x1F77F}, -- Alchemical
  {0x1F900, 0x1F9FF}, -- Supplemental Symbols
}

local function is_symbol(ch)
  if ch:byte() < 0x80 then return false end
  local n = utf8.codepoint(ch)
  for _, r in ipairs(symbol_blocks) do
    if n >= r[1] and n <= r[2] then return true end
  end
  return false
end

local function wrap_symbols(text)
  local out = pandoc.List()
  local buf = ''
  local function flush()
    if buf ~= '' then
      out:insert(pandoc.Str(buf))
      buf = ''
    end
  end
  for ch in text:gmatch('.[\\128-\\191]*') do
    if is_symbol(ch) then
      flush()
      out:insert(pandoc.RawInline('latex', '{\\\\symbolfont{' .. ch .. '}}'))
    else
      buf = buf .. ch
    end
  end
  flush()
  return out
end

function Str(el)
  local out = wrap_symbols(el.text)
  if #out == 1 and out[1].t == 'Str' and out[1].text == el.text then
    return nil
  end
  return out
end

function Span(el)
  local rt = el.attributes['rt']
  if rt then
    el.attributes['rt'] = nil
    local base = pandoc.utils.stringify(el.content)
    local cjk = '%s'
    return pandoc.RawInline('latex', '{\\\\CJKfontspec{' .. cjk .. '}\\\\ruby{' .. base .. '}{' .. rt .. '}}')
  end
end
"""

_FILTER_PATH = os.path.join(tempfile.gettempdir(), "md2pdf_filters.lua")

_FULL_DOC_RE = re.compile(r"^\s*<(?:!doctype html|html(?:\s|>))", re.IGNORECASE)

_META_RE = {
    "author": re.compile(r'<meta name="author" content="([^"]*)"'),
    "description": re.compile(r'<meta name="description" content="([^"]*)"'),
    "keywords": re.compile(r'<meta name="keywords" content="([^"]*)"'),
    "published": re.compile(r'<meta name="published" content="([^"]*)"'),
}
_TITLE_RE = re.compile(r"<title>(.*?)</title>", re.DOTALL)


# ---------------------------------------------------------------------------
# Font helpers
# ---------------------------------------------------------------------------


def _font_available(family: str) -> bool:
    try:
        result = subprocess.run(
            ["fc-list", f":family={family}"],
            capture_output=True,
            text=True,
            check=False,
            timeout=15,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return True
    return bool(result.stdout.strip())


def _select_font(family: str, fallbacks: list[str]) -> str:
    chain = [family, *[f for f in fallbacks if f != family]]
    for name in chain:
        if _font_available(name):
            if name != family:
                warnings.warn(
                    f"Font '{family}' not found; using '{name}' instead.",
                    stacklevel=3,
                )
            return name
    return family


def _cjk_fallback_chain(lang: str | None) -> list[str]:
    lang = (lang or "").lower()
    if lang.startswith("zh"):
        if lang.startswith(("zh-hant", "zh-tw", "zh-hk", "zh-mo")):
            return CJK_TC_FALLBACKS
        return CJK_SC_FALLBACKS
    return CJK_JP_FALLBACKS


def _default_cjk_font(lang: str | None) -> str:
    if (lang or "").lower().startswith("zh"):
        if (lang or "").lower().startswith(("zh-hant", "zh-tw", "zh-hk", "zh-mo")):
            return DEFAULT_CJK_TC_FONT
        return DEFAULT_CJK_SC_FONT
    return DEFAULT_CJK_JP_FONT


# ---------------------------------------------------------------------------
# HTML post-processing helpers
# ---------------------------------------------------------------------------


def _resolve_image_src(html: str, source_dir: str) -> str:
    def _abs(m: re.Match) -> str:
        src = m.group(1)
        if src.startswith(("http://", "https://", "data:", "/")):
            return m.group(0)
        resolved = os.path.normpath(os.path.join(source_dir, src))
        return m.group(0).replace(f'src="{src}"', f'src="{resolved}"')

    return re.sub(r'src="([^"]+)"', _abs, html)


def _strip_footnote_backref(html: str) -> str:
    return re.sub(r'\s*<a[^>]*class="footnote-backref"[^>]*>.*?</a>', "", html)


def _normalize_quotes(html: str) -> str:
    return (
        html.replace("\u201c", '"')
        .replace("\u201d", '"')
        .replace("\u2018", "'")
        .replace("\u2019", "'")
    )


def _strip_variation_selectors(html: str) -> str:
    html = html.replace("\ufe0f", "")
    return re.sub(r"&#65039;|&#x[fF][eE]0[fF];", "", html)


def _ruby_to_span(html: str) -> str:
    return re.sub(
        r"<ruby>([^<]+)<rp>\(</rp><rt>([^<]+)</rt><rp>\)</rp></ruby>",
        lambda m: f'<span class="ruby" rt="{m.group(2)}">{m.group(1)}</span>',
        html,
    )


def _is_html(text: str) -> bool:
    return text.strip().startswith("<")


def _strip_metadata_tags(html: str) -> str:
    html = re.sub(r"<title[^>]*>.*?</title>", "", html, flags=re.DOTALL | re.IGNORECASE)
    return re.sub(r"<meta[^>]*>", "", html, flags=re.IGNORECASE)


def _is_full_document(html: str) -> bool:
    return bool(_FULL_DOC_RE.match(html))


def _h6_to_bold_italic_para(html: str) -> str:
    return re.sub(
        r"<h6([^>]*)>(.*?)</h6>",
        lambda m: f"<p{m.group(1)}><strong><em>{m.group(2)}</em></strong></p>",
        html,
        flags=re.DOTALL,
    )


# ---------------------------------------------------------------------------
# Document assembly
# ---------------------------------------------------------------------------


def _extract_metadata(html: str) -> dict[str, str]:
    metadata: dict[str, str] = {}
    title = _TITLE_RE.search(html)
    if title:
        metadata["title"] = title.group(1).strip()
    for key, pattern in _META_RE.items():
        match = pattern.search(html)
        if match:
            metadata[key] = match.group(1)
    return metadata


def _wrap_html(body: str, lang: str, main: str, mono: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="{lang}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
{_CSS.format(main=main, mono=mono)}
</style>
</head>
<body>
{body}
</body>
</html>"""


def _inject_css(full_html: str, main: str, mono: str) -> str:
    style = _CSS.format(main=main, mono=mono)
    return re.sub(
        r"<head>",
        f"<head>\n<style>\n{style}</style>",
        full_html,
        count=1,
    )


def _make_latex_header(
    main_font: str,
    cjk_font: str,
    mono_font: str,
    symbol_font: str,
    main_chain: list[str] | None = None,
    cjk_chain: list[str] | None = None,
    mono_chain: list[str] | None = None,
    pdf_metadata: dict[str, str] | None = None,
) -> str:
    main_decl = _guard_font_set("setmainfont", main_chain or [main_font])
    cjk_decl = _guard_font_set("setCJKmainfont", cjk_chain or [cjk_font])
    mono_decl = _guard_font_set("setmonofont", mono_chain or [mono_font])
    hypersetup = _make_hypersetup(pdf_metadata or {})
    running_header = _make_running_header(pdf_metadata or {})
    return _LATEX_PREAMBLE % (
        main_decl,
        cjk_decl,
        mono_decl,
        symbol_font,
        running_header,
        hypersetup,
    )


def _write_lua_filter(path: str, cjk_font: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        f.write(_LUA_FILTER_CODE % cjk_font)


# ---------------------------------------------------------------------------
# Pandoc bridge
# ---------------------------------------------------------------------------


def _pandoc_html_to_pdf(
    html_path: str,
    pdf_path: str,
    *,
    metadata: dict[str, str] | None = None,
    main_font: str,
    cjk_font: str,
    mono_font: str,
    symbol_font: str,
    main_chain: list[str],
    cjk_chain: list[str],
    mono_chain: list[str],
) -> None:
    header = _make_latex_header(
        main_font,
        cjk_font,
        mono_font,
        symbol_font,
        main_chain=main_chain,
        cjk_chain=cjk_chain,
        mono_chain=mono_chain,
        pdf_metadata=metadata,
    )
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".tex", delete=False, encoding="utf-8"
    ) as f:
        header_path = f.name
        f.write(header)

    _write_lua_filter(_FILTER_PATH, cjk_font)

    try:
        cmd = [
            "pandoc",
            html_path,
            "-o",
            pdf_path,
            "--pdf-engine=xelatex",
            "-H",
            header_path,
            "--lua-filter",
            _FILTER_PATH,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if result.returncode != 0:
            msg = (
                result.stderr.strip()
                or result.stdout.strip()
                or f"pandoc exited with code {result.returncode}"
            )
            raise RuntimeError(f"pandoc failed: {msg}")
        if result.stderr:
            print(result.stderr, file=sys.stderr)
    finally:
        os.unlink(header_path)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def _process_html(
    html_body: str,
    source_dir: str | None,
    lang: str,
    main: str,
    mono: str,
) -> tuple[str, dict[str, str]]:
    if _is_full_document(html_body):
        metadata = _extract_metadata(html_body)
        full = _inject_css(_strip_metadata_tags(html_body), main, mono)
    else:
        metadata = {}
        full = _wrap_html(html_body, lang, main, mono)

    if source_dir:
        full = _resolve_image_src(full, source_dir)
    full = _normalize_quotes(full)
    full = _strip_footnote_backref(full)
    full = _strip_variation_selectors(full)
    full = _ruby_to_span(full)
    full = _h6_to_bold_italic_para(full)
    return full, metadata


def convert(
    markdown_text: str,
    output_path: str | None = None,
    *,
    source_dir: str | None = None,
    lang: str | None = None,
    main_font: str | None = None,
    cjk_font: str | None = None,
    mono_font: str | None = None,
    symbol_font: str | None = None,
) -> bytes | None:
    html_body = (
        markdown_text
        if _is_html(markdown_text)
        else MarkdownToHTML().convert(markdown_text)
    )

    doc_lang = lang or _extract_lang(html_body)
    effective_cjk = cjk_font or _default_cjk_font(doc_lang)
    cjk_chain = _cjk_fallback_chain(doc_lang)

    main = _select_font(main_font or DEFAULT_MAIN_FONT, MAIN_FONT_FALLBACKS)
    cjk = _select_font(effective_cjk, cjk_chain)
    mono = _select_font(mono_font or DEFAULT_MONO_FONT, MONO_FONT_FALLBACKS)
    symbol = _select_font(symbol_font or DEFAULT_SYMBOL_FONT, SYMBOL_FONT_FALLBACKS)

    full_html, metadata = _process_html(
        html_body, source_dir, doc_lang or "en", main, mono
    )
    if doc_lang:
        metadata["lang"] = doc_lang

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".html", delete=False, encoding="utf-8"
    ) as f:
        html_path = f.name
        f.write(full_html)

    kwargs = {
        "metadata": metadata,
        "main_font": main,
        "cjk_font": cjk,
        "mono_font": mono,
        "symbol_font": symbol,
        "main_chain": [main, *MAIN_FONT_FALLBACKS],
        "cjk_chain": [cjk, *cjk_chain],
        "mono_chain": [mono, *MONO_FONT_FALLBACKS],
    }

    try:
        if output_path:
            _pandoc_html_to_pdf(html_path, output_path, **kwargs)
            return None

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            pdf_path = tmp.name
        _pandoc_html_to_pdf(html_path, pdf_path, **kwargs)
        with open(pdf_path, "rb") as f:
            return f.read()
    finally:
        os.unlink(html_path)
        if output_path is None:
            os.unlink(pdf_path)


def convert_file(
    input_path: str,
    output_path: str | None = None,
    *,
    lang: str | None = None,
    main_font: str | None = None,
    cjk_font: str | None = None,
    mono_font: str | None = None,
    symbol_font: str | None = None,
) -> bytes | None:
    with open(input_path, encoding="utf-8") as f:
        text = f.read()
    source_dir = os.path.dirname(os.path.abspath(input_path))
    return convert(
        text,
        output_path,
        source_dir=source_dir,
        lang=lang,
        main_font=main_font,
        cjk_font=cjk_font,
        mono_font=mono_font,
        symbol_font=symbol_font,
    )


def _extract_lang(html: str) -> str | None:
    match = re.search(r'<html[^>]*\blang="([^"]*)"', html)
    return match.group(1) if match else None
