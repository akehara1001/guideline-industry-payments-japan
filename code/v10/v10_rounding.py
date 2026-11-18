# -*- coding: utf-8 -*-
"""v10, item 3: re-apply round-half-up to every number of the tables and figures (counts and aggregates only, no names).
The scripts that built the tables format with f"{x:.2f}" on floats, which rounds an exact tie to even (0.625 -> 0.62) and a tie that binary
floating point stores just below (0.975 -> 0.97) down. Here every displayed value is recomputed from its exact source and rounded half up:
  A. proportions with their counts on display (cell 'p [lo, hi] (k/n)'; row cells 'k/n' + 'p [lo, hi]'; Table 2 and S10 Table columns;
     the forest plots' text columns): p = k/n exactly (Fraction); Wilson bounds as in the scripts (z = 1.959963984540054), rounded half up
     from their float value (Decimal of repr).
  B. the two-channel aggregates without counts on display (amount shares, medians and quartiles over guidelines, pooled shares, ratio of
     shares, amounts in 10,000 JPY): recomputed exactly from the integer-yen amounts and counts in the fixed run's pickles
     (work/stage20/two_channels.pkl of script 120, work/twochannel_comparison/twochannel_comparison.pkl), with numpy's linear percentile done
     in Fractions; every value that is an exact tie at its displayed precision is listed (only a tie can round differently).
  C. every other decimal number in the table cells, listed with its table so that nothing is left unchecked.
Writes rerun_fixed_20261117/v10_audit/rounding_changes.csv (A: every displayed value that changes), rounding_ties_B.csv, rounding_other.csv,
rounding_summary.json. Usage: python -X utf8 v10_rounding.py <project>"""
import sys, pathlib, re, json, math
from fractions import Fraction as F
from decimal import Decimal, ROUND_HALF_UP
import pandas as pd, numpy as np, docx
from docx.oxml.ns import qn

P = pathlib.Path(sys.argv[1]).resolve(); R = P / "rerun_fixed_20261117"; OUT = R / "v10_audit"; OUT.mkdir(exist_ok=True)
MS = R / "work" / "v10" / "accepted" / "manuscript_v9_AO_accepted.docx"; SUP = P / "paper" / "v9" / "supplementary_v9.docx"
PAPER = R / "work" / "stage2" / "mirror_fixed" / "ledger_root" / "out" / "paper"
LR = R / "work" / "stage2" / "mirror_fixed" / "ledger_root" / "work"
Z = 1.959963984540054

def hu(x, nd):
    """half up: x a Fraction (exact) or a float (from its shortest repr)."""
    d = Decimal(x.numerator) / Decimal(x.denominator) if isinstance(x, F) else Decimal(repr(float(x)))
    if isinstance(x, F):  # exact decimal expansion when it terminates, else enough digits
        from decimal import localcontext
        with localcontext() as c:
            c.prec = 60; d = Decimal(x.numerator) / Decimal(x.denominator)
    return str(d.quantize(Decimal(1).scaleb(-nd), rounding=ROUND_HALF_UP))
def wilson(k, n):
    p = k / n; d = 1 + Z * Z / n; c = (p + Z * Z / (2 * n)) / d; h = Z * math.sqrt(p * (1 - p) / n + Z * Z / (4 * n * n)) / d
    return max(0.0, c - h), min(1.0, c + h)
num = lambda s: int(s.replace(",", ""))
def expect(k, n):
    lo, hi = wilson(k, n); return hu(F(k, n), 2), hu(lo, 2), hu(hi, 2)

# ---------------------------------------------------------------- cells
def cells(path, doc):
    d = docx.Document(path); out = []; ti = -1; title = ""
    for el in d.element.body.iterchildren():
        if el.tag == qn("w:p"):
            t = "".join(x.text or "" for x in el.iter(qn("w:t"))).strip()
            if re.match(r"^(S\d+ Table|Table \d+)\. ", t): title = t.split(".")[0]
        elif el.tag == qn("w:tbl"):
            ti += 1
            for ri, tr in enumerate(el.iter(qn("w:tr"))):
                row = [" ".join("".join(x.text or "" for x in p.iter(qn("w:t"))) for p in tc.iter(qn("w:p"))) for tc in tr.iter(qn("w:tc"))]
                for ci, s in enumerate(row): out.append(dict(doc=doc, table=title, tidx=ti, row=ri, col=ci, text=s, rowcells=row))
    return out
