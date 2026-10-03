# markdown2pdf-base

Convert Markdown to PDF using [markdown2html5-base](https://github.com/nobus-1967/markdown2html5-base) and pandoc (xelatex).

The generated PDF matches the HTML5 document rendered with `markdown2html5-base`'s built-in styles, so much of pandoc's own output is overridden. See the package [README](./markdown2pdf-base/README.md) for the full documentation.

## Features

All `markdown2html5-base` 0.6.1 operations are supported:

- Headings (H1–H6) with custom IDs, including TOC
- Bold, italic, strikethrough, highlight, subscript, superscript, underline (an underscore inside a word is literal, so `my_module_name` keeps its underscores instead of being set as *mymodulename*)
- Inline code and fenced code blocks
- Links and images (relative paths resolved automatically; link URLs keep underscores, asterisks and balanced parentheses, so the annotation points at the real target)
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
- Wrapping long strings (inline code and code blocks; in a heading only at spaces and word joiners)
- HTML comments (`[comment]: #`)
- Backslash escaping
- Portrait or landscape page (`--page landscape`)

Fonts for PDF output can be overridden, including the CJK fonts: see [Font Stacks Documentation](https://github.com/nobus-1967/fonts-stack-cjk/blob/main/Fonts.md) to choose suitable fonts.

## How it works

You can compare conversion results: the original [Markdown file](./test_page/Test_Page.md) → the [HTML5 file](./test_page/Test_Page.html) via markdown2html5-base → the [PDF file](./test_page/Test_Page.pdf) via markdown2pdf-base.

You can also check the result from the command line: `markdown2pdf-base input.md -o output.pdf`. Add `--page landscape` for a rotated page (portrait by default); see the [package README](./markdown2pdf-base/README.md) for the full option list.

## Requirements

- `markdown2html5-base` >= 0.6.1
- `pandoc` with Lua filter support
- `xelatex` (TeX Live)
- `Noto` and `Symbola` fonts (see the [package README](./markdown2pdf-base/README.md) for details)
