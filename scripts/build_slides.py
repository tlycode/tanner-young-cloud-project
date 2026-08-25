"""Build the presentation deck in PDF and PPTX form from the Markdown source.

    python scripts/build_slides.py

Reads  docs/slides/final-presentation.md
Writes docs/slides/final-presentation.pdf
       docs/slides/final-presentation.pptx

Requires (documentation-time tools, not app dependencies):
    pip install playwright python-pptx && python -m playwright install chromium
"""

import html
import re
from pathlib import Path

from playwright.sync_api import sync_playwright
from pptx import Presentation
from pptx.dml.color import RGBColor
from PIL import Image
from pptx.util import Emu, Inches, Pt

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "docs" / "slides" / "final-presentation.md"
PDF_OUT = ROOT / "docs" / "slides" / "final-presentation.pdf"
PPTX_OUT = ROOT / "docs" / "slides" / "final-presentation.pptx"

INK = RGBColor(0x1E, 0x1B, 0x4B)
MUTED = RGBColor(0x55, 0x5F, 0x7A)
ACCENT = RGBColor(0x4F, 0x46, 0xE5)
RULE = RGBColor(0xD8, 0xDD, 0xEA)
HEAD_BG = RGBColor(0xEE, 0xF2, 0xFF)


def parse_slides(md_text):
    """Split the Markdown into slides on '# Slide N — Title' headings."""
    body = re.sub(r"^---\n.*?\n---\n", "", md_text, count=1, flags=re.S)
    parts = re.split(r"\n---\n", body)
    slides = []
    for part in parts:
        part = part.strip()
        if not part:
            continue
        m = re.match(r"#\s+(.+?)\n(.*)", part, re.S)
        if not m:
            continue
        slides.append({"title": m.group(1).strip(), "body": m.group(2).strip()})
    return slides


# --------------------------------------------------------------------------
# PDF — render styled HTML in headless Chromium
# --------------------------------------------------------------------------

def md_inline(text):
    """Minimal inline Markdown -> HTML (escaping first)."""
    text = html.escape(text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"(?<![\w*])\*(?!\s)([^*\n]+?)(?<!\s)\*(?![\w*])", r"<em>\1</em>", text)
    text = re.sub(r"`(.+?)`", r"<code>\1</code>", text)
    return text


IMAGE_RE = re.compile(r"^!\[(?P<alt>[^\]]*)\]\((?P<src>[^)]+)\)$")


def block_to_html(block):
    """Convert one Markdown block (image, table, code fence, list, heading, para)."""
    lines = block.split("\n")

    m = IMAGE_RE.match(lines[0].strip())
    if m:
        # Resolve relative to the Markdown file so the PDF renderer can load it.
        src = (SRC.parent / m.group("src")).resolve()
        return f'<img class="figure" src="{src.as_uri()}" alt="{html.escape(m.group("alt"))}">'

    if lines[0].startswith("```"):
        code = "\n".join(lines[1:-1] if lines[-1].startswith("```") else lines[1:])
        return f"<pre>{html.escape(code)}</pre>"

    if lines[0].startswith("## "):
        return f"<h2>{md_inline(lines[0][3:])}</h2>"

    # Markdown table: header, separator, rows
    if len(lines) >= 2 and lines[0].startswith("|") and set(lines[1]) <= set("|-: "):
        head = [c.strip() for c in lines[0].strip("|").split("|")]
        rows = [[c.strip() for c in ln.strip("|").split("|")] for ln in lines[2:] if ln.startswith("|")]
        show_head = any(h for h in head)
        thead = ("<thead><tr>" + "".join(f"<th>{md_inline(h)}</th>" for h in head) + "</tr></thead>") if show_head else ""
        tbody = "<tbody>" + "".join(
            "<tr>" + "".join(f"<td>{md_inline(c)}</td>" for c in r) + "</tr>" for r in rows
        ) + "</tbody>"
        return f"<table>{thead}{tbody}</table>"

    if lines[0].lstrip().startswith("- "):
        items = "".join(f"<li>{md_inline(l.lstrip()[2:])}</li>" for l in lines if l.lstrip().startswith("- "))
        return f"<ul>{items}</ul>"

    return f"<p>{md_inline(' '.join(lines))}</p>"


def slide_html(slide, index, total):
    blocks = [b for b in re.split(r"\n\s*\n", slide["body"]) if b.strip()]
    content = "\n".join(block_to_html(b.strip()) for b in blocks)
    return f"""
<section class="slide">
  <div class="bar"></div>
  <h1>{md_inline(slide['title'])}</h1>
  <div class="content">{content}</div>
  <div class="foot"><span>Flask E-Commerce — Cloud Computing (UCBX)</span><span>{index} / {total}</span></div>
</section>"""