C = cells(MS, "manuscript") + cells(SUP, "supplementary")
# figures: the text the forest plots and the flow chart draw (113's csv of the fixed run = the v9 figures)
FIGC = []
for nm, lab in (("figure2_forest_main", "Fig 2"), ("figureS1_forest_inferred", "S1 Fig"), ("figure1_flow", "Fig 1")):
    f = pd.read_csv(PAPER / f"{nm}.csv", dtype=str, keep_default_na=False, encoding="utf-8-sig")
    for r in f.itertuples(): FIGC.append(dict(doc="figure", table=lab, rkey=r.rkey, ckey=r.ckey, text=r.text))

PCI = re.compile(r"(\d\.\d\d) \[(\d\.\d\d), (\d\.\d\d)\] \((\d[\d,]*)/(\d[\d,]*)\)")
changes = []; covered = set(); checkedA = 0
def check(where, shown, k, n):
    global checkedA
    checkedA += 1
    e = expect(k, n)
    for lab, s, x in zip(("proportion", "CI lower", "CI upper"), shown, e):
        if s != x: changes.append(dict(**where, part=lab, counts=f"{k:,}/{n:,}", shown=s, half_up=x))
for c in C:
    w = dict(doc=c["doc"], table=c["table"], row=c["row"], col=c["col"])
    for m in PCI.finditer(c["text"]):
        check(w, m.groups()[:3], num(m[4]), num(m[5])); covered.add((c["doc"], c["tidx"], c["row"], c["col"]))
    # row cells: 'k/n' then 'p [lo, hi]'
    if re.fullmatch(r"\d[\d,]*/\d[\d,]*", c["text"].strip()) and c["col"] + 1 < len(c["rowcells"]):
        m2 = re.fullmatch(r"(\d\.\d\d) \[(\d\.\d\d), (\d\.\d\d)\]", c["rowcells"][c["col"] + 1].strip())
        if m2:
            k, n = map(num, c["text"].split("/"))
            check(dict(doc=c["doc"], table=c["table"], row=c["row"], col=c["col"] + 1), m2.groups(), k, n)
            covered.add((c["doc"], c["tidx"], c["row"], c["col"] + 1)); covered.add((c["doc"], c["tidx"], c["row"], c["col"]))
# Table 2 (units compared, agreeing, agreement) and S10 Table (evaluable, undeclared, proportion)
for c in C:
    m = re.fullmatch(r"(\d\.\d\d) \[(\d\.\d\d), (\d\.\d\d)\]", c["text"].strip())
    if not m: continue
    rc = c["rowcells"]
    if c["table"] == "Table 2" and c["col"] == 3: n, k = num(rc[1]), num(rc[2])
    elif c["table"] == "S10 Table" and c["col"] == 4: n, k = num(rc[2]), num(rc[3])
    else: continue
    check(dict(doc=c["doc"], table=c["table"], row=c["row"], col=c["col"]), m.groups(), k, n); covered.add((c["doc"], c["tidx"], c["row"], c["col"]))
# Table 4 and S5 Table: proportion rows take their counts from the two rows above in the same column
for c in C:
    if c["table"] not in ("Table 4", "S5 Table") or c["col"] < 2: continue
    m = re.fullmatch(r"(\d\.\d\d) \[(\d\.\d\d), (\d\.\d\d)\]", c["text"].strip())
    if not m: continue
    lab = c["rowcells"][1]
    same = {(x["row"]): x for x in C if x["doc"] == c["doc"] and x["tidx"] == c["tidx"] and x["col"] == c["col"]}
    labs = {x["row"]: x["rowcells"][1] for x in C if x["doc"] == c["doc"] and x["tidx"] == c["tidx"] and x["col"] == 1}
    want = {"Proportion undeclared [95% CI]": ("Undeclared units, after deduplication", "Evaluable units, after deduplication"),
            "Proportion of authors [95% CI]": ("Authors with at least one undeclared unit", "Authors with at least one evaluable unit")}[lab]
    assert labs[c["row"] - 1].startswith(want[0]) and labs[c["row"] - 2].startswith(want[1]), (c["table"], c["row"])
    k, n = num(same[c["row"] - 1]["text"]), num(same[c["row"] - 2]["text"])
    check(dict(doc=c["doc"], table=c["table"], row=c["row"], col=c["col"]), m.groups(), k, n); covered.add((c["doc"], c["tidx"], c["row"], c["col"]))
