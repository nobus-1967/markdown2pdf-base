import argparse
import sys

from markdown2pdf_base import convert, convert_file


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Convert Markdown to PDF using markdown2html5-base + pandoc"
    )
    parser.add_argument(
        "input", nargs="?", type=str, help="Input Markdown file (defaults to stdin)"
    )
    parser.add_argument("-o", "--output", type=str, help="Output PDF file")
    parser.add_argument(
        "--cjk-font", default=None, help="CJK font name (default: Noto Sans CJK SC)"
    )
    parser.add_argument(
        "--mono-font",
        default=None,
        help="Monospace font name (default: Noto Sans Mono CJK SC)",
    )
    parser.add_argument(
        "--symbol-font",
        default="Symbola",
        help="Symbol/emoji font name (default: Symbola)",
    )

    args = parser.parse_args()

    if not args.input and sys.stdin.isatty():
        parser.print_help()
        sys.exit(1)

    kwargs = {}
    if args.cjk_font:
        kwargs["cjk_font"] = args.cjk_font
    if args.mono_font:
        kwargs["mono_font"] = args.mono_font
    if args.symbol_font:
        kwargs["symbol_font"] = args.symbol_font

    if args.input:
        output = args.output or args.input.rsplit(".", 1)[0] + ".pdf"
        convert_file(args.input, output, **kwargs)
    else:
        md_text = sys.stdin.read()
        pdf_bytes = convert(md_text, None, **kwargs)
        sys.stdout.buffer.write(pdf_bytes)


if __name__ == "__main__":
    main()
