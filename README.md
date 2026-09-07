# markdown2pdf-base

Convert Markdown to PDF using [markdown2html5-base](https://github.com/nobus-1967/markdown2html5-base) and pandoc (xelatex).

The generated PDF file matches the HTML5 document with the built-in styles (used in markdown2html5-base), so the pandoc output was overridden in many cases.

## Features

All markdown2html5-base features are supported:

- Headings (H1–H6) with custom IDs
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
- Wrapping long strings (inline code and code blocks)
- HTML comments (`[comment]: #`)
- Backslash escaping

Now you can change fonts for PDF output, including `CJK` fonts: see [Font Stacks Documentation](https://github.com/nobus-1967/fonts-stack-cjk/blob/main/Fonts.md) to choose right fonts.

## How it works

You can compare conversion results: original [Markdown file](./test_page/Test_Page.md) → use markdown2html5-base for [HTML5 file](./test_page/Test_Page.html) → use markdown2pdf-base for [PDF file](./test_page/Test_Page.pdf).

You can also evaluate the results using CLI: `markdown2pdf-base input.md -o output.pdf`

## Requirements

- `markdown2html5-base >= 0.5.0`;
- `pandoc` with Lua filter support;
- `xelatex` (TeX Live);
- `Noto` and `Symbola` fonts (see [README](./markdown2pdf-base/README.md) for details).
