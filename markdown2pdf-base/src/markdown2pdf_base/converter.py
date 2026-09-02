"""Convert Markdown to PDF via markdown2html5-base and pandoc/xelatex.

This module bridges the HTML produced by :mod:`markdown2html5_base` to a PDF
built by pandoc using the xelatex engine. It applies font selection, a bespoke
Lua filter and LaTeX preamble to faithfully reproduce the HTML layout
(headings, tables, code blocks, ruby annotations, per-language CJK fonts and
``<figure>``/``<figcaption>`` images) in the generated PDF.
"""

from __future__ import annotations

import functools
import os
import re
import subprocess
import sys
import tempfile
import warnings
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from string import Template
from typing import Any, Final

from markdown2html5_base import MarkdownToHTML

# ===========================================================================
# Font Constants
# ===========================================================================

DEFAULT_MAIN_FONT: Final[str] = "Noto Serif"
DEFAULT_HEAD_FONT: Final[str] = "Noto Sans"
DEFAULT_MONO_FONT: Final[str] = "Noto Sans Mono"
DEFAULT_SYMBOL_FONT: Final[str] = "Symbola"

DEFAULT_CJK_JP_FONT: Final[str] = "Noto Serif CJK JP"
DEFAULT_CJK_ZH_CN_FONT: Final[str] = "Noto Serif CJK SC"
DEFAULT_CJK_ZH_TW_FONT: Final[str] = "Noto Serif CJK TC"
DEFAULT_CJK_ZH_HK_FONT: Final[str] = "Noto Serif CJK HK"
DEFAULT_CJK_KR_FONT: Final[str] = "Noto Serif CJK KR"

CJK_FONT_KEYS: Final[tuple[str, ...]] = ("ja", "cn", "tw", "hk", "kr")

CJK_DEFAULT_FONTS: Final[Mapping[str, str]] = {
    "ja": DEFAULT_CJK_JP_FONT,
    "cn": DEFAULT_CJK_ZH_CN_FONT,
    "tw": DEFAULT_CJK_ZH_TW_FONT,
    "hk": DEFAULT_CJK_ZH_HK_FONT,
    "kr": DEFAULT_CJK_KR_FONT,
}


@dataclass(frozen=True)
class FontConfig:
    """Read-only immutable configuration container for matching document fonts."""

    main: str = DEFAULT_MAIN_FONT
    head: str = DEFAULT_HEAD_FONT
    mono: str = DEFAULT_MONO_FONT
    symbol: str = DEFAULT_SYMBOL_FONT
    cjk: Mapping[str, str] = field(default_factory=lambda: dict(CJK_DEFAULT_FONTS))

    def __post_init__(self) -> None:
        """Reject CJK font keys that are not part of the supported set."""
        invalid_keys = set(self.cjk.keys()) - set(CJK_FONT_KEYS)
        if invalid_keys:
            raise ValueError(
                f"Invalid CJK language keys: {invalid_keys}. Valid: {CJK_FONT_KEYS}"
            )


@dataclass(frozen=True)
class DocumentMetadata:
    """Type-safe wrapper for parsed document headers and metadata."""

    title: str | None = None
    author: str | None = None
    description: str | None = None
    keywords: str | None = None
    lang: str | None = None
    published: str | None = None

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> DocumentMetadata:
        """Safely build metadata configurations from raw source dictionaries."""
        return cls(
            title=data.get("title"),
            author=data.get("author"),
            description=data.get("description"),
            keywords=data.get("keywords"),
            lang=data.get("lang"),
            published=data.get("published"),
        )


# ===========================================================================
# Static Templates & String Assemblers (CSS & LaTeX Preamble)
# ===========================================================================

_CSS_TEMPLATE: Final[Template] = Template("""
    body { font-family: "$main", sans-serif; font-size: 11pt; line-height: 1.6; max-width: 42em; margin: 2em auto; padding: 0 1em; }
    pre, code { font-family: "$mono", monospace; font-size: 9.5pt; }
    pre { background: #f5f5f5; padding: 0.8em; border-radius: 4px; overflow-x: auto; }
    code { background: #f0f0f0; padding: 0.15em 0.3em; border-radius: 3px; }
    pre code { background: none; padding: 0; }
    div.code-lang { font-family: "$mono", monospace; font-size: 9pt; color: #666; margin: 0; padding: 0.2em 0; }
    table { border-collapse: collapse; width: 100%; margin: 1em 0; }
    th, td { border: 1px solid #ccc; padding: 0.4em 0.6em; text-align: left; }
    th { background: #eee; }
    blockquote { margin: 0.5em 0; padding: 0.2em 1em; border-left: 4px solid #ccc; color: #555; }
    hr { border: none; border-top: 2px solid #ccc; margin: 1.5em 0; }
    img { max-width: 100%; }
    .footnotes { margin-top: 2em; font-size: 0.9em; color: #666; }
    mark { background: #ffec8b; padding: 0.1em 0.2em; }
    s { color: #999; }
    sub { font-size: 0.75em; }
    sup { font-size: 0.75em; }
    ins { text-decoration: underline; }
    dl { margin: 0.5em 0; }
    dt { font-weight: bold; margin-top: 0.3em; }
    dd { margin-left: 1.5em; }
    a { text-decoration: underline; font-style: italic; }
    ruby { ruby-align: center; }
    rp { display: none; }
    """)

