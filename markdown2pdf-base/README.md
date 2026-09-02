# markdown2pdf-base

Convert Markdown to PDF using [markdown2html5-base](https://github.com/nobus-1967/markdown2html5-base) and pandoc (xelatex).

Version 0.3.3 — feature-aligned with `markdown2html5-base` 0.3.7. Images are rendered as in-flow figures scaled to the line width with an italic, left-aligned `figcaption` below (no float, no auto-numbering); untitled images get no caption or "Figure N:" label. Also from 0.3.2: inline code renders in plain black mono; long runs break across lines via `\allowbreak`; heading code uses plain `\texttt` (macros/breaks are unsafe in moving arguments); per-language CJK fonts (`--cjk-{ja,cn,tw,hk,kr}-font`) can be used simultaneously; ruby annotations keep the doc-language CJK font.

## Requirements

- `markdown2html5-base >= 0.3.7` (Python package)
- `pandoc` with Lua filter support
- `xelatex` (TeX Live) with `fontspec`, `xeCJK`, `ruby`, `fvextra`, `framed`, `titlesec`, `mdframed`, `longtable`, `colortbl`
- Fonts (see [Fonts](#fonts)): `Noto Fonts` (`Noto Sans`, `Noto Serif`, `Noto Sans Mono`, `Noto Serif CJK JP/SC/TC/HK/KR`) and `Symbola`; run `fc-list`/`fc-match` from `fontconfig` to verify availability

## CLI Usage

```bash
# Convert a file
markdown2pdf-base input.md -o output.pdf

# Output name defaults to input name with .pdf extension
markdown2pdf-base input.md

# Read from stdin, write to stdout
cat input.md | markdown2pdf-base > output.pdf

# Custom fonts and document language
markdown2pdf-base input.md -o output.pdf \
  --lang ja --main-font "Noto Serif" --head-font "Noto Sans" \
  --cjk-ja-font "Noto Serif CJK JP" --mono-font "Noto Sans Mono" \
  --symbol-font "Symbola"
```

### Options

| Option            | Description                                          | Default             |
| ----------------- | ---------------------------------------------------- | ------------------- |
| `--lang`          | Document language (BCP 47, e.g. `ja`, `zh-CN`)       | from front matter   |
| `--main-font`     | Main text font                                       | `Noto Serif`        |
| `--head-font`     | Heading font                                         | `Noto Sans`         |
| `--cjk-font`      | CJK font override for the document language          | by language         |
| `--cjk-ja-font`   | Japanese CJK font                                    | `Noto Serif CJK JP` |
| `--cjk-cn-font`   | Simplified Chinese CJK font                          | `Noto Serif CJK SC` |
| `--cjk-tw-font`   | Traditional Chinese (Taiwan) CJK font                | `Noto Serif CJK TC` |
| `--cjk-hk-font`   | Hong Kong CJK font                                   | `Noto Serif CJK HK` |
| `--cjk-kr-font`   | Korean CJK font                                      | `Noto Serif CJK KR` |
| `--mono-font`     | Monospace font                                       | `Noto Sans Mono`    |
| `--symbol-font`   | Symbol/emoji font                                    | `Symbola`           |

The per-language `--cjk-*-font` options can be used simultaneously in one
document. Text is routed to the matching CJK font by script: Hiragana and
Katakana use the Japanese font, Hangul uses the Korean font, and Han
characters use the font for the document language (see the `lang` mapping
below).

## Python API

```python
from markdown2pdf_base import convert, convert_file

convert_file("input.md", "output.pdf")  # write to file
data = convert("# Hello", None)  # returns PDF bytes
data = convert("# こんにちは", None, lang="ja")  # language-driven CJK font
data = convert("# Hi", None, main_font="Noto Serif", head_font="Noto Sans")
# Per-language CJK fonts, usable simultaneously
data = convert(
    "# 混合",
    None,
    lang="ja",
    cjk_fonts={"ja": "Noto Serif CJK JP", "kr": "Noto Serif CJK KR"},
)
```

## Features

All `markdown2html5-base` 0.3.7 operations are supported:

- Headings (H1–H6) with custom IDs (H6 rendered as bold-italic paragraph for PDF typography, with the `id` preserved as an anchor so internal links resolve)
- Bold, italic, strikethrough, highlight, subscript, superscript, underline (`<u>` tag)
- Inline code and fenced code blocks
- Links and images (relative paths resolved automatically; image titles such as `![alt](img.png "Title")` become figure captions — images wrapped in `<figure>` render in-flow scaled to the line width, with an italic, left-aligned `figcaption` below and no auto-numbering; untitled images render without a caption or "Figure N:" label)
- Horizontal rules
- Unordered, ordered, and task lists (checkboxes)
- Blockquotes
- Tables with alignment and footer (thead/tbody/tfoot)
- Definition lists (dl/dt/dd)
- Footnotes with back-references
- Ruby annotations / furigana (`{日本語|にほんご}`)
- Emoji shortcodes (`:rocket:`, `:heart:`, etc.)
- Typography symbols (`(c)`, `(tm)`, `(r)`, `...`, `---`, `--`, `!=`, etc.)
- Smart quotes
- Hard line breaks (trailing `\` or two spaces)
- HTML comments (`[comment]: #`)
- Backslash escaping

Page layout uses 25.4 mm (1 inch) margins on all sides (`geometry`). A running header showing `title (author: published)` is drawn in the top margin, and page numbers are placed in the bottom margin.

### YAML front matter

YAML front matter is parsed into an HTML5 document shell, so the PDF is built from the document as a whole (no duplicated `<html>` wrapper):

```markdown
---
lang: en
title: Test Page
author: nobus-1967
description: A description
keywords: markdown, pdf
published: 2026-08-09
---
# Heading 1
Body text.
```

Recognized keys: `lang`, `title`, `author`, `description`, `keywords`, `published` (with `date` accepted as an alias for `published`). Front matter values are used only for PDF metadata (Title,
Author, Subject, Keywords via `\hypersetup`) and for CJK font selection via `lang` — they never appear as text in the PDF body. `lang` selects the default CJK font (see below).

## Fonts

Default fonts:

| Role   | Default font          |
| ------ | --------------------- |
| Main   | `Noto Serif`          |
| Head   | `Noto Sans`           |
| Mono   | `Noto Sans Mono`      |
| CJK    | `Noto Serif CJK JP`   |
| CJK    | `Noto Serif CJK SC`   |
| CJK    | `Noto Serif CJK TC`   |
| CJK    | `Noto Serif CJK HK`   |
| CJK    | `Noto Serif CJK KR`   |
| Symbol | `Symbola`             |

Headings (H1–H6) are typeset in the heading font (`\newfontfamily{\headfont}` + `titlesec`); body text uses the main font.

CJK font selection by `lang`:

- `ja` / `ja-*` → `Noto Serif CJK JP`
- `ko` / `ko-*` → `Noto Serif CJK KR`
- `zh` / `zh-Hans` / `zh-CN` → `Noto Serif CJK SC`
- `zh-Hant` / `zh-TW` / `zh-MO` → `Noto Serif CJK TC`
- `zh-HK` / `zh-Hant-HK` → `Noto Serif CJK HK`

The symbol font declaration in the generated LaTeX header is guarded with `\IfFontExistsTF` and falls back to `Symbola` when the requested font cannot be loaded by XeLaTeX (e.g. color fonts).

## Notes

- Emoji and symbols are detected by Unicode block (including Mathematical Operators) in the Lua filter and rendered through the symbol font, so adjacent text always stays in the main font (no `ucharclasses` font leaking).
- Ruby annotations are converted to LaTeX `\ruby{}{}` via a Lua filter.
- Footnotes render as a superscript link plus a footnotes list at the end.
- Inline code is printed in plain black mono (`\texttt`). `\allowbreak` (a penalty node, unaffected by `\hyphenpenalty`) is inserted after every token, so long runs wrap anywhere instead of overflowing table cells and paragraph lines. Code inside headings uses plain `\texttt` (no breaks) — macros and break commands are unsafe in moving arguments such as bookmarks and the table of contents.
- Fenced code blocks are typeset in black on a light gray (`RGB(245,245,245)`) background inside a black frame via an `fvextra` `verbatim` override with line breaking enabled (`breaklines`); wrapped lines show no break symbol.
- Fenced code blocks with a language tag (`python`) show a `/language/` label in white on a full-width black bar attached to the top of the frame, rendered in the mono font.
- The running header (`title (author: published)`) in the top margin is rendered in black; `published` can be supplied as YAML front matter `date:` or `published:`.
