# -*- coding: utf-8 -*-
"""Mechanical text copies of the public guideline files for pipeline v3.1 (form only, content unchanged).
Same as 06_doc_to_text_v3.py except the config (config/guidelines_v3_1.csv) and the output folder (work/pilot_src/v3_1/<key>).
Usage: python 06_doc_to_text_v3_1.py "<project>" <guideline key>
Reads  config/guidelines_v3_1.csv (coi_files, committee_files, note_files) and data_raw/guidelines/<key>/<file>.
Writes work/pilot_src/v3_1/<key>/<file stem>.txt
Differences from 06_doc_to_text.py (v2, unchanged): HTML table captions are written as "[caption] ..." before the rows;
ordered-list items carry their list number ("3. ..."), honouring <ol start> and <li value>; list items keep their own line.
  PDF : one block per page, each starting with "=== <filename> page N ===" (pdfplumber text; "[no text layer]" if empty).
  HTML: visible text of the main content, one numbered line per block ("L0001: ..."); headings as "[h2] ...";
        tables as "[table N]" followed by "[caption] ..." and one line per row, cells joined by " | ".
The script prints file names, page counts and line counts only.
"""
import sys, pathlib, re, csv
import pdfplumber
from bs4 import BeautifulSoup, NavigableString

P = pathlib.Path(sys.argv[1]); KEY = sys.argv[2]
RAW = P/"data_raw"/"guidelines"/KEY; OUT = P/"work"/"pilot_src"/"v3_1"/KEY; OUT.mkdir(parents=True, exist_ok=True)
SKIP = {"script", "style", "noscript", "nav", "header", "footer", "form", "iframe", "svg", "button"}
HEAD = {"h1", "h2", "h3", "h4", "h5", "h6"}
BLOCK = {"p", "dt", "dd", "blockquote", "pre", "address", "figcaption"}


def ws(t):
    return re.sub(r"\s+", " ", t or "").strip()


def pdf_text(path):
    out = []
    with pdfplumber.open(path) as pdf:
        for i, page in enumerate(pdf.pages, start=1):
            t = page.extract_text() or ""
            out.append(f"=== {path.name} page {i} ===")
            out.append(t if t.strip() else "[no text layer]")
    return "\n".join(out) + "\n", len(out) // 2


def html_text(path):
    soup = BeautifulSoup(path.read_bytes(), "lxml")
    root = soup.select_one("div.entry-body") or soup.find("main") or soup.find("article") or soup.body or soup
    lines, ntab = [], [0]

    def emit(t, prefix=""):
        t = ws(t)
        if t: lines.append(prefix + t)

    def walk(node):
        for ch in node.children:
            if isinstance(ch, NavigableString):
                if ch.parent is not None and ch.parent.name not in SKIP: emit(str(ch))
                continue
            if ch.name in SKIP: continue
            if ch.name == "table":
                ntab[0] += 1; lines.append(f"[table {ntab[0]}]")
                cap = ch.find("caption")
                if cap is not None and ws(cap.get_text(" ", strip=True)): lines.append("[caption] " + ws(cap.get_text(" ", strip=True)))
                for tr in ch.find_all("tr"):
                    cells = [ws(td.get_text(" ", strip=True)) for td in tr.find_all(["th", "td"], recursive=False)]
                    if any(cells): lines.append(" | ".join(cells))
            elif ch.name in HEAD:
                t = ws(ch.get_text(" ", strip=True))
                if t: lines.append(f"[{ch.name}] {t}")
            elif ch.name == "ol":
                try: n = int(ch.get("start", 1))
                except ValueError: n = 1
                for li in ch.find_all("li", recursive=False):
                    try: n = int(li.get("value", n))
                    except ValueError: pass
                    if li.find(["table", "ol", "ul"] + list(HEAD)):
                        emit(f"{n}.")
                        walk(li)
                    else:
                        emit(li.get_text(" ", strip=True), prefix=f"{n}. ")
                    n += 1
            elif ch.name == "ul":
                for li in ch.find_all("li", recursive=False):
                    if li.find(["table", "ol", "ul"] + list(HEAD)): walk(li)
                    else: emit(li.get_text(" ", strip=True))
            elif ch.name in BLOCK and not ch.find(["table", "ol", "ul"] + list(HEAD)):
                emit(ch.get_text(" ", strip=True))
            elif ch.name == "br":
                continue
            else:
                walk(ch)
    walk(root)
    return "\n".join(f"L{i:04d}: {t}" for i, t in enumerate(lines, start=1)) + "\n", len(lines)


def main():
    cfg = {r["key"]: r for r in csv.DictReader(open(P/"config"/"guidelines_v3_1.csv", encoding="utf-8-sig"))}[KEY]
    files = [f for col in ("coi_files", "committee_files", "note_files") for f in cfg[col].split(";") if f]
    for fn in files:
        f = RAW/fn
        if f.suffix.lower() == ".pdf": txt, n = pdf_text(f); unit = "pages"
        elif f.suffix.lower() in (".html", ".htm"): txt, n = html_text(f); unit = "lines"
        else: print(f"skip (not pdf/html): {f.name}"); continue
        (OUT/(f.stem + ".txt")).write_text(txt, encoding="utf-8")
        print(f"{f.name}: {n} {unit}, {len(txt)} chars -> v3_1/{KEY}/{f.stem}.txt")


if __name__ == "__main__":
    main()