_LATEX_PREAMBLE_TEMPLATE: Final[Template] = Template(
    r"""\usepackage[margin=25.4mm]{geometry}
\usepackage{graphicx}
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
\mdfdefinestyle{codelangbox}{%
  linecolor=black, linewidth=0.6pt,
  frametitlefont=\small\bfseries\ttfamily\color{white},
  frametitlebackgroundcolor=black,
  backgroundcolor=shadecolor,
  innertopmargin=4pt, innerbottommargin=4pt,
  innerleftmargin=6pt, innerrightmargin=6pt,
  skipabove=6pt, skipbelow=6pt,
}
\makeatletter
\newenvironment{ShadedVerbatim}{%
  \VerbatimEnvironment
  \begin{mdframed}[style=codelangbox]\begin{Verbatim}[frame=none, breaklines, breaksymbolleft={}, vspace=0pt]%
}{%
  \end{Verbatim}\end{mdframed}%
}
\let\verbatim\ShadedVerbatim
\let\endverbatim\endShadedVerbatim
\makeatother
\renewenvironment{quote}{%
  \begin{mdframed}[leftline=true, rightline=false, topline=false, bottomline=false,
    linecolor=shadecolor, linewidth=10pt,
    innerleftmargin=20pt, innerrightmargin=0pt,
    innertopmargin=4pt, innerbottommargin=4pt,
    leftmargin=0pt, rightmargin=0pt, skipabove=6pt, skipbelow=6pt]
}{%
  \end{mdframed}%
}
\makeatletter
\providecommand{\pandocbounded}[1]{%
  \begingroup
  \setbox\@tempboxa\hbox{#1}%
  \@tempdima=\dimexpr\ht\@tempboxa\relax
  \@tempdimb=\dimexpr\wd\@tempboxa\relax
  \ifdim\@tempdima>\textheight
    \@tempdimb=\dimexpr\@tempdimb * \textheight / \@tempdima\relax
    \@tempdima=\textheight
  \fi
  \ifdim\@tempdimb>\linewidth
    \@tempdima=\dimexpr\@tempdima * \linewidth / \@tempdimb\relax
    \@tempdimb=\linewidth
  \fi
  \resizebox{\@tempdimb}{\@tempdima}{#1}%
  \endgroup
}
\makeatother
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

$font_settings
$cjk_font_settings

\newfontfamily{\headfont}{$head_font}
\titleformat{\section}{\Large\bfseries\headfont}{\thesection}{1em}{}
\titleformat{\subsection}{\large\bfseries\headfont}{\thesubsection}{1em}{}
\titleformat{\subsubsection}{\normalsize\bfseries\headfont}{\thesubsubsection}{1em}{}
\titleformat{\paragraph}{\normalsize\bfseries\headfont}{\theparagraph}{1em}{}
\titleformat{\subparagraph}{\normalsize\bfseries\headfont}{\thesubparagraph}{1em}{}
\newcommand{\useSymbolFont}[1]{%
  \IfFontExistsTF{#1}{%
    \newfontfamily{\symbolfont}{#1}%
  }{%
    \newfontfamily{\symbolfont}{Symbola}%
  }%
}
\useSymbolFont{$symbol_font}
\pagestyle{fancy}
\fancyhf{}
\fancyhead[C]{$header_title}
\fancyfoot[C]{\thepage}
\renewcommand{\headrulewidth}{0pt}
\AtBeginDocument{%
\ifcsname Shaded\endcsname
  \renewenvironment{Shaded}{\begin{snugshade}}{\end{snugshade}}%
\fi
$document_hooks
\let\oldhref\href
\renewcommand{\href}[2]{\oldhref{#1}{\underline{\textcolor{blue}{{#2}}}}}%
}
"""
)


def generate_css(config: FontConfig) -> str:
    """Render the embedded CSS template with the configured main and mono fonts."""
    return _CSS_TEMPLATE.substitute(main=config.main, mono=config.mono)


def generate_latex_preamble(
    config: FontConfig,
    header_title: str = "",
    font_settings: str = "",
    cjk_font_settings: str = "",
    document_hooks: str = "",
) -> str:
    """Substitute the configured fonts and document fragments into the LaTeX preamble."""
    return _LATEX_PREAMBLE_TEMPLATE.substitute(
        head_font=config.head,
        symbol_font=config.symbol,
        header_title=header_title,
        font_settings=font_settings,
        cjk_font_settings=cjk_font_settings,
        document_hooks=document_hooks,
    )


# ===========================================================================
# Monolithic Embedded Pandoc Lua Filter Template
# ===========================================================================

