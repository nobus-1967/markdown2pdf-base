from __future__ import annotations

import os
import re
import subprocess
import sys
import tempfile
import warnings

from markdown2html5_base import MarkdownToHTML

DEFAULT_MAIN_FONT = "Noto Serif"
DEFAULT_HEAD_FONT = "Noto Sans"
DEFAULT_MONO_FONT = "Noto Sans Mono"
DEFAULT_CJK_JP_FONT = "Noto Serif CJK JP"
DEFAULT_CJK_ZH_CN_FONT = "Noto Serif CJK SC"
DEFAULT_CJK_ZH_TW_FONT = "Noto Serif CJK TC"
DEFAULT_CJK_ZH_HK_FONT = "Noto Serif CJK HK"
DEFAULT_CJK_KR_FONT = "Noto Serif CJK KR"
DEFAULT_SYMBOL_FONT = "Symbola"

_CSS = """\
  body {{ font-family: "{main}", sans-serif; font-size: 11pt; line-height: 1.6; max-width: 42em; margin: 2em auto; padding: 0 1em; }}
  pre, code {{ font-family: "{mono}", monospace; font-size: 9.5pt; }}
  pre {{ background: #f5f5f5; padding: 0.8em; border-radius: 4px; overflow-x: auto; }}
  code {{ background: #f0f0f0; padding: 0.15em 0.3em; border-radius: 3px; }}
  pre code {{ background: none; padding: 0; }}
  div.code-lang {{ font-family: "{mono}", monospace; font-size: 9pt; color: #666; margin: 0; padding: 0.2em 0; }}
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
\usepackage{fvextra}
\usepackage{titlesec}
\usepackage{mdframed}
\usepackage{colortbl}
\usepackage{longtable}
\setlength{\LTleft}{0pt}
\setlength{\LTright}{\fill}
\usepackage{array}
\renewcommand{\arraystretch}{1.5}
\usepackage{xltabular}
\usepackage{ragged2e}
\newcolumntype{L}{>{\RaggedRight\arraybackslash}X}
\newcolumntype{C}{>{\Centering\arraybackslash}X}
\newcolumntype{R}{>{\RaggedLeft\arraybackslash}X}
\definecolor{shadecolor}{RGB}{245,245,245}
\mdfdefinestyle{codelangbox}{%%
  linecolor=black, linewidth=0.6pt,
  frametitlefont=\small\bfseries\ttfamily\color{white},
  frametitlebackgroundcolor=black,
  backgroundcolor=shadecolor,
  innertopmargin=4pt, innerbottommargin=4pt,
  innerleftmargin=6pt, innerrightmargin=6pt,
  skipabove=6pt, skipbelow=6pt,
}
\makeatletter
\newenvironment{ShadedVerbatim}{%%
  \VerbatimEnvironment
  \begin{mdframed}[style=codelangbox]\begin{Verbatim}[frame=none, breaklines, breaksymbolleft={}, vspace=0pt]%%
}{%%
  \end{Verbatim}\end{mdframed}%%
}
\let\verbatim\ShadedVerbatim
\let\endverbatim\endShadedVerbatim
\makeatother
\renewenvironment{quote}{%%
  \begin{mdframed}[leftline=true, rightline=false, topline=false, bottomline=false,
    linecolor=shadecolor, linewidth=10pt,
    innerleftmargin=20pt, innerrightmargin=0pt,
    innertopmargin=4pt, innerbottommargin=4pt,
    leftmargin=0pt, rightmargin=0pt, skipabove=6pt, skipbelow=6pt]
}{%%
  \end{mdframed}%%
}
\emergencystretch=1.5em
\hyphenpenalty=10000
\exhyphenpenalty=10000
\usepackage{soul}
\sethlcolor{shadecolor}
\soulregister{\textless}{1}
\soulregister{\textgreater}{1}
\soulregister{\textbackslash}{1}
\soulregister{\textasciitilde}{1}
\soulregister{\textasciicircum}{1}
\soulregister{\slash}{0}
\soulregister{\allowbreak}{0}
\newcommand{\markhl}[1]{\sethlcolor{yellow}\hl{#1}\sethlcolor{shadecolor}}
\renewcommand{\rubysep}{0.3ex}
\newunicodechar{^^^^2026}{\ldots}
\newunicodechar{^^^^22ef}{\ldots}
%s
%s
%s
\newfontfamily{\headfont}{%s}
\titleformat{\section}{\Large\bfseries\headfont}{\thesection}{1em}{}
\titleformat{\subsection}{\large\bfseries\headfont}{\thesubsection}{1em}{}
\titleformat{\subsubsection}{\normalsize\bfseries\headfont}{\thesubsubsection}{1em}{}
\titleformat{\paragraph}{\normalsize\bfseries\headfont}{\theparagraph}{1em}{}
\titleformat{\subparagraph}{\normalsize\bfseries\headfont}{\thesubparagraph}{1em}{}
\newcommand{\useSymbolFont}[1]{%%
  \IfFontExistsTF{#1}{%%
    \newfontfamily{\symbolfont}{#1}%%
  }{%%
    \newfontfamily{\symbolfont}{Symbola}%%
  }%%
}
\useSymbolFont{%s}
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
    return " ".join(parts)


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

local code_escapes = {
  ['\\\\'] = '\\\\textbackslash{}',
  ['{'] = '\\\\{',
  ['}'] = '\\\\}',
  ['$'] = '\\\\$',
  ['&'] = '\\\\&',
  ['#'] = '\\\\#',
  ['_'] = '\\\\_',
  ['%%'] = '\\\\%%',
  ['^'] = '\\\\textasciicircum{}',
  ['~'] = '\\\\textasciitilde{}',
  ['<'] = '<',
  ['>'] = '>',
}

local function latex_escape_code(text)
  local out = {}
  for ch in text:gmatch('.[\\128-\\191]*') do
    out[#out + 1] = code_escapes[ch] or ch
  end
  return table.concat(out)
end

local hdr_walker = {
  Code = function(el)
    return pandoc.RawInline('latex',
      '\\\\texttt{' .. latex_escape_code(el.text) .. '}')
  end,
}
local function breakable_code(escaped)
  -- Insert \allowbreak (a penalty node, unaffected by \\hyphenpenalty) after
  -- every token so TeX can break long code runs anywhere instead of
  -- overflowing the line. Tokens are single characters, \\macro or
  -- \\macro{} groups, and multibyte (CJK) characters.
  local out = {}
  local i = 1
  while i <= #escaped do
    local tok
    local c = escaped:sub(i, i)
    if c == '\\\\' then
      local j = i + 1
      local ch = escaped:sub(j, j)
      if ch:match('[a-zA-Z]') then
        local k = j
        while escaped:sub(k, k):match('[a-zA-Z]') do k = k + 1 end
        tok = escaped:sub(i, k - 1)
        local rest = escaped:sub(k)
        if rest:sub(1, 1) == '{' then
          local close = rest:find('}', 2)
          tok = tok .. rest:sub(1, close)
        end
      else
        tok = escaped:sub(i, i + 1)
      end
    else
      local nb = 1
      local b = escaped:byte(i)
      if b >= 240 then nb = 4 elseif b >= 224 then nb = 3 elseif b >= 192 then nb = 2 end
      tok = escaped:sub(i, i + nb - 1)
    end
    out[#out + 1] = tok
    out[#out + 1] = '\\\\allowbreak{}'
    i = i + #tok
  end
  return table.concat(out)
end

local function code_latex(el)
  local escaped = latex_escape_code(el.text)
  -- All inline code renders as breakable plain monospace text with no
  -- background. \allowbreak (a penalty node) is inserted after every token
  -- so long runs wrap anywhere instead of overflowing tables and paragraphs.
  return '\\\\texttt{' .. breakable_code(escaped) .. '}'
end
local function code_emit(el)
  return pandoc.RawInline('latex', code_latex(el))
end
local body_walker = {
  Code = code_emit,
  HorizontalRule = function()
    return pandoc.RawBlock('latex', '\\\\noindent\\\\rule{\\\\linewidth}{0.4pt}')
  end,
  Mark = function(el)
    return pandoc.RawInline('latex', '\\\\markhl{' .. serialize_inlines(el.content) .. '}')
  end,
}

local function has_class(el, name)
  for _, c in ipairs(el.classes) do
    if c == name then return true end
  end
  return false
end

local function latex_escape_text(s)
  s = s:gsub('\\\\', '\\\\textbackslash{}')
  s = s:gsub('([{}$&#_%%%%])', '\\\\%%1')
  s = s:gsub('~', '\\\\textasciitilde{}')
  s = s:gsub('%%^', '\\\\textasciicircum{}')
  return s
end

local function inline_latex(inl)
  if inl.t == 'Str' then return latex_escape_text(inl.text) end
  if inl.t == 'RawInline' then return inl.text end
  if inl.t == 'Code' then return code_latex(inl) end
  if inl.t == 'Space' or inl.t == 'SoftBreak' then return ' ' end
  if inl.t == 'Strong' then
    return '\\\\textbf{' .. serialize_inlines(inl.content) .. '}'
  end
  if inl.t == 'Emph' then
    return '\\\\emph{' .. serialize_inlines(inl.content) .. '}'
  end
  if inl.t == 'Mark' then
    return '\\\\markhl{' .. serialize_inlines(inl.content) .. '}'
  end
  if inl.t == 'Link' then
    return '\\\\href{' .. inl.target .. '}{' .. serialize_inlines(inl.content) .. '}'
  end
  return pandoc.utils.stringify(inl)
end

local function serialize_inlines(inlines)
  local out = {}
  for _, inl in ipairs(inlines) do
    out[#out + 1] = inline_latex(inl)
  end
  return table.concat(out)
end

local function cell_latex(cell)
  local out = {}
  for _, blk in ipairs(cell.contents) do
    if blk.t == 'Para' or blk.t == 'Plain' then
      out[#out + 1] = serialize_inlines(blk.content)
    else
      out[#out + 1] = pandoc.utils.stringify(blk)
    end
  end
  return table.concat(out, ' ')
end

local function row_latex(row, pre, post)
  local cells = {}
  for _, cell in ipairs(row.cells) do
    local body = cell_latex(cell)
    if pre then body = pre .. body .. post end
    cells[#cells + 1] = body
  end
  return table.concat(cells, ' & ') .. ' \\\\\\\\'
end

local function inlines_need_wrap(inlines)
  for _, inl in ipairs(inlines) do
    if inl.t == 'Code' and #inl.text >= 40 then return true end
    if inl.t == 'Str' and #inl.text >= 40 then return true end
    if inl.t == 'Link' and #inl.target >= 60 then return true end
    if (inl.t == 'Strong' or inl.t == 'Emph') and inlines_need_wrap(inl.content) then
      return true
    end
  end
  return false
end

local function cell_needs_wrap(cell)
  for _, blk in ipairs(cell.contents) do
    if blk.t == 'Para' or blk.t == 'Plain' then
      if inlines_need_wrap(blk.content) then return true end
    end
  end
  return false
end

local function table_latex(tbl)
  local ncols = #tbl.colspecs
  local wrap = {}
  for i = 1, ncols do wrap[i] = false end
  local function scan_rows(rows)
    for _, row in ipairs(rows) do
      for ci, cell in ipairs(row.cells) do
        if cell_needs_wrap(cell) then wrap[ci] = true end
      end
    end
  end
  if tbl.head then scan_rows(tbl.head.rows) end
  if tbl.foot then scan_rows(tbl.foot.rows) end
  for _, b in ipairs(tbl.bodies) do scan_rows(b.body) end

  local spec = {}
  local any_x = false
  for i, cs in ipairs(tbl.colspecs) do
    local a = cs[1]
    if wrap[i] then
      any_x = true
      local xc = (a == 'AlignCenter') and 'C' or ((a == 'AlignRight') and 'R' or 'L')
      spec[#spec + 1] = '|' .. xc
    else
      local achar = (a == 'AlignCenter') and 'c' or ((a == 'AlignRight') and 'r' or 'l')
      spec[#spec + 1] = '|' .. achar
    end
  end
  spec[#spec + 1] = '|'
  local colspec = table.concat(spec)
  local begin = any_x
    and '\\\\begin{xltabular}{\\\\linewidth}{' .. colspec .. '}'
    or ('\\\\begin{longtable}{' .. colspec .. '}')
  local out = { begin }
  local head_rows = tbl.head and tbl.head.rows or {}
  local foot_rows = tbl.foot and tbl.foot.rows or {}
  if #head_rows > 0 then
    for i, row in ipairs(head_rows) do
      local pre = (i == 1) and '\\\\hline\\\\rowcolor{black}' or ''
      out[#out + 1] = pre .. row_latex(row, '\\\\textcolor{white}{\\\\bfseries ', '}')
    end
    out[#out + 1] = '\\\\hline\\\\endhead'
  end
  if #foot_rows > 0 then
    for _, row in ipairs(foot_rows) do
      out[#out + 1] = '\\\\hline\\\\rowcolor{shadecolor}' .. row_latex(row, '\\\\textit{', '}')
    end
    out[#out + 1] = '\\\\hline\\\\endlastfoot'
  end
  for _, b in ipairs(tbl.bodies) do
    for _, row in ipairs(b.body) do
      out[#out + 1] = '\\\\hline ' .. row_latex(row, nil)
    end
  end
  if #foot_rows == 0 and #out > 0 then
    out[#out] = out[#out] .. '\\\\hline'
  end
  out[#out + 1] = any_x and '\\\\end{xltabular}' or '\\\\end{longtable}'
  return table.concat(out, '\\n')
end

local function render_code_lang_block(label, code)
  return '\\\\begin{mdframed}[style=codelangbox, frametitle={' .. label .. '}]\\n'
    .. '\\\\begin{Verbatim}[frame=none, breaklines, breaksymbolleft={}, vspace=0pt]\\n'
    .. code .. '\\n'
    .. '\\\\end{Verbatim}\\n'
    .. '\\\\end{mdframed}'
end

function Pandoc(doc)
  local out = pandoc.List()
  local i = 1
  while i <= #doc.blocks do
    local b = doc.blocks[i]
    if b.t == 'Header' then
      -- Plain texttt: no \allowbreak or macros unsafe in moving args (toc/bookmarks)
      local cc = pandoc.List()
      for _, inl in ipairs(b.content) do
        local res = pandoc.walk_inline(inl, hdr_walker)
        if res.tag then
          cc:insert(res)
        else
          for _, x in ipairs(res) do cc:insert(x) end
        end
      end
      b.content = cc
      out:insert(b)
      i = i + 1
    else
      local nb = doc.blocks[i + 1]
      if b.t == 'Div' and has_class(b, 'code-lang') then
        local label = pandoc.utils.stringify(b.content)
        if nb and nb.t == 'CodeBlock' then
          out:insert(pandoc.RawBlock('latex', render_code_lang_block(label, nb.text)))
          i = i + 2
        else
          out:insert(pandoc.RawBlock('latex',
            '\\\\noindent{\\\\small\\\\texttt{' .. label .. '}}\\\\par'))
          i = i + 1
        end
      elseif b.t == 'Table' then
        out:insert(pandoc.RawBlock('latex', table_latex(b)))
        i = i + 1
      elseif b.t == 'HorizontalRule' then
        out:insert(pandoc.RawBlock('latex', '\\\\noindent\\\\rule{\\\\linewidth}{0.4pt}'))
        i = i + 1
      else
        out:insert(pandoc.walk_block(b, body_walker))
        i = i + 1
      end
    end
  end
  doc.blocks = out
  return doc
end

function Span(el)
  local rt = el.attributes['rt']
  if rt then
    el.attributes['rt'] = nil
    local base = pandoc.utils.stringify(el.content)
    local cjk = '%s'
    return pandoc.RawInline('latex', '{\\\\CJKfontspec{' .. cjk .. '}\\\\ruby{' .. base .. '}{' .. rt .. '}}')
  end
  for _, c in ipairs(el.classes) do
    if c == 'mark' then
      return pandoc.RawInline('latex', '\\\\markhl{' .. serialize_inlines(el.content) .. '}')
    end
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


def _is_traditional_chinese(lang: str | None) -> bool:
    return (lang or "").lower().startswith(("zh-hant", "zh-tw", "zh-mo"))


def _default_cjk_font(lang: str | None) -> str:
    lang = (lang or "").lower()
    if lang.startswith("zh"):
        if lang in ("zh-hk", "zh-hant-hk"):
            return DEFAULT_CJK_ZH_HK_FONT
        if _is_traditional_chinese(lang):
            return DEFAULT_CJK_ZH_TW_FONT
        return DEFAULT_CJK_ZH_CN_FONT
    if lang.startswith("ko"):
        return DEFAULT_CJK_KR_FONT
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

    return re.sub(r'<img\b[^>]*?\bsrc="([^"]+)"', _abs, html)


def _strip_footnote_backref(html: str) -> str:
    return re.sub(r'\s*<a[^>]*class="footnote-backref"[^>]*>.*?</a>', "", html)


def _strip_image_titles(html: str) -> str:
    return re.sub(r'(<img\b[^>]*?)\s+title="[^"]*"([^>]*>)', r"\1\2", html)


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
    def _convert(m: re.Match) -> str:
        attrs = m.group(1)
        anchor = ""
        id_match = re.search(r'\sid="([^"]*)"', attrs)
        if id_match:
            anchor = f'<a id="{id_match.group(1)}"></a>'
            attrs = attrs.replace(id_match.group(0), "", 1)
        return f"{anchor}<p{attrs}><strong><em>{m.group(2)}</em></strong></p>"

    return re.sub(
        r"<h6([^>]*)>(.*?)</h6>",
        _convert,
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
    head_font: str = DEFAULT_HEAD_FONT,
    pdf_metadata: dict[str, str] | None = None,
) -> str:
    main_decl = _guard_font_set("setmainfont", [main_font])
    cjk_decl = _guard_font_set("setCJKmainfont", [cjk_font])
    mono_decl = _guard_font_set("setmonofont", [mono_font])
    hypersetup = _make_hypersetup(pdf_metadata or {})
    running_header = _make_running_header(pdf_metadata or {})
    return _LATEX_PREAMBLE % (
        main_decl,
        cjk_decl,
        mono_decl,
        head_font,
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
    head_font: str,
) -> None:
    header = _make_latex_header(
        main_font,
        cjk_font,
        mono_font,
        symbol_font,
        head_font=head_font,
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
    full = _strip_image_titles(full)
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
    head_font: str | None = None,
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

    main = _select_font(main_font or DEFAULT_MAIN_FONT, [])
    head = _select_font(head_font or DEFAULT_HEAD_FONT, [])
    cjk = _select_font(effective_cjk, [])
    mono = _select_font(mono_font or DEFAULT_MONO_FONT, [])
    symbol = _select_font(symbol_font or DEFAULT_SYMBOL_FONT, [])

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
        "head_font": head,
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
    head_font: str | None = None,
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
        head_font=head_font,
        cjk_font=cjk_font,
        mono_font=mono_font,
        symbol_font=symbol_font,
    )


def _extract_lang(html: str) -> str | None:
    match = re.search(r'<html[^>]*\blang="([^"]*)"', html)
    return match.group(1) if match else None
