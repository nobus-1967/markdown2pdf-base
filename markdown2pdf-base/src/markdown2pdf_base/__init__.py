"""Convert Markdown to PDF via markdown2html5-base and pandoc/xelatex."""

from markdown2pdf_base.converter import convert, convert_file

__version__ = "0.6.3"

__all__ = ["__version__", "convert", "convert_file"]