_FULL_LUA_FILTER_TEMPLATE: Final[Template] = Template("""local symbol_blocks = {
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

local RUBY_CJK_FONT = '$ruby_cjk_font'

local function is_symbol(ch)
  if ch:byte() < 0x80 then return false end
  local n = utf8.codepoint(ch)
  for _, r in ipairs(symbol_blocks) do
    if n >= r[1] and n <= r[2] then return true end
  end
  return false
end

local cjk_blocks = {
  ja = {
    {0x3040, 0x30FF}, {0x31F0, 0x31FF}, {0xFF66, 0xFF9F},
  },
  kr = {
    {0x1100, 0x11FF}, {0x3130, 0x318F}, {0xAC00, 0xD7A3},
  }
}

local function char_class(ch)
  if ch:byte() < 0x80 then return 'latin' end
  local n = utf8.codepoint(ch)
  
  for _, r in ipairs(symbol_blocks) do
    if n >= r[1] and n <= r[2] then return 'symbol' end
  end
  
  for lang, blocks in pairs(cjk_blocks) do
    for _, r in ipairs(blocks) do
      if n >= r[1] and n <= r[2] then return lang end
    end
  end
  return 'latin'
end

local function wrap_scripts(text)
  local out = pandoc.List()
  local buf = {}
  local cls = 'latin'
  
  local function flush()
    if #buf > 0 then
      local joined_buf = table.concat(buf)
      if cls == 'symbol' then
        out:insert(pandoc.RawInline('latex', '{\\\\symbolfont{' .. joined_buf .. '}}'))
      elseif cls == 'ja' then
        out:insert(pandoc.RawInline('latex', '{\\\\cjkja{' .. joined_buf .. '}}'))
      elseif cls == 'kr' then
        out:insert(pandoc.RawInline('latex', '{\\\\cjkkr{' .. joined_buf .. '}}'))
      else
        out:insert(pandoc.Str(joined_buf))
      end
      buf = {}
    end
  end
  
  for ch in text:gmatch(utf8.charpattern) do
    local c = char_class(ch)
    if c ~= cls then
      flush()
      cls = c
    end
    buf[#buf + 1] = ch
  end
  flush()
  return out
end

function Str(el)
  local out = wrap_scripts(el.text)
  if #out == 1 and out.t == 'Str' and out.text == el.text then
    return nil
  end
  return out
end

local code_escapes = {
  ['\\\\'] = '\\\\textbackslash{}', ['{'] = '\\\\{', ['}'] = '\\\\}',
  ['$$'] = '\\\\$$', ['&'] = '\\\\&', ['#'] = '\\\\#', ['_'] = '\\\\_',
  ['%'] = '\\\\%', ['^'] = '\\\\textasciicircum{}', ['~'] = '\\\\textasciitilde{}',
  ['<'] = '<', ['>'] = '>',
}

local function latex_escape_code(text)
  return (text:gsub(utf8.charpattern, function(ch) return code_escapes[ch] or ch end))
end

local hdr_walker = {
  Code = function(el)
    return pandoc.RawInline('latex', '\\\\texttt{' .. latex_escape_code(el.text) .. '}')
  end,
}

local function breakable_code(escaped)
  local out = {}
  local i = 1
  local len = #escaped
  while i <= len do
    local tok
    local c = escaped:sub(i, i)
    if c == '\\\\' then
      local j = i + 1
      local ch = escaped:sub(j, j)
      if ch:match('[a-zA-Z]') then
        local k = j
        while k <= len and escaped:sub(k, k):match('[a-zA-Z]') do k = k + 1 end
        tok = escaped:sub(i, k - 1)
        local rest = escaped:sub(k)
        if rest:sub(1, 1) == '{' then
          local close = rest:find('}', 2)
          if close then tok = tok .. rest:sub(1, close) end
        end
      else
        tok = escaped:sub(i, i + 1)
      end
    else
      local nb = 1
      local b = escaped:byte(i)
      if b then
        if b >= 240 then nb = 4 elseif b >= 224 then nb = 3 elseif b >= 192 then nb = 2 end
      end
      tok = escaped:sub(i, i + nb - 1)
    end
    out[#out + 1] = tok
    out[#out + 1] = '\\\\allowbreak{}'
    i = i + #tok
  end
  return table.concat(out)
end

local function code_latex(el)
  return '\\\\texttt{' .. breakable_code(latex_escape_code(el.text)) .. '}'
end

local function code_emit(el) return pandoc.RawInline('latex', code_latex(el)) end

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
  local classes = {}
  for _, c in ipairs(el.classes) do classes[c] = true end
  return classes[name] == true
end

local function latex_escape_text(s)
  s = s:gsub('\\\\', '\\\\textbackslash{}')
  s = s:gsub('([{}$$&#_%%%%])', '\\\\%%1')
  s = s:gsub('~', '\\\\textasciitilde{}')
  s = s:gsub('%%^', '\\\\textasciicircum{}')
  return s
end

local inline_handlers = {
  Str = function(inl) return latex_escape_text(inl.text) end,
  RawInline = function(inl) return inl.text end,
  Code = function(inl) return code_latex(inl) end,
  Space = function() return ' ' end,
  SoftBreak = function() return ' ' end,
  Strong = function(inl) return '\\\\textbf{' .. serialize_inlines(inl.content) .. '}' end,
  Emph = function(inl) return '\\\\emph{' .. serialize_inlines(inl.content) .. '}' end,
  Mark = function(inl) return '\\\\markhl{' .. serialize_inlines(inl.content) .. '}' end,
  Link = function(inl) return '\\\\href{' .. inl.target .. '}{' .. serialize_inlines(inl.content) .. '}' end,
}

function inline_latex(inl)
  local handler = inline_handlers[inl.t]
  return handler and handler(inl) or pandoc.utils.stringify(inl)
end

function serialize_inlines(inlines)
  local out = {}
  for i = 1, #inlines do out[i] = inline_latex(inlines[i]) end
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
  for i, cell in ipairs(row.cells) do
    local body = cell_latex(cell)
    if pre and post then body = table.concat({pre, body, post}) end
    cells[i] = body
  end
  return table.concat(cells, ' & ') .. ' \\\\\\\\'
end

local function inlines_need_wrap(inlines)
  for _, inl in ipairs(inlines) do
    local t = inl.t
    if (t == 'Code' or t == 'Str') and #inl.text >= 40 then return true end
    if t == 'Link' and #inl.target >= 60 then return true end
    if (t == 'Strong' or t == 'Emph') and inlines_need_wrap(inl.content) then return true end
  end
  return false
end

local function cell_needs_wrap(cell)
  for _, blk in ipairs(cell.contents) do
    if (blk.t == 'Para' or blk.t == 'Plain') and inlines_need_wrap(blk.content) then return true end
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
    if wrap[i] then
      any_x = true
      local xc = (cs == 'AlignCenter') and 'C' or ((cs == 'AlignRight') and 'R' or 'L')
      spec[#spec + 1] = '|' .. xc
    else
      local achar = (cs == 'AlignCenter') and 'c' or ((cs == 'AlignRight') and 'r' or 'l')
      spec[#spec + 1] = '|' .. achar
    end
  end
  spec[#spec + 1] = '|'
  local colspec = table.concat(spec)
  
  local begin = any_x and '\\\\begin{xltabular}{\\\\linewidth}{' .. colspec .. '}' or ('\\\\begin{longtable}{' .. colspec .. '}')
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
    for _, row in ipairs(b.body) do out[#out + 1] = '\\\\hline ' .. row_latex(row, nil) end
  end
  
  if #foot_rows == 0 and #out > 0 then out[#out] = out[#out] .. '\\\\hline' end
  out[#out + 1] = any_x and '\\\\end{xltabular}' or '\\\\end{longtable}'
  return table.concat(out, '\\n')
end

local function definition_list_latex(b)
  local chunks = {}
  for _, item in ipairs(b.content) do
    local defs = {}
    for _, def in ipairs(item[2]) do
      local def_parts = {}
      for _, blk in ipairs(def) do
        if blk.t == 'Para' or blk.t == 'Plain' then
          def_parts[#def_parts + 1] = serialize_inlines(blk.content)
        else
          def_parts[#def_parts + 1] = pandoc.utils.stringify(blk)
        end
      end
      defs[#defs + 1] = '\\\\hspace*{1.5em}{\\\\itshape ' .. table.concat(def_parts, ' ') .. '}\\\\par'
    end
    chunks[#chunks + 1] = '\\\\textbf{' .. serialize_inlines(item[1]) .. '}\\\\par' .. table.concat(defs, ' ')
  end
  return '\\\\par\\\\smallskip ' .. table.concat(chunks, ' \\\\par\\\\smallskip ')
end

local function render_code_lang_block(label, code)
  return table.concat({
    '\\\\begin{mdframed}[style=codelangbox, frametitle={', label, '}]\\n',
    '\\\\begin{Verbatim}[frame=none, breaklines, breaksymbolleft={}, vspace=0pt]\\n',
    code, '\\n',
    '\\\\end{Verbatim}\\n',
    '\\\\end{mdframed}'
  })
end

local function image_inline_latex(el)
  local src = el.src
  local alt = pandoc.utils.stringify(el.caption)
  if src:sub(1, 5) == 'data:' then
    if alt == '' then alt = 'image' end
    return pandoc.RawInline('latex', '{\\\\itshape [' .. alt .. ']}')
  end
  return pandoc.RawInline('latex', '\\\\pandocbounded{\\\\includegraphics[keepaspectratio,alt={' .. alt .. '}]{' .. src .. '}}')
end

local function figure_latex(fig)
  local cap = serialize_inlines(fig.caption.long)
  local imgs = pandoc.List()
  local scan = { Image = function(el) imgs:insert(el) return el end }
  for i = 1, #fig.content do pandoc.walk_block(fig.content[i], scan) end
  
  local im = {}
  for i = 1, #imgs do im[i] = image_inline_latex(imgs[i]).text end
  local out = { '\\\\noindent', table.concat(im, '\\\\par\\\\smallskip\\\\par') }
  if cap ~= '' then out[#out + 1] = '\\\\par\\n{\\\\itshape ' .. cap .. '}' end
  out[#out + 1] = '\\n\\\\par'
  return table.concat(out)
end

function Pandoc(doc)
  local out = pandoc.List()
  local i = 1
  local blocks_len = #doc.blocks
  while i <= blocks_len do
    local b = doc.blocks[i]
    if b.t == 'Header' then
      local cc = pandoc.List()
      for j = 1, #b.content do
        local res = pandoc.walk_inline(b.content[j], hdr_walker)
        if res.tag then cc:insert(res) else for k = 1, #res do cc:insert(res[k]) end end
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
          out:insert(pandoc.RawBlock('latex', '\\\\noindent{\\\\small\\\\texttt{' .. label .. '}}\\\\par'))
          i = i + 1
        end
      elseif b.t == 'Table' then out:insert(pandoc.RawBlock('latex', table_latex(b))); i = i + 1
      elseif b.t == 'HorizontalRule' then out:insert(pandoc.RawBlock('latex', '\\\\noindent\\\\rule{\\\\linewidth}{0.4pt}')); i = i + 1
      elseif b.t == 'Figure' then out:insert(pandoc.RawBlock('latex', figure_latex(b))); i = i + 1
      elseif b.t == 'DefinitionList' then out:insert(pandoc.RawBlock('latex', definition_list_latex(b))); i = i + 1
      else out:insert(pandoc.walk_block(b, body_walker)); i = i + 1 end
    end
  end
  doc.blocks = out
  return doc
end

local function plain_text(inlines)
  local parts = {}
  for i = 1, #inlines do
    local x = inlines[i]
    if x.t == 'Str' then parts[#parts + 1] = x.text
    elseif x.t == 'RawInline' then
      parts[#parts + 1] = x.text:match('{\\\\cjk%%a+{(.-)}}') or x.text:match('{\\\\symbolfont{(.-)}}') or x.text
    else parts[#parts + 1] = pandoc.utils.stringify(x) end
  end
  return table.concat(parts)
end

function Span(el)
  local rt = el.attributes['rt']
  if rt then
    el.attributes['rt'] = nil
    return pandoc.RawInline('latex', '{\\\\CJKfontspec{' .. RUBY_CJK_FONT .. '}\\\\ruby{' .. plain_text(el.content) .. '}{' .. rt .. '}}')
  end
  if has_class(el, 'mark') then
    return pandoc.RawInline('latex', '\\\\markhl{' .. serialize_inlines(el.content) .. '}')
  end
  if has_class(el, 'h6') then
    return pandoc.RawInline('latex', '\\\\textbf{\\\\emph{\\\\headfont{' .. serialize_inlines(el.content) .. '}}}')
  end
end
""")