# forest plots
fg = pd.DataFrame([x for x in FIGC if x["table"] in ("Fig 2", "S1 Fig")])
for (tab, rk), g in fg.groupby(["table", "rkey"]):
    t = dict(zip(g.ckey, g.text))
    for tag in ("ph", "dv"):
        if t.get(f"{tag}_ci", "—") == "—": continue
        m = re.fullmatch(r"(\d\.\d\d) \[(\d\.\d\d), (\d\.\d\d)\]", t[f"{tag}_ci"])
        check(dict(doc="figure", table=tab, row=rk, col=f"{tag}_ci"), m.groups(), num(t[f"{tag}_k"]), num(t[f"{tag}_n"]))
cA = pd.DataFrame(changes); cA.to_csv(OUT / "rounding_changes.csv", index=False, encoding="utf-8-sig")

# ---------------------------------------------------------------- B. two-channel aggregates: exact ties
TC = pd.read_pickle(LR / "stage20" / "two_channels.pkl"); CMP = pd.read_pickle(LR / "twochannel_comparison" / "twochannel_comparison.pkl")
def fr(x): return F(int(round(float(x)))) if float(x) == round(float(x)) else F(x)
def pct(vals, q):
    v = sorted(vals); h = (len(v) - 1) * F(q, 100); lo = math.floor(h); hi = math.ceil(h)
    return v[lo] + (h - lo) * (v[hi] - v[lo])
def tie(x, nd):
    s = x * 10 ** nd; return abs((s - math.floor(s)) - F(1, 2)) < F(1, 10 ** 9)   # exact ties and near ties (float noise could flip these)
ties = []; checkedB = 0; repro = [0, 0]
def look(what, x, nd):
    global checkedB
    checkedB += 1
    if tie(x, nd): ties.append(dict(item=what, exact=str(x), exact_tie=(x * 10 ** nd - math.floor(x * 10 ** nd)) == F(1, 2), shown_old=f"{float(x):.{nd}f}", half_up=hu(x, nd)))
old_fmt = lambda m: f"{float(m[1]):.2f}（四分位距 {float(m[0]):.2f}–{float(m[2]):.2f}，{m[3]} 部）"
for var, res in TC["RES"].items():
    groups = {f"society {s}": TC["SOCK"][s] for s in TC["SOCK"]} | {f"set {s}": TC["SETS"][s] for s in TC["SETS"]}
    for gname, keys in groups.items():
        for ind in ("all", "pharma", "device"):
            rows = [res[k][ind] for k in keys if k in res]
            sh = [fr(r["fromA"]) / fr(r["total"]) for r in rows if float(r["total"]) > 0]
            aba = [F(int(r["AB"]), int(r["A"])) for r in rows if int(r["A"]) > 0]
            abb = [F(int(r["AB"]), int(r["B"])) for r in rows if int(r["B"]) > 0]
            for lab, v in (("share from A", sh), ("AB/A", aba), ("AB/B", abb)):
                if not v: continue
                m = [pct(v, q) for q in (25, 50, 75)]
                for qn_, x in zip(("Q1", "median", "Q3"), m): look(f"{var} | {gname} | {ind} | {lab} {qn_}", x, 2)
                # reproduce the stored strings (society rows of the main variant and the pooled sets)
                stored = None
                if var == "main" and gname.startswith("society ") and gname[8:] in TC["SOCP"]:
                    stored = TC["SOCP"][gname[8:]][ind].get({"share from A": "med_share", "AB/A": "med_ab_a", "AB/B": "med_ab_b"}[lab])
                if gname.startswith("set ") and gname[4:] in TC["POOL"][var]:
                    stored = TC["POOL"][var][gname[4:]][ind].get({"share from A": "med_share", "AB/A": "med_ab_a", "AB/B": "med_ab_b"}[lab])
                if stored and "—" not in stored:
                    repro[1] += 1; repro[0] += stored == old_fmt(m + [len(v)])
            tot = sum(fr(r["total"]) for r in rows); fa = sum(fr(r["fromA"]) for r in rows)
            look(f"{var} | {gname} | {ind} | payments to societies (10,000 JPY), sum over guidelines", tot / 10000, 0)
            if tot: look(f"{var} | {gname} | {ind} | pooled share from A", fa / tot, 2)