def build_pdf(slides):
    body = "\n".join(slide_html(s, i + 1, len(slides)) for i, s in enumerate(slides))
    page = f"""<!doctype html><meta charset="utf-8">
<style>
  @page {{ size: 13.333in 7.5in; margin: 0; }}
  * {{ box-sizing: border-box; }}
  body {{ margin: 0; font-family: -apple-system, 'Helvetica Neue', Arial, sans-serif; color: #1e1b4b; }}
  .slide {{ position: relative; width: 13.333in; height: 7.5in; padding: 0.62in 0.75in 0.55in;
            page-break-after: always; overflow: hidden; background: #fff; }}
  .bar {{ position: absolute; top: 0; left: 0; right: 0; height: 8px; background: #4f46e5; }}
  h1 {{ font-size: 30px; margin: 6px 0 4px; letter-spacing: -0.4px; }}
  h2 {{ font-size: 19px; color: #4f46e5; margin: 14px 0 8px; font-weight: 600;
        break-after: avoid; page-break-after: avoid; }}
  p {{ font-size: 14.5px; line-height: 1.5; margin: 7px 0; }}
  ul {{ margin: 6px 0 10px 20px; padding: 0; }}
  li {{ font-size: 14px; line-height: 1.55; margin-bottom: 4px; }}
  strong {{ color: #1e1b4b; }}
  em {{ font-style: italic; }}
  code {{ font-family: 'SF Mono', Menlo, monospace; font-size: 12.5px;
          background: #eef2ff; padding: 1px 5px; border-radius: 3px; }}
  pre {{ font-family: 'SF Mono', Menlo, monospace; font-size: 12px; line-height: 1.45;
         background: #0d1117; color: #c9d1d9; padding: 12px 14px; border-radius: 6px;
         margin: 8px 0; white-space: pre; overflow: hidden; }}
  table {{ border-collapse: collapse; margin: 8px 0 12px; width: auto; }}
  th {{ background: #eef2ff; text-align: left; font-size: 12.5px; padding: 6px 11px;
        border-bottom: 2px solid #c7d2fe; white-space: nowrap; }}
  td {{ font-size: 12.5px; padding: 5px 11px; border-bottom: 1px solid #e6e9f2; }}
  .content {{ column-count: 2; column-gap: 34px; column-fill: balance; max-height: 5.75in; }}
  .content > * {{ break-inside: avoid; }}
  .figure {{ display: block; width: 100%; max-width: 100%; height: auto;
              border: 1px solid #e6e9f2; border-radius: 6px; margin: 10px 0 12px; }}
  .foot {{ position: absolute; bottom: 0.34in; left: 0.75in; right: 0.75in;
           display: flex; justify-content: space-between;
           font-size: 10.5px; color: #8890a8; border-top: 1px solid #e6e9f2; padding-top: 7px; }}
</style>
{body}"""
    tmp = ROOT / "docs" / "slides" / "_slides.html"
    tmp.write_text(page)
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        p = browser.new_page()
        p.goto(tmp.as_uri())
        p.wait_for_timeout(500)
        p.pdf(path=str(PDF_OUT), width="13.333in", height="7.5in", print_background=True)
        browser.close()
    tmp.unlink()
    print(f"  wrote {PDF_OUT.relative_to(ROOT)}")


# --------------------------------------------------------------------------
# PPTX — native editable shapes via python-pptx
# --------------------------------------------------------------------------

def strip_md(text):
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"(?<![\w*])\*(?!\s)([^*\n]+?)(?<!\s)\*(?![\w*])", r"\1", text)
    return re.sub(r"`(.+?)`", r"\1", text)


def add_table(slide, lines, left, top, width):
    head = [c.strip() for c in lines[0].strip("|").split("|")]
    rows = [[c.strip() for c in ln.strip("|").split("|")] for ln in lines[2:] if ln.startswith("|")]
    if not rows:
        return top
    n_rows, n_cols = len(rows) + 1, len(head)
    height = Inches(0.26) * n_rows
    shape = slide.shapes.add_table(n_rows, n_cols, left, top, width, height)
    table = shape.table
    for c, text in enumerate(head):
        cell = table.cell(0, c)
        cell.text = strip_md(text)
        para = cell.text_frame.paragraphs[0]
        para.font.size = Pt(10)
        para.font.bold = True
        para.font.color.rgb = INK
        cell.fill.solid()
        cell.fill.fore_color.rgb = HEAD_BG
    for r, row in enumerate(rows, start=1):
        for c in range(n_cols):
            cell = table.cell(r, c)
            cell.text = strip_md(row[c]) if c < len(row) else ""
            para = cell.text_frame.paragraphs[0]
            para.font.size = Pt(9.5)
            para.font.color.rgb = INK
            cell.fill.solid()
            cell.fill.fore_color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
    return top + height + Inches(0.14)