# ===========================================================================
# Regular Expression Matchers, Metadata Parsers & Cached Font System Lookups
# ===========================================================================

_FULL_DOC_RE: Final[re.Pattern[str]] = re.compile(
    r"^\s*<(?:!doctype html|html(?:\s|>))", re.IGNORECASE
)
_HTML_LANG_RE: Final[re.Pattern[str]] = re.compile(
    r'<html[^>]*\blang="([^"]*)"', re.IGNORECASE
)
_TITLE_RE: Final[re.Pattern[str]] = re.compile(
    r"<title>(.*?)</title>", re.DOTALL | re.IGNORECASE
)

_META_RE: Final[Mapping[str, re.Pattern[str]]] = {
    "author": re.compile(
        r'<meta\s+[^>]*name="author"[^>]*content="([^"]*)"[^>]*>', re.IGNORECASE
    ),
    "description": re.compile(
        r'<meta\s+[^>]*name="description"[^>]*content="([^"]*)"[^>]*>', re.IGNORECASE
    ),
    "keywords": re.compile(
        r'<meta\s+[^>]*name="keywords"[^>]*content="([^"]*)"[^>]*>', re.IGNORECASE
    ),
    "published": re.compile(
        r'<meta\s+[^>]*name="published"[^>]*content="([^"]*)"[^>]*>', re.IGNORECASE
    ),
}

