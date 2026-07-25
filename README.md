# markdown2pdf-base

Convert Markdown to PDF using 
[markdown2html5-base](https://github.com/nobus-1967/markdown2html5-base) and p
andoc (xelatex).

## CLI Usage

```bash
# Convert a file
markdown2pdf-base input.md -o output.pdf

# Output name defaults to input name with .pdf extension
markdown2pdf-base input.md

# Read from stdin, write to stdout
cat input.md | markdown2pdf-base > output.pdf

# Custom fonts
markdown2pdf-base input.md -o output.pdf \
--cjk-font "Noto Sans CJK JP" --symbol-font "Symbola"
```

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
- HTML comments (`[comment]: #`)
- Backslash escaping
