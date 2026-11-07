#!/usr/bin/env python3
"""build_pdf.py - render report.md to report.html and report.pdf without pandoc.

Usage:  python3 report/build_pdf.py [report/report.md]
Needs only Python and a Chromium-based browser (google-chrome / chromium) for the PDF.
Supports the Markdown subset used in report.md: headings, paragraphs, **bold**, *italic*,
`code`, links, pipe tables, block quotes, - and 1. lists, and raw HTML lines (figures).
If pandoc is installed, `pandoc report.md -o report.pdf --pdf-engine=xelatex` also works.
"""
import html, os, re, shutil, subprocess, sys

CSS = """
@page { size: A4; margin: 11mm 13mm 11mm 13mm; }
body { font-family: "DejaVu Serif", Georgia, serif; font-size: 9.2pt; line-height: 1.3; color: #222;
       max-width: 184mm; margin: 0 auto; }
h1 { font-size: 16pt; line-height: 1.2; margin: 0 0 4pt; }
h2 { font-size: 12.5pt; margin: 12pt 0 4pt; border-bottom: 0.6pt solid #bbb; padding-bottom: 1pt; }
h3 { font-size: 10.8pt; margin: 9pt 0 3pt; }
p { margin: 3pt 0 5pt; text-align: justify; }
ul, ol { margin: 2pt 0 5pt; padding-left: 17pt; } li { margin: 1pt 0; }
blockquote { margin: 4pt 0 6pt 14pt; padding: 2pt 8pt; border-left: 2pt solid #2a78d6; background: #f5f8fc; }
blockquote p { margin: 1pt 0; text-align: left; }
table { border-collapse: collapse; margin: 5pt auto 8pt; font-size: 8.6pt; page-break-inside: avoid; }
th, td { border-bottom: 0.5pt solid #ccc; padding: 2pt 6pt; text-align: left; }
th { border-bottom: 1pt solid #555; background: #f3f3f3; }
code { font-family: "DejaVu Sans Mono", monospace; font-size: 8.4pt; background: #f2f2f2; padding: 0 2pt; }
p.figrow { display: flex; gap: 4mm; justify-content: center; margin: 6pt 0 0; page-break-inside: avoid; }
p.figrow img { width: 44%; height: auto; object-fit: contain; }
p.figrow img:only-child { width: 58%; }
p.figrow img.wide { width: 60%; }
p.cap { font-size: 8.4pt; color: #444; text-align: left; margin: 2pt 4mm 9pt; page-break-before: avoid; }
em.meta { color: #555; }
"""


SUB = re.compile(r"(?<![\w\u0302])([A-Za-z\u0394\u03b5\u03b7\u03c0\u03c4]\u0302?)_([0-9A-Za-z\u03b5\u03c4]+)")


def inline(t):
    t = html.escape(t, quote=False)
    parts = t.split("`")            # odd parts are code spans: keep their underscores
    t = "`".join(SUB.sub(r"\1<sub>\2</sub>", x) if i % 2 == 0 else x for i, x in enumerate(parts))
    t = re.sub(r"`([^`]+)`", r"<code>\1</code>", t)
    t = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", t)
    t = re.sub(r"(?<![\w*])\*([^*\n]+)\*(?![\w*])", r"<em>\1</em>", t)
    t = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', t)
    return t


def convert(md):
    lines, out, i = md.split("\n"), [], 0
    while i < len(lines):
        ln = lines[i]
        if not ln.strip():
            i += 1; continue
        if ln.lstrip().startswith("<"):                       # raw HTML
            out.append(SUB.sub(r"\1<sub>\2</sub>", ln) if 'class="cap"' in ln else ln); i += 1; continue
        m = re.match(r"(#{1,6})\s+(.*)", ln)
        if m:
            n = len(m.group(1)); out.append(f"<h{n}>{inline(m.group(2))}</h{n}>"); i += 1; continue
        if ln.startswith("|"):                                # table
            rows = []
            while i < len(lines) and lines[i].startswith("|"):
                rows.append([c.strip() for c in lines[i].strip().strip("|").split("|")]); i += 1
            hdr, body = rows[0], [r for r in rows[1:] if not all(re.fullmatch(r":?-+:?", c) for c in r)]
            out.append("<table><thead><tr>" + "".join(f"<th>{inline(c)}</th>" for c in hdr) + "</tr></thead><tbody>"
                       + "".join("<tr>" + "".join(f"<td>{inline(c)}</td>" for c in r) + "</tr>" for r in body)
                       + "</tbody></table>")
            continue
        if ln.startswith(">"):
            buf = []
            while i < len(lines) and lines[i].startswith(">"):
                buf.append(lines[i][1:].strip()); i += 1
            out.append("<blockquote><p>" + inline(" ".join(buf)) + "</p></blockquote>"); continue
        if re.match(r"\s*([-*]|\d+\.)\s+", ln):              # list
            ordered = bool(re.match(r"\s*\d+\.", ln)); items = []
            while i < len(lines) and lines[i].strip():
                m = re.match(r"\s*([-*]|\d+\.)\s+(.*)", lines[i])
                if m:
                    items.append(m.group(2))
                else:
                    items[-1] += " " + lines[i].strip()
                i += 1
            tag = "ol" if ordered else "ul"
            out.append(f"<{tag}>" + "".join(f"<li>{inline(x)}</li>" for x in items) + f"</{tag}>"); continue
        buf = []
        while i < len(lines) and lines[i].strip() and not re.match(r"(#|\||>|<|\s*([-*]|\d+\.)\s)", lines[i]):
            buf.append(lines[i].strip()); i += 1
        out.append("<p>" + inline(" ".join(buf)) + "</p>")
    return "\n".join(out)


def main():
    src = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), "report.md"))
    base = os.path.splitext(src)[0]
    md = open(src, encoding="utf-8").read()
    title = re.search(r"^#\s+(.*)", md, re.M).group(1)
    doc = (f"<!doctype html><html><head><meta charset='utf-8'><title>{html.escape(title)}</title>"
           f"<style>{CSS}</style></head><body>{convert(md)}</body></html>")
    open(base + ".html", "w", encoding="utf-8").write(doc)
    browser = next((b for b in ("google-chrome", "chromium", "chromium-browser") if shutil.which(b)), None)
    if not browser:
        sys.exit(f"wrote {base}.html; no Chrome/Chromium found - open it in a browser and print to PDF")
    subprocess.run([browser, "--headless=new", "--disable-gpu", "--no-sandbox", "--no-pdf-header-footer",
                    f"--print-to-pdf={base}.pdf", "file://" + base + ".html"],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print(f"wrote {base}.html and {base}.pdf")


if __name__ == "__main__":
    main()