_LATEX_SPECIAL_CHARS_RE: Final[re.Pattern[str]] = re.compile(r"([\\{}%#&_~^])")
_LATEX_REPLACEMENTS: Final[Mapping[str, str]] = {
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

_QUOTES_TRANSLATION: Final[Mapping[int, str]] = str.maketrans(
    {0x201C: '"', 0x201D: '"', 0x2018: "'", 0x2019: "'", 0xFE0F: None}
)
_VARIATION_SELECTOR_RE: Final[re.Pattern[str]] = re.compile(r"️|&#x[fF][eE]0[fF];")
_RUBY_RE: Final[re.Pattern[str]] = re.compile(
    r"<ruby\b[^>]*>(.*?)</ruby>", re.DOTALL | re.IGNORECASE
)
_RUBY_INNER_RE: Final[re.Pattern[str]] = re.compile(
    r"([^<]+)<rp>\(</rp><rt>([^<]+)</rt><rp>\)</rp>", re.DOTALL | re.IGNORECASE
)


def _latex_escape(value: str) -> str:
    """Escape LaTeX special characters so the string is safe for PDF metadata."""
    if not value:
        return ""
    return _LATEX_SPECIAL_CHARS_RE.sub(lambda m: _LATEX_REPLACEMENTS[m.group(1)], value)


def _make_hypersetup(metadata: DocumentMetadata) -> str:
    """Build a ``\\hypersetup`` hook from the document's PDF metadata fields."""
    mapping = {
        "title": "pdftitle",
        "author": "pdfauthor",
        "description": "pdfsubject",
        "keywords": "pdfkeywords",
        "lang": "pdflang",
    }
    fields = []
    for attr, option in mapping.items():
        value = getattr(metadata, attr, None)
        if value:
            fields.append(f"{option}={{{_latex_escape(value)}}}")
    return f"\\hypersetup{{{', '.join(fields)}}}" if fields else ""


def _make_running_header(metadata: DocumentMetadata) -> str:
    """Format the title, author and published date into a running-header line."""
    if not (metadata.title or metadata.author or metadata.published):
        return ""
    parts = []
    if metadata.title:
        parts.append(f"\\textbf{{{_latex_escape(metadata.title)}}}")
    suffix = []
    if metadata.author:
        suffix.append(f"\\textit{{{_latex_escape(metadata.author)}}}")
    if metadata.published:
        suffix.append(_latex_escape(metadata.published))
    if suffix:
        parts.append(f"({': '.join(suffix)})")
    return " ".join(parts)


@functools.lru_cache(maxsize=1)
def _get_installed_fonts() -> set[str]:
    """Return the set of font family names installed on the system (via ``fc-list``)."""
    try:
        result = subprocess.run(
            ["fc-list", ":", "family"],
            capture_output=True,
            text=True,
            check=False,
            timeout=15,
        )
        if result.returncode == 0:
            fonts = set()
            for line in result.stdout.splitlines():
                if ":" in line:
                    families_part = line.split(":", 1)[1]
                    for family in families_part.split(","):
                        fonts.add(family.strip().lower())
            return fonts
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return set()


def _font_available(family: str) -> bool:
    """Return whether the given font family is installed (assumes available if unknown)."""
    installed = _get_installed_fonts()
    return family.lower() in installed if installed else True


def _select_font(family: str, fallbacks: Sequence[str]) -> str:
    """Return the first available font from ``family`` followed by its fallbacks."""
    chain = [family] + [f for f in fallbacks if f != family]
    for name in chain:
        if _font_available(name):
            if name != family:
                warnings.warn(
                    f"Font '{family}' not found; using '{name}' instead.", stacklevel=3
                )
            return name
    return family


def _build_fallback_chain(
    chain: Sequence[str], cmd_factory: Callable[[str], str]
) -> str:
    """Build a nested ``\\IfFontExistsTF`` fallback chain over the font names."""
    unique_chain = list(dict.fromkeys(chain))
    if not unique_chain:
        return ""
    if len(unique_chain) == 1:
        return cmd_factory(unique_chain[0])
    parts = [
        f"\\IfFontExistsTF{{{name}}}{{{cmd_factory(name)}}}{{"
        for name in unique_chain[:-1]
    ]
    parts.append(cmd_factory(unique_chain[-1]))
    parts.append("}" * (len(unique_chain) - 1))
    return "".join(parts)


def _guard_font_set(set_command: str, chain: list[str]) -> str:
    return _build_fallback_chain(chain, lambda name: f"\\{set_command}{{{name}}}")


def _guard_new_cjk_family(family: str, chain: list[str]) -> str:
    return _build_fallback_chain(
        chain, lambda name: f"\\newCJKfontfamily{{\\{family}}}{{{name}}}"
    )


def _cjk_key_for_lang(lang: str | None) -> str:
    """Map a language code to one of the CJK font keys (``ja``, ``cn``, ``tw``, ``hk``, ``kr``)."""
    lang = (lang or "").lower()
    if lang.startswith("zh"):
        if lang in ("zh-hk", "zh-hant-hk") or lang.startswith(
            ("zh-hant", "zh-tw", "zh-mo")
        ):
            return "hk" if "hk" in lang else "tw"
        return "cn"
    return "kr" if lang.startswith("ko") else "ja"


# ===========================================================================
# HTML Sanitization & Post-Processing Pipeline
# ===========================================================================


def _resolve_image_src(html: str, source_dir: str) -> str:
    """Resolve relative image ``src`` paths against ``source_dir``, keeping absolute URLs."""

    def _abs(m: re.Match[str]) -> str:
        src = m.group(1)
        if src.startswith(("http://", "https://", "data:", "/")):
            return m.group(0)
        return m.group(0).replace(
            f'src="{src}"', f'src="{os.path.normpath(os.path.join(source_dir, src))}"'
        )

    return re.sub(r'<img\b[^>]*?\bsrc="([^"]+)"', _abs, html)


def _strip_footnote_backref(html: str) -> str:
    """Remove footnote back-reference links from the generated HTML."""
    return re.sub(
        r'\s*<a\b[^>]*class="footnote-backref"[^>]*>.*?</a>', "", html, flags=re.DOTALL
    )


def _strip_image_titles(html: str) -> str:
    """Remove ``title`` attributes from image tags."""
    return re.sub(
        r'(<img\b[^>]*?)\s+title="[^"]*"([^>]*>)', r"\1\2", html, flags=re.IGNORECASE
    )


def _normalize_quotes(html: str) -> str:
    """Replace fancy typographic quotes with straight ASCII equivalents."""
    return html.translate(_QUOTES_TRANSLATION)


def _strip_variation_selectors(html: str) -> str:
    """Remove Unicode variation selectors (e.g. emoji presentation chars) from the HTML."""
    return _VARIATION_SELECTOR_RE.sub("", html.translate(_QUOTES_TRANSLATION))


def _ruby_to_span(html: str) -> str:
    """Rewrite ``<ruby>`` ruby markup into a ``<span class="ruby" rt="...">`` form."""

    def _convert_ruby(m: re.Match[str]) -> str:
        match = _RUBY_INNER_RE.match(m.group(1).strip())
        return (
            f'<span class="ruby" rt="{match.group(2)}">{match.group(1)}</span>'
            if match
            else m.group(0)
        )

    return _RUBY_RE.sub(_convert_ruby, html)


def _h6_to_bold_italic_para(html: str) -> str:
    """Turn ``<h6>`` headings into a sans bold-italic paragraph via a ``class="h6"`` span."""
    pattern = r"<h6\b([^>]*)>(.*?)</h6>"
    id_pattern = re.compile(r'\bid="([^"]*)"')

    def _convert(m: re.Match[str]) -> str:
        idm = id_pattern.search(m.group(1))
        anchor = f'<a id="{idm.group(1)}"></a>' if idm else ""
        return f'{anchor}<p><span class="h6">{m.group(2)}</span></p>'

    return re.sub(pattern, _convert, html, flags=re.DOTALL | re.IGNORECASE)


def _is_html(text: str) -> bool:
    """Return ``True`` if the input looks like raw HTML (starts with ``<``)."""
    return text.strip().startswith("<")


def _is_full_document(html: str) -> bool:
    """Return ``True`` if the input is a complete HTML document."""
    return bool(_FULL_DOC_RE.match(html))


def _cjk_family_name(key: str) -> str:
    """Return the LaTeX/HTML family macro name for a CJK key."""
    return f"cjk{key}"


def _strip_metadata_tags(html: str) -> str:
    """Remove ``<title>`` and ``<meta>`` tags from the HTML."""
    html = re.sub(r"<title[^>]*>.*?</title>", "", html, flags=re.DOTALL | re.IGNORECASE)
    return re.sub(r"<meta[^>]*>", "", html, flags=re.IGNORECASE)


# ===========================================================================
# Document Assembly & Thread-Safe Engine Hooks
# ===========================================================================


def _extract_metadata(html: str) -> DocumentMetadata:
    """Parse the document title and meta fields into a :class:`DocumentMetadata`."""
    raw_metadata: dict[str, str] = {}
    title_match = _TITLE_RE.search(html)
    if title_match:
        raw_metadata["title"] = title_match.group(1).strip()
    for key, pattern in _META_RE.items():
        match = pattern.search(html)
        if match:
            raw_metadata[key] = match.group(1).strip()
    return DocumentMetadata.from_dict(raw_metadata)


def _wrap_html(body: str, lang: str, config: FontConfig) -> str:
    """Wrap a fragment in a minimal HTML document shell with injected CSS."""
    return f'<!DOCTYPE html>\n<html lang="{lang}">\n<head>\n<meta charset="utf-8">\n<style>\n{generate_css(config)}\n</style>\n</head>\n<body>\n{body}\n</body>\n</html>'


def _inject_css(full_html: str, config: FontConfig) -> str:
    """Inject the generated CSS ``<style>`` block into the document ``<head>``."""
    return re.sub(
        r"<head>",
        f"<head>\n<style>\n{generate_css(config)}\n</style>",
        full_html,
        count=1,
        flags=re.IGNORECASE,
    )


def _make_latex_header(
    config: FontConfig,
    cjk_fonts: Mapping[str, str],
    main_cjk_key: str,
    pdf_metadata: DocumentMetadata | None = None,
) -> str:
    """Assemble the full LaTeX header (preamble, fonts and metadata) for XeLaTeX."""
    metadata = pdf_metadata or DocumentMetadata()
    font_settings = f"{_guard_font_set('setmainfont', [config.main])}\n{_guard_font_set('setmonofont', [config.mono])}"

    cjk_families = "\n".join(
        _guard_new_cjk_family(
            _cjk_family_name(k), [cjk_fonts[k], config.cjk.get(k, "")]
        )
        for k in CJK_FONT_KEYS
    )
    cjk_font_settings = f"{_guard_font_set('setCJKmainfont', [cjk_fonts[main_cjk_key]])}\n{cjk_families}"

    return generate_latex_preamble(
        config=config,
        header_title=_make_running_header(metadata),
        font_settings=font_settings,
        cjk_font_settings=cjk_font_settings,
        document_hooks=_make_hypersetup(metadata),
    )


def _write_lua_filter(
    path: str, cjk_fonts: Mapping[str, str], main_cjk_key: str
) -> None:
    """Render and write the Lua filter template to ``path`` using the main CJK font."""
    with open(path, "w", encoding="utf-8") as f:
        f.write(
            _FULL_LUA_FILTER_TEMPLATE.substitute(ruby_cjk_font=cjk_fonts[main_cjk_key])
        )


def _pandoc_html_to_pdf(
    html_path: str,
    pdf_path: str,
    *,
    metadata: DocumentMetadata | None = None,
    config: FontConfig,
    cjk_fonts: Mapping[str, str],
    main_cjk_key: str,
    cwd: str | None = None,
) -> None:
    """Convert the given HTML file to a PDF by running pandoc with the XeLaTeX engine.

    ``cwd`` is the working directory for the pandoc/xelatex subprocess; set it to
    the document's source directory so relative image paths resolve correctly.
    """
    header = _make_latex_header(config, cjk_fonts, main_cjk_key, metadata)

    # Write the header and Lua filter to temp files so pandoc can reference them
    with (
        tempfile.NamedTemporaryFile(
            mode="w", suffix=".tex", delete=False, encoding="utf-8"
        ) as tex_f,
        tempfile.NamedTemporaryFile(
            mode="w", suffix=".lua", delete=False, encoding="utf-8"
        ) as lua_f,
    ):
        header_path, lua_filter_path = tex_f.name, lua_f.name
        tex_f.write(header)
        tex_f.flush()
        _write_lua_filter(lua_filter_path, cjk_fonts, main_cjk_key)
        lua_f.flush()

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
            lua_filter_path,
        ]
        result = subprocess.run(
            cmd, capture_output=True, text=True, check=False, cwd=cwd
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"pandoc failed: {result.stderr.strip() or result.stdout.strip() or 'code ' + str(result.returncode)}"
            )
        if result.stderr:
            print(result.stderr, file=sys.stderr)
    finally:
        if os.path.exists(header_path):
            os.unlink(header_path)
        if os.path.exists(lua_filter_path):
            os.unlink(lua_filter_path)