# the stored society and pooled totals themselves (the table prints these)
for var in TC["POOL"]:
    for s, v in TC["POOL"][var].items():
        for ind, d in v.items():
            look(f"POOL {var} | {s} | {ind} | total (10,000 JPY)", fr(d["total"]) / 10000, 0); look(f"POOL {var} | {s} | {ind} | fromA (10,000 JPY)", fr(d["fromA"]) / 10000, 0)
            if float(d["total"]): look(f"POOL {var} | {s} | {ind} | pooled share", fr(d["fromA"]) / fr(d["total"]), 2)
for s, v in TC["SOCP"].items():
    for ind, d in v.items():
        look(f"SOCP {s} | {ind} | total (10,000 JPY)", fr(d["total"]) / 10000, 0); look(f"SOCP {s} | {ind} | fromA (10,000 JPY)", fr(d["fromA"]) / 10000, 0)
# Table 3 groups (script twochannel_comparison.py): per-guideline group shares, pooled, ratio A vs C, for both universes (full n/s, d = nd/sd)
for sname, keys in CMP["SETS"].items():
    per = [CMP["PER"][k] for k in keys]
    for g in ("A", "B", "C"):
        sh = [fr(p["amt"][g]) / fr(p["total"]) for p in per if float(p["total"]) > 0]
        m = [pct(sh, q) for q in (25, 50, 75)]
        for qn_, x in zip(("Q1", "median", "Q3"), m): look(f"Table 3 | {sname} | group {g} share {qn_}", x, 2)
        stored = CMP["RES"][sname]["share"][g]
        repro[1] += 3; repro[0] += sum(abs(float(a) - float(b)) < 1e-12 for a, b in zip((m[1], m[0], m[2]), stored[:3]))   # stored = (median, Q1, Q3, n)
        for univ, nk, sk in (("full", "n", "s"), ("d", "nd", "sd")):
            n_ = sum(p[nk][g] for p in per); s_ = sum(p[sk][g] for p in per)
            look(f"Table 3 | {sname} | {univ} | group {g} proportion", F(s_, n_), 2)
    for univ, nk, sk in (("full", "n", "s"), ("d", "nd", "sd")):
        nA = sum(p[nk]["A"] for p in per); sA = sum(p[sk]["A"] for p in per); nC = sum(p[nk]["C"] for p in per); sC = sum(p[sk]["C"] for p in per)
        look(f"Table 3 | {sname} | {univ} | ratio A vs C", F(sA, nA) / F(sC, nC), 2)
    tot = sum(fr(p["total"]) for p in per); look(f"Table 3 | {sname} | pooled share A", sum(fr(p["amt"]["A"]) for p in per) / tot, 2)
pd.DataFrame(ties).to_csv(OUT / "rounding_ties_B.csv", index=False, encoding="utf-8-sig")

# ---------------------------------------------------------------- C. other decimal numbers in the cells
DEC = re.compile(r"(?<![\d.])\d+\.\d+(?![\d.])")
other = []
for c in C:
    if (c["doc"], c["tidx"], c["row"], c["col"]) in covered: continue
    for m in DEC.finditer(c["text"]): other.append(dict(doc=c["doc"], table=c["table"], row=c["row"], col=c["col"], value=m[0], header=c["rowcells"][0][:50]))
oth = pd.DataFrame(other); oth.to_csv(OUT / "rounding_other.csv", index=False, encoding="utf-8-sig")
summ = dict(A_checked=checkedA, A_changes=len(cA), B_checked=checkedB, B_ties=len(ties), B_reproduced_stored=f"{repro[0]}/{repro[1]}",
            C_other_decimals=len(oth), C_by_table=oth.groupby(["doc", "table"]).size().to_dict() if len(oth) else {})
summ["C_by_table"] = {f"{a}|{b}": int(v) for (a, b), v in summ["C_by_table"].items()}
(OUT / "rounding_summary.json").write_text(json.dumps(summ, ensure_ascii=False, indent=1), encoding="utf-8")
print(json.dumps(summ, ensure_ascii=False, indent=1))
if len(cA): print(cA.to_string())
if ties: print(pd.DataFrame(ties).to_string())
