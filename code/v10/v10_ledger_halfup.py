# -*- coding: utf-8 -*-
"""v10, item 3: in a copy of the fixed ledger (work/v10/ledger_root_v10/out/RESULTS_LEDGER.csv), re-round every proportion written with its
counts ('p，95% CI [lo, hi]（k/n）', the format of scripts 104-124) half up: p = k/n exact, Wilson bounds from their float value. Text-level
replacement of those substrings only; every other byte of the file is kept. Logs each changed substring with its ledger row id.
Usage: python -X utf8 v10_ledger_halfup.py <project>"""
import sys, pathlib, re, math, csv, io
from fractions import Fraction as F
from decimal import Decimal, ROUND_HALF_UP, localcontext
P = pathlib.Path(sys.argv[1]).resolve(); R = P / "rerun_fixed_20261117"
LG = R / "work" / "v10" / "ledger_root_v10" / "out" / "RESULTS_LEDGER.csv"
assert "ledger_root_v10" in str(LG)
Z = 1.959963984540054
def hu(x, nd):
    with localcontext() as c:
        c.prec = 60
        d = Decimal(x.numerator) / Decimal(x.denominator) if isinstance(x, F) else Decimal(repr(float(x)))
        return str(d.quantize(Decimal(1).scaleb(-nd), rounding=ROUND_HALF_UP))
def wilson(k, n):
    p = k / n; d = 1 + Z * Z / n; c = (p + Z * Z / (2 * n)) / d; h = Z * math.sqrt(p * (1 - p) / n + Z * Z / (4 * n * n)) / d
    return max(0.0, c - h), min(1.0, c + h)
PAT = re.compile(r"(\d\.\d\d)，95% CI \[(\d\.\d\d), (\d\.\d\d)\]（(\d[\d,]*)/(\d[\d,]*)）")
raw = LG.read_bytes(); txt = raw.decode("utf-8-sig"); bom = raw.startswith(b"\xef\xbb\xbf")
log = []; seen = 0
def rep(m):
    global seen
    seen += 1
    k, n = int(m[4].replace(",", "")), int(m[5].replace(",", "")); lo, hi = wilson(k, n)
    new = f"{hu(F(k, n), 2)}，95% CI [{hu(lo, 2)}, {hu(hi, 2)}]（{m[4]}/{m[5]}）"
    if new != m[0]:
        line = txt.count("\n", 0, m.start()); log.append(dict(file_line=line + 1, old=m[0], new=new))
    return new
new = PAT.sub(rep, txt)
# row ids of the changed lines
rows = list(csv.reader(io.StringIO(new)))
hdr = rows[0]; idc = hdr.index("编号")
lines = new.split("\n")
for L in log:
    L["row_id"] = next((r[idc] for r in csv.reader(io.StringIO(lines[L["file_line"] - 1]))), "")
LG.write_bytes((b"\xef\xbb\xbf" if bom else b"") + new.encode("utf-8"))
out = R / "v10_audit" / "ledger_halfup_changes.csv"
with open(out, "w", newline="", encoding="utf-8-sig") as f:
    w = csv.DictWriter(f, fieldnames=["row_id", "file_line", "old", "new"]); w.writeheader(); w.writerows(log)
print("proportions with counts in the ledger:", seen, "| changed:", len(log)); [print(" ", L["row_id"], L["old"], "->", L["new"]) for L in log]