def _process_html(
    html_body: str, source_dir: str | None, lang: str, config: FontConfig
) -> tuple[str, DocumentMetadata]:
    """Run the HTML post-processing pipeline and return the document plus its metadata."""
    if _is_full_document(html_body):
        metadata = _extract_metadata(html_body)
        full = _inject_css(_strip_metadata_tags(html_body), config)
    else:
        metadata = DocumentMetadata()
        full = _wrap_html(html_body, lang, config)

    if source_dir:
        full = _resolve_image_src(full, source_dir)

    full = _h6_to_bold_italic_para(
        _ruby_to_span(
            _strip_variation_selectors(
                _strip_image_titles(_strip_footnote_backref(_normalize_quotes(full)))
            )
        )
    )
    return full, metadata


def _extract_lang(html: str) -> str | None:
    """Read the ``lang`` attribute from the document's ``<html>`` tag, if present."""
    match = _HTML_LANG_RE.search(html)
    return match.group(1).strip() if match else None


# ===========================================================================
# Public API Gateways & Global Entry Points
# ===========================================================================


def convert(
    markdown_text: str,
    output_path: str | None = None,
    *,
    source_dir: str | None = None,
    lang: str | None = None,
    main_font: str | None = None,
    head_font: str | None = None,
    cjk_font: str | None = None,
    cjk_fonts: Mapping[str, str] | None = None,
    mono_font: str | None = None,
    symbol_font: str | None = None,
) -> bytes | None:
    """Convert Markdown (or raw HTML) text into a compiled PDF.

    If ``output_path`` is given, the PDF is written there and ``None`` is
    returned; otherwise the PDF bytes are returned directly.
    """
    html_body = (
        markdown_text
        if _is_html(markdown_text)
        else MarkdownToHTML().convert(markdown_text)
    )
    doc_lang = lang or _extract_lang(html_body) or "en"
    main_cjk_key = _cjk_key_for_lang(doc_lang)

    base_cjk = dict(CJK_DEFAULT_FONTS)
    base_cjk.update({k: v for k, v in (cjk_fonts or {}).items() if v})
    if cjk_font:
        base_cjk[main_cjk_key] = cjk_font

    config = FontConfig(
        main=_select_font(main_font or DEFAULT_MAIN_FONT, []),
        head=_select_font(head_font or DEFAULT_HEAD_FONT, []),
        mono=_select_font(mono_font or DEFAULT_MONO_FONT, []),
        symbol=_select_font(symbol_font or DEFAULT_SYMBOL_FONT, []),
        cjk={k: _select_font(base_cjk[k], []) for k in CJK_FONT_KEYS},
    )

    full_html, metadata = _process_html(html_body, source_dir, doc_lang, config)
    if not metadata.lang:
        metadata = DocumentMetadata(
            title=metadata.title,
            author=metadata.author,
            description=metadata.description,
            keywords=metadata.keywords,
            lang=doc_lang,
            published=metadata.published,
        )

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".html", delete=False, encoding="utf-8"
    ) as f:
        html_path = f.name
        f.write(full_html)

    kwargs = {
        "metadata": metadata,
        "config": config,
        "cjk_fonts": config.cjk,
        "main_cjk_key": main_cjk_key,
        "cwd": source_dir,
    }
    pdf_path: str | None = None
    try:
        if output_path:
            _pandoc_html_to_pdf(html_path, output_path, **kwargs)
            return None

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            pdf_path = tmp.name

        _pandoc_html_to_pdf(html_path, pdf_path, **kwargs)
        with open(pdf_path, "rb") as pdf_file:
            return pdf_file.read()
    finally:
        if os.path.exists(html_path):
            os.unlink(html_path)
        if output_path is None and pdf_path and os.path.exists(pdf_path):
            os.unlink(pdf_path)


def convert_file(
    input_path: str,
    output_path: str | None = None,
    *,
    lang: str | None = None,
    main_font: str | None = None,
    head_font: str | None = None,
    cjk_font: str | None = None,
    cjk_fonts: Mapping[str, str] | None = None,
    mono_font: str | None = None,
    symbol_font: str | None = None,
) -> bytes | None:
    """Read the file at ``input_path`` and convert its contents to a PDF.

    Relative image paths are resolved against the input file's directory.
    """
    with open(input_path, encoding="utf-8") as f:
        text = f.read()

    return convert(
        text,
        output_path,
        source_dir=os.path.dirname(os.path.abspath(input_path)),
        lang=lang,
        main_font=main_font,
        head_font=head_font,
        cjk_font=cjk_font,
        cjk_fonts=cjk_fonts,
        mono_font=mono_font,
        symbol_font=symbol_font,
    )
