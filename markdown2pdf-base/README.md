# markdown2pdf-base

Convert Markdown to PDF using [markdown2html5-base](https://github.com/nobus-1967/markdown2html5-base) and pandoc (xelatex). Version 0.6.3 — requires `markdown2html5-base` 0.6.1, so identifiers and link targets are rendered correctly.

Since 0.6.3: the page can be turned to landscape with `--page landscape` (or `page_layout="landscape"` in Python), which makes `geometry` swap paper width and height while the 25.4 mm margins stay put — so landscape is a wider and shorter text block, and portrait remains the default, leaving every document that does not ask for landscape laid out exactly as before.

Since 0.6.2: headings wrap only at spaces — `\RaggedRight` is re-issued inside `\titleformat` so the stretch is measured in the heading's own font size and a title never crosses the right margin. A code span in a title breaks at a space or after one of the word-joining characters `- _ / = \` and never inside a word, and H6 — a paragraph rather than a `\titleformat` heading — has the paragraph break tokens taken back out of it so it breaks only at its spaces too, which leaves a code span in an H6 with fewer opportunities than in H1–H5.

Since 0.6.1: `markdown2html5-base` 0.6.1 is required, and an underscore no longer opens or closes emphasis inside a word, so `my_module_name` keeps its underscores in the PDF and link targets are taken verbatim instead of being mangled.

Since 0.6.0: nested lists are supported — sublists that `markdown2html5-base` 0.6.0 nests inside their parent `<li>` keep their level, and bullet/number markers follow the nesting depth. This is a feature-alignment release; the PDF pipeline emits each nesting level as a proper nested `itemize`/`enumerate`, matching the HTML structure of `markdown2html5-base` 0.6.0.

Since 0.5.3: tables, the `%20` path decoding, highlighted text and vertical spacing are typeset as described under [Notes](#notes), and images are set as in-flow figures with a caption below. Any `## … {#toc}` heading (in any language) is rendered italic, matching the `h2#toc` CSS rule of `markdown2html5-base` 0.5.3.

Since 0.3.2: inline code is set in plain black mono and broken as described under [Notes](#notes); per-language CJK fonts can be used simultaneously (see [CLI Usage](#cli-usage)); ruby annotations keep the doc-language CJK font.

## Requirements

- `markdown2html5-base >= 0.6.1` (Python package)
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

# Landscape page instead of portrait
markdown2pdf-base input.md -o output.pdf --page landscape
```

### Options

| Option            | Description                                          | Default             |
| ----------------- | ---------------------------------------------------- | ------------------- |
| `--lang`          | Document language (BCP 47, e.g. `ja`, `zh-CN`)       | from front matter   |
| `--page`          | Page orientation: `portrait` or `landscape`          | `portrait`          |
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

The per-language `--cjk-*-font` options can be used simultaneously in one document. Text is routed to the matching CJK font by script: Hiragana and Katakana use the Japanese font, Hangul uses the Korean font, and Han characters use the font for the document language (see the `lang` mapping below).

## Python API

```python
from markdown2pdf_base import convert, convert_file

convert_file("input.md", "output.pdf")  # write to file
data = convert("# Hello", None)  # returns PDF bytes
data = convert("# こんにちは", None, lang="ja")  # language-driven CJK font
data = convert("# Hi", None, main_font="Noto Serif", head_font="Noto Sans")
# Landscape page instead of the default portrait
data = convert("# Hello", None, page_layout="landscape")
# Per-language CJK fonts, usable simultaneously
data = convert(
    "# 混合",
    None,
    lang="ja",
    cjk_fonts={"ja": "Noto Serif CJK JP", "kr": "Noto Serif CJK KR"},
)
```

## Features

All `markdown2html5-base` 0.6.1 operations are supported:

- Headings (H1–H6) with custom IDs, including TOC (H6 rendered as a sans-serif bold-italic paragraph for PDF typography, with the `id` preserved as an anchor so internal links resolve); long headings stay inside the page margins and are never split inside a word
- Bold, italic, strikethrough, highlight, subscript, superscript, underline (`<u>` tag). An underscore inside a word is literal, so identifiers such as `my_module_name` and `max_retry_count` keep their underscores; `*italic*` and `_italic_` are unaffected
- Inline code and fenced code blocks
- Links and images (relative paths resolved automatically; link destinations are taken verbatim, so underscores, asterisks and balanced parentheses in a URL are preserved and the resulting annotation points at the real target; a link title such as `[text](url "Title")` is accepted and kept out of the URL, but PDF has no tooltip for it, so the title does not appear in the output — only image titles such as `![alt](img.png "Title")` become visible figure captions; images wrapped in `<figure>` render in-flow scaled to the line width, with an italic, left-aligned `figcaption` below and no auto-numbering; untitled images render without a caption or "Figure N:" label)
- Horizontal rules
- Unordered, ordered, nested, and task lists (checkboxes)
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

Page layout uses 25.4 mm (1 inch) margins on all sides (`geometry`), with page numbers in the bottom margin and a running header in the top one. The paper itself is set by pandoc; `--page landscape` rotates it, which widens the text block and shortens the page.

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

Recognized keys: `lang`, `title`, `author`, `description`, `keywords`, `published` (with `date` accepted as an alias for `published`). Front matter values are used only for PDF metadata (Title, Author, Subject, Keywords via `\hypersetup`) and for CJK font selection via `lang` — they never appear as text in the PDF body. `lang` selects the default CJK font (see below).

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

Body text is set to **12pt**; headings H1–H5 are typeset in the heading font (`\titleformat`) at absolute sizes (24/21/18/15/13.5pt) independent of the document size, and H6 renders as a bold-italic heading-font line at the body size (**12pt**), matching the CSS `h6 { font-style: italic }` with the size reset to the base.

CJK font selection by `lang`:

- `ja` / `ja-*` → `Noto Serif CJK JP`
- `ko` / `ko-*` → `Noto Serif CJK KR`
- `zh` / `zh-Hans` / `zh-CN` → `Noto Serif CJK SC`
- `zh-Hant` / `zh-TW` / `zh-MO` → `Noto Serif CJK TC`
- `zh-HK` / `zh-Hant-HK` → `Noto Serif CJK HK`

Per-span language selection is also supported: a `<span lang="ja">`, `<span lang="zh-CN">`, `<span lang="zh-TW">`, `<span lang="zh-HK">` or `<span lang="ko">` renders with that language's CJK font, matching the CSS `span[lang="*"]` rules, so multiple CJK languages can coexist in one document. The same applies to block elements — `<p lang="ja">`, `<li lang="ko">`, `<blockquote lang="zh-CN">`, etc. — and combinations such as a `<span lang="...">` nested inside a `lang`-marked block.

The symbol font declaration in the generated LaTeX header is guarded with `\IfFontExistsTF` and falls back to `Symbola` when the requested font cannot be loaded by XeLaTeX (e.g. color fonts).

## Notes

- Emoji and symbols are detected by Unicode block (including Mathematical Operators) in the Lua filter and rendered through the symbol font, so adjacent text always stays in the main font (no `ucharclasses` font leaking).
- Ruby annotations are converted to LaTeX `\ruby{}{}` via a Lua filter.
- Definition lists are typeset with the term in bold on its own line, followed by each definition as indented, italicized text (multiple definitions per term are stacked vertically).
- Footnotes render as a superscript link plus a footnotes list at the end.
- Word wrapping matches the CSS `overflow-wrap` rules: break penalties are inserted after separator characters and `\allowbreak` after spaces/wide characters of plain text tokens, so long unbreakable words wrap in paragraphs, list items, blockquotes, definition terms/definitions, figure captions, and table cells (header/footer/body) instead of overflowing — matching `word-break: break-all`/`overflow-wrap: anywhere`. TeX still prefers breaking at spaces, so normal words are unaffected. Headings are the one exception and use the narrower rule below. Highlighted text (`<mark>`/`==…==`) is serialized without those break tokens so `soul`'s `\hl` (which drives the yellow marking) can parse its argument cleanly.
- Headings are set at 13.5–24 pt, so a single line holds far fewer words than body text and a heading is the first place a long word would overrun the margin. `\titleformat` re-issues `\RaggedRight` so the `2em` of `\rightskip` stretch is scaled to the heading size: with only the body-size stretch, TeX treats an overfull line as no worse than a loose one and lets the heading cross the margin. That stretch is also what keeps a heading flush left — every line starts at the left margin, and the right one is reached only where the words run out, never stretched to it. A heading breaks at its spaces and nowhere else, so unlike a paragraph it never offers a break after `, . ; : ! ? - / = _`; a title is not allowed to split a phrase that the text under it keeps whole. Hyphenation remains disabled (`\hyphenpenalty=10000`), exactly as in the body text, so a heading never gains a hyphen the HTML5 document does not have. Ideographs keep a break opportunity of their own, because CJK has no spaces. H6 is set as a paragraph rather than through `\titleformat`, but it is still a title: the paragraph break tokens are taken back out of it, so it also breaks at its spaces and nowhere else, and a code span inside it is not cut in half. The heading walker has to be invoked on the heading itself, because `pandoc.walk_inline` applies a filter table to the *descendant* elements of the element it is given and not to that element — a title therefore received neither the body break penalties nor the code-span rules while it was only being passed through the filter. The outcome does not depend on the document language: Russian, English and CJK titles all stay inside the margins even when no hyphenation patterns are loaded for the text.
- Tables are typeset with `longtable` (or `xltabular` with X-type `L`/`C`/`R` columns when any cell needs wrapping, matching the CSS `overflow-wrap` behavior). When a table switches to `xltabular`, **every** column is emitted as an X-type column so a natural-width column wider than the line cannot drive an X column to a negative size (which overflowed TeX's main memory); alignment is preserved (`C`/`R`/`L` vs `c`/`r`/`l`).
- Tables with a header row repeat it on every page via `longtable`'s `\endhead`. The header stays glued to its first body row: the leading `\hline` that would otherwise be emitted on that row is suppressed, so the breakable rule construction can never leave the header stranded alone at the bottom of a page (the rule under the header is drawn by the header's own trailing `\hline`).
- Image file paths containing spaces are URL-encoded by pandoc as `%20`; the Lua filter percent-decodes them back to real spaces before emitting `\includegraphics`, so the literal `%` never becomes a TeX comment that truncates the path.
- Inline code is printed in plain black mono (`\texttt`) with a two-tier break rule: it prefers line breaks at spaces and at separator characters (`- / = _ ( [ { , : ; \`); it breaks anywhere (`\penalty1000\allowbreak`) only when a long run has no such break point. Code inside a heading uses a narrower rule on purpose — a space or one of the word joiners `- _ / = \`, and never inside a word. Reusing the body's per-character penalty there does not work as a last resort: it is cheap enough that the line breaker takes it even when a space or a joiner was available, and a title comes out as `Pyth` / `on` or `kore` / `an-romanizer`. A heading span with no break point at all therefore overhangs the margin rather than being cut. The inserted break tokens are valid in a moving argument and survive a written and re-read `.toc` file. When an inline `<code lang="ja|zh-*|ko">` is marked as CJK, its CJK glyphs render in the matching CJK mono font (`Noto Sans Mono CJK …`); the break/wrap rules are identical for CJK-mono and standard mono.
- Task-list checkboxes render as a box (`☐`, `- [ ]`) or checked box (`☑`, `- [x]`) from the symbol font, followed by the task text, for both unordered (`ul`) and ordered (`ol`) task lists; the checkbox glyph is drawn 2pt smaller than the surrounding text from the symbol font, and the checked state maps to the CSS `accent-color: #000000` styling.
- Vertical whitespace is uniform: paragraphs are separated by the `\parskip` from `parskip.sty`, and the same `\parskip` (plus tuned margins) is applied before and after lists, blockquotes, code blocks and definition lists, so every text block sits at the same distance from its neighbors as consecutive paragraphs do. Images and tables keep either equal or up to twice that spacing, since their frames/captions already add height.
- Fenced/`<pre>` code blocks are typeset in black on a light gray (`RGB(245,245,245)`) background inside a black frame via an `fvextra` `verbatim` override with line breaking enabled (`breaklines`); wrapped lines show no break symbol. A CJK `lang="…"` on the block selects the matching CJK mono font for its CJK glyphs without changing the break behavior.
- Fenced code blocks with a language tag (`python`) show a `/language/` label in white on a full-width black bar attached to the top of the frame, rendered in the mono font.
- The running header (`title (author: published)`) in the top margin is rendered in black; `published` can be supplied as YAML front matter `date:` or `published:`.
