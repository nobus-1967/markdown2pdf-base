import os
import re
import subprocess
import sys
import tempfile

from markdown2html5_base import MarkdownToHTML


DEFAULT_CJK_FONT = "Noto Sans CJK SC"
DEFAULT_MONO_FONT = "Noto Sans Mono CJK SC"
DEFAULT_SYMBOL_FONT = "Symbola"


def _resolve_image_src(html: str, source_dir: str) -> str:
    def _abs(m: re.Match) -> str:
        src = m.group(1)
        if src.startswith(("http://", "https://", "data:", "/")):
            return m.group(0)
        resolved = os.path.normpath(os.path.join(source_dir, src))
        return m.group(0).replace(f'src="{src}"', f'src="{resolved}"')

    return re.sub(r'src="([^"]+)"', _abs, html)


def _sanitize_footnote_ids(html: str) -> str:
    html = re.sub(r'\bid="(fn(?:ref)?):', r'id="\1-', html)
    html = re.sub(r'\bhref="#(fn(?:ref)?):', r'href="#\1-', html)
    return html


def _ruby_to_span(html: str) -> str:
    return re.sub(
        r"<ruby>([^<]+)<rp>\(</rp><rt>([^<]+)</rt><rp>\)</rp></ruby>",
        lambda m: f'<span class="ruby" rt="{m.group(2)}">{m.group(1)}</span>',
        html,
    )


_FILTER_CODE = """function Span(el)
  local rt = el.attributes['rt']
  if rt then
    el.attributes['rt'] = nil
    local base = pandoc.utils.stringify(el.content)
    return pandoc.RawInline('latex', '\\\\ruby{' .. base .. '}{' .. rt .. '}')
  end
end
"""


def _write_ruby_filter(path: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        f.write(_FILTER_CODE)


def _wrap_html(body: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
  body {{ font-family: "{DEFAULT_CJK_FONT}", sans-serif; font-size: 11pt; line-height: 1.6; max-width: 42em; margin: 2em auto; padding: 0 1em; }}
  pre, code {{ font-family: "{DEFAULT_MONO_FONT}", monospace; font-size: 9.5pt; }}
  pre {{ background: #f5f5f5; padding: 0.8em; border-radius: 4px; overflow-x: auto; }}
  code {{ background: #f0f0f0; padding: 0.15em 0.3em; border-radius: 3px; }}
  pre code {{ background: none; padding: 0; }}
  table {{ border-collapse: collapse; width: 100%; margin: 1em 0; }}
  th, td {{ border: 1px solid #ccc; padding: 0.4em 0.6em; text-align: left; }}
  th {{ background: #eee; }}
  blockquote {{ margin: 0.5em 0; padding: 0.2em 1em; border-left: 4px solid #ccc; color: #555; }}
  hr {{ border: none; border-top: 2px solid #ccc; margin: 1.5em 0; }}
  img {{ max-width: 100%; }}
  .footnotes {{ margin-top: 2em; font-size: 0.9em; color: #666; }}
  mark {{ background: #ffec8b; padding: 0.1em 0.2em; }}
  s {{ color: #999; }}
  sub {{ font-size: 0.75em; }}
  sup {{ font-size: 0.75em; }}
  ins {{ text-decoration: underline; }}
  dl {{ margin: 0.5em 0; }}
  dt {{ font-weight: bold; margin-top: 0.3em; }}
  dd {{ margin-left: 1.5em; }}
  ruby {{ ruby-align: center; }}
  rp {{ display: none; }}
</style>
</head>
<body>
{body}
</body>
</html>"""


def _make_latex_header(cjk_font: str, mono_font: str, symbol_font: str) -> str:
    return f"""\\usepackage{{fontspec}}
\\usepackage{{xeCJK}}
\\usepackage{{ruby}}
\\setmainfont{{{symbol_font}}}
\\setCJKmainfont{{{cjk_font}}}
\\setmonofont{{{mono_font}}}
"""


def convert(
    markdown_text: str,
    output_path: str | None = None,
    *,
    source_dir: str | None = None,
    cjk_font: str | None = None,
    mono_font: str | None = None,
    symbol_font: str | None = None,
) -> bytes | None:
    html_body = MarkdownToHTML().convert(markdown_text)
    full_html = _wrap_html(html_body)

    if source_dir:
        full_html = _resolve_image_src(full_html, source_dir)
    full_html = _sanitize_footnote_ids(full_html)
    full_html = _ruby_to_span(full_html)

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".html", delete=False, encoding="utf-8"
    ) as f:
        html_path = f.name
        f.write(full_html)

    try:
        if output_path:
            _pandoc_html_to_pdf(
                html_path,
                output_path,
                cjk_font=cjk_font,
                mono_font=mono_font,
                symbol_font=symbol_font,
            )
            return None
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            pdf_path = tmp.name
        _pandoc_html_to_pdf(
            html_path,
            pdf_path,
            cjk_font=cjk_font,
            mono_font=mono_font,
            symbol_font=symbol_font,
        )
        with open(pdf_path, "rb") as f:
            data = f.read()
        os.unlink(pdf_path)
        return data
    finally:
        os.unlink(html_path)


def convert_file(
    input_path: str,
    output_path: str | None = None,
    *,
    cjk_font: str | None = None,
    mono_font: str | None = None,
    symbol_font: str | None = None,
) -> bytes | None:
    with open(input_path, encoding="utf-8") as f:
        md_text = f.read()
    source_dir = os.path.dirname(os.path.abspath(input_path))
    return convert(
        md_text,
        output_path,
        source_dir=source_dir,
        cjk_font=cjk_font,
        mono_font=mono_font,
        symbol_font=symbol_font,
    )


def _pandoc_html_to_pdf(
    html_path: str,
    pdf_path: str,
    *,
    cjk_font: str | None = None,
    mono_font: str | None = None,
    symbol_font: str | None = None,
) -> None:
    cf = cjk_font or DEFAULT_CJK_FONT
    mf = mono_font or DEFAULT_MONO_FONT
    sf = symbol_font or DEFAULT_SYMBOL_FONT

    header = _make_latex_header(cf, mf, sf)
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".tex", delete=False, encoding="utf-8"
    ) as f:
        header_path = f.name
        f.write(header)

    filter_path = os.path.join(tempfile.gettempdir(), "md2pdf_ruby_filter.lua")
    _write_ruby_filter(filter_path)

    try:
        cmd = ["pandoc", html_path, "-o", pdf_path, "--pdf-engine=xelatex"]
        cmd.extend(["-H", header_path])
        cmd.extend(["--lua-filter", filter_path])
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            msg = (
                result.stderr.strip()
                or result.stdout.strip()
                or f"pandoc exited with code {result.returncode}"
            )
            raise RuntimeError(f"pandoc failed: {msg}")
        if result.stderr:
            print(result.stderr, file=sys.stderr)
    finally:
        os.unlink(header_path)
