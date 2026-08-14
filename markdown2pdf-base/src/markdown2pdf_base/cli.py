import argparse
import sys

from markdown2pdf_base import __version__, convert, convert_file
from markdown2pdf_base.converter import (
    DEFAULT_CJK_JP_FONT,
    DEFAULT_MAIN_FONT,
    DEFAULT_MONO_FONT,
    DEFAULT_SYMBOL_FONT,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Convert Markdown to PDF using markdown2html5-base + pandoc"
    )
    parser.add_argument(
        "-v",
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
        help="Show the library version and exit",
    )
    parser.add_argument(
        "input", nargs="?", type=str, help="Input Markdown file (defaults to stdin)"
    )
    parser.add_argument("-o", "--output", type=str, help="Output PDF file")
    parser.add_argument("--lang", default=None, help="Document language (BCP 47)")
    parser.add_argument(
        "--main-font",
        default=None,
        help=f"Main text font name (default: {DEFAULT_MAIN_FONT})",
    )
    parser.add_argument(
        "--cjk-font",
        default=None,
        help=f"CJK font name (default by language: {DEFAULT_CJK_JP_FONT})",
    )
    parser.add_argument(
        "--mono-font",
        default=None,
        help=f"Monospace font name (default: {DEFAULT_MONO_FONT})",
    )
    parser.add_argument(
        "--symbol-font",
        default=None,
        help=f"Symbol/emoji font name (default: {DEFAULT_SYMBOL_FONT})",
    )

    args = parser.parse_args()

    if not args.input and sys.stdin.isatty():
        parser.print_help()
        sys.exit(1)

    kwargs = {}
    if args.lang:
        kwargs["lang"] = args.lang
    if args.main_font:
        kwargs["main_font"] = args.main_font
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