def add_text(slide, text, left, top, width, size, *, bold=False, color=INK, mono=False):
    box = slide.shapes.add_textbox(left, top, width, Inches(0.3))
    tf = box.text_frame
    tf.word_wrap = True
    para = tf.paragraphs[0]
    run = para.add_run()
    run.text = text
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.color.rgb = color
    if mono:
        run.font.name = "Menlo"
    # ~2.1 chars per point of width at this size; estimate wrapped height
    est_chars = max(1, int(width / Emu(1) * 96 / 914400 * 0)) if False else None
    lines = max(1, len(text) // max(20, int((width / 914400) * (100 / size) * 9)) + 1)
    return top + Inches(0.03) + Inches(size / 72 * 1.35) * lines


def build_pptx(slides):
    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)
    blank = prs.slide_layouts[6]

    for idx, s in enumerate(slides, start=1):
        slide = prs.slides.add_slide(blank)

        # Accent bar
        bar = slide.shapes.add_shape(1, 0, 0, prs.slide_width, Inches(0.09))
        bar.fill.solid()
        bar.fill.fore_color.rgb = ACCENT
        bar.line.fill.background()

        # Title
        add_text(slide, s["title"], Inches(0.6), Inches(0.3), Inches(12.1), 26, bold=True)

        left_x, right_x = Inches(0.6), Inches(7.0)
        col_w = Inches(5.9)
        y = {left_x: Inches(1.15), right_x: Inches(1.15)}
        col = left_x

        blocks = [b.strip() for b in re.split(r"\n\s*\n", s["body"]) if b.strip()]
        for block in blocks:
            lines = block.split("\n")
            # Switch to the right column past the midpoint of the left one
            if y[col] > Inches(5.6) and col == left_x:
                col = right_x

            m = IMAGE_RE.match(lines[0].strip())
            if m:
                img_path = (SRC.parent / m.group("src")).resolve()
                if img_path.exists():
                    with Image.open(img_path) as im:
                        iw, ih = im.size
                    # A figure needs real estate to stay legible: if this column
                    # is too far down, move to the top of the next one.
                    if y[col] > Inches(3.4) and col == left_x:
                        col = right_x
                    disp_w = col_w
                    disp_h = int(disp_w * ih / iw)
                    # Cap by whatever vertical room is actually left in this
                    # column, so a figure placed low still lands on the slide.
                    footer_top = Inches(6.95)
                    max_h = min(Inches(3.1), max(Inches(1.0), footer_top - y[col]))
                    if disp_h > max_h:
                        disp_h = int(max_h)
                        disp_w = int(disp_h * iw / ih)
                    slide.shapes.add_picture(str(img_path), col, y[col], disp_w, disp_h)
                    y[col] += disp_h + Inches(0.14)
                continue

            if lines[0].startswith("```"):
                code = "\n".join(lines[1:-1] if lines[-1].startswith("```") else lines[1:])
                box = slide.shapes.add_textbox(col, y[col], col_w, Inches(0.3))
                tf = box.text_frame
                tf.word_wrap = False
                for i, ln in enumerate(code.split("\n")):
                    para = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
                    run = para.add_run()
                    run.text = ln
                    run.font.size = Pt(8.5)
                    run.font.name = "Menlo"
                    run.font.color.rgb = MUTED
                y[col] += Inches(0.15) * (len(code.split("\n")) + 1)

            elif lines[0].startswith("## "):
                y[col] = add_text(slide, strip_md(lines[0][3:]), col, y[col] + Inches(0.06),
                                  col_w, 15, bold=True, color=ACCENT)

            elif len(lines) >= 2 and lines[0].startswith("|") and set(lines[1]) <= set("|-: "):
                y[col] = add_table(slide, lines, col, y[col] + Inches(0.04), col_w)

            elif lines[0].lstrip().startswith("- "):
                for ln in lines:
                    if not ln.lstrip().startswith("- "):
                        continue
                    y[col] = add_text(slide, "•  " + strip_md(ln.lstrip()[2:]), col, y[col], col_w, 11)
                y[col] += Inches(0.06)

            else:
                y[col] = add_text(slide, strip_md(" ".join(lines)), col, y[col], col_w, 11.5)
                y[col] += Inches(0.05)

        # Footer
        add_text(slide, "Flask E-Commerce — Cloud Computing (UCBX)",
                 Inches(0.6), Inches(7.05), Inches(7.0), 9, color=RGBColor(0x88, 0x90, 0xA8))
        add_text(slide, f"{idx} / {len(slides)}", Inches(12.2), Inches(7.05),
                 Inches(0.6), 9, color=RGBColor(0x88, 0x90, 0xA8))

    prs.save(str(PPTX_OUT))
    print(f"  wrote {PPTX_OUT.relative_to(ROOT)}")


def main():
    slides = parse_slides(SRC.read_text())
    print(f"Parsed {len(slides)} slides from {SRC.relative_to(ROOT)}")
    for s in slides:
        print(f"   - {s['title']}")
    build_pdf(slides)
    build_pptx(slides)


if __name__ == "__main__":
    main()
