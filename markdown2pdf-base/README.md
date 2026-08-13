# markdown2pdf-base

Convert Markdown to PDF using [markdown2html5-base](https://github.com/nobus-1967/markdown2html5-base) and pandoc (xelatex).

Version 0.2.2 — feature-aligned with `markdown2html5-base` 0.2.4. Inline code is wrapped with `seqsplit` so long runs break across lines; heading code uses plain `\texttt` (seqsplit is unsafe in moving arguments).

## Requirements

- `markdown2html5-base >= 0.2.4` (Python package)
- `pandoc` with Lua filter support
- `xelatex` (TeX Live) with `fontspec`, `xeCJK`, `ruby`, `fvextra`, `framed`, `seqsplit`
- Fonts (see [Fonts](#fonts)); run `fc-list`/`fc-match` from fontconfig for fallback detection

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
  --lang ja --main-font "Noto Sans" --cjk-font "Noto Sans CJK JP" \
  --mono-font "Noto Sans Mono" --symbol-font "Symbola"
```

### Options

| Option           | Description                                          | Default           |
| ---------------- | ---------------------------------------------------- | ----------------- |
| `--lang`         | Document language (BCP 47, e.g. `ja`, `zh-CN`)       | from front matter |
| `--main-font`    | Main text font                                       | `Noto Sans`       |
| `--cjk-font`     | CJK font (overrides language-based default)          | by language       |
| `--mono-font`    | Monospace font                                       | `Noto Sans Mono`  |
| `--symbol-font`  | Symbol/emoji font                                    | `Symbola`         |

## Python API

```python
from markdown2pdf_base import convert, convert_file

convert_file("input.md", "output.pdf")  # write to file
data = convert("# Hello", None)  # returns PDF bytes
data = convert("# こんにちは", None, lang="ja")  # language-driven CJK font
```

## Features

All `markdown2html5-base` 0.2.3 operations are supported:

- Headings (H1–H6) with custom IDs (H6 rendered as bold-italic paragraph for PDF typography)
- Bold, italic, strikethrough, highlight, subscript, superscript, underline
- Inline code and fenced code blocks
- Links and images (relative paths resolved automatically)
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

Recognized keys: `lang`, `title`, `author`, `description`, `keywords`, `published`. Front matter values are used only for PDF metadata (Title,
Author, Subject, Keywords via `\hypersetup`) and for CJK font selection via `lang` — they never appear as text in the PDF body. `lang` selects the default CJK font (see below).

## Fonts

Default fonts, per document language:

| Role   | Default font          |
| ------ | --------------------- |
| Main   | `Noto Sans`           |
| Mono   | `Noto Sans Mono`      |
| CJK    | `Noto Sans CJK JP`    |
| CJK    | `Noto Sans CJK SC`    |
| CJK    | `Noto Sans CJK TC`    |
| Symbol | `Symbola`             |

CJK font selection by `lang`:

- `ja` / `ja-*` → `Noto Sans CJK JP`
- `zh` / `zh-Hans` / `zh-CN` → `Noto Sans CJK SC`
- `zh-Hant` / `zh-TW` / `zh-HK` → `Noto Sans CJK TC`

### Substitution fallbacks

When a default font is not installed, `markdown2pdf-base` detects availability
via `fc-list` and substitutes the first installed font, emitting a warning:

| Role   | Fallback chain                                                     |
| ------ | ------------------------------------------------------------------ |
| Main   | Noto Sans → DejaVu Sans → Liberation Sans → FreeSans               |
| Mono   | Noto Sans Mono → DejaVu Sans Mono → Liberation Mono → FreeMono     |
| CJK JP | Noto Sans CJK JP → Source Han Sans JP → Sarasa Gothic → IPAPGothic |
| CJK SC | Noto Sans CJK SC → Source Han Sans SC → Sarasa Gothic SC → I.Ming  |
| CJK TC | Noto Sans CJK TC → Source Han Sans TC → Sarasa Gothic TC → I.Ming  |
| Symbol | Symbola → Noto Sans Symbols → DejaVu Sans                          |

The generated LaTeX header additionally guards every font declaration with `\IfFontExistsTF` as a final safety net.

## Notes

- Emoji and symbols are detected by Unicode block (including Mathematical Operators) in the Lua filter and rendered through the symbol font, so adjacent text always stays in the main font (no `ucharclasses` font leaking).
- Ruby annotations are converted to LaTeX `\ruby{}{}` via a Lua filter.
- Footnotes render as a superscript link plus a footnotes list at the end.
- Inline code is printed in the mono font colored mid-gray (`RGB(90,90,90)`). Long runs that would overflow a line are wrapped with `seqsplit` (it breaks anywhere, without hyphens) via the `\seqcode` macro; short runs and any code inside headings use plain `\texttt` — `seqsplit` is unsafe in moving arguments such as bookmarks and the table of contents.
- Fenced code blocks are typeset in the mono font inside a light gray frame (`RGB(180,180,180)`) via an `fvextra` `verbatim` override with line breaking enabled (`breaklines`); wrapped lines show no break symbol.
- The running header (`title (author: published)`) in the top margin is colored mid-gray (`RGB(90,90,90)`).
