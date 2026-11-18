# -*- coding: utf-8 -*-
"""Stage 4: fiscal year vs calendar year. Undeclared share among the evaluable units of the main analysis set, after the paper's author
deduplication, for (1) all units, (2) units whose payment is at least twice the guideline's threshold for that item, (3) the same, without the
last year of the disclosure period.
Usage: python s4_fiscal_year.py <project_dir> <units_pkl> <label>
  units_pkl  work/stage18/units_rule2.pkl (frozen) or rerun_fixed_20261117/stage2/mirror_fixed/work/stage18/units_rule2.pkl (fixed)
Rules (as the paper; nothing changed):
  evaluable = judge2 (after rules 1 and 2) is 已申报 or 未申报; main analysis set = config/guidelines_analysis_sets.csv analysis_set 主分析集;
  industry = the company node's primary industry (prim); the external evaluators of the Japanese Circulation Society are kept (official count).
  Author deduplication (115 dedup): units with a person key, grouped by person x company node x year; a group is undeclared when every unit
  in it is 未申报; the denominator is the number of groups.
  Threshold = the guideline's own threshold for the unit's item (lecture_threshold_man / manuscript_threshold_man x 10,000 JPY, rule 2).
  Last year = the guideline's last audit year (kg/nodes/guideline.parquet audit_year_last), dropped only when the disclosure period ends in 2023 or
  earlier; a period that runs to 2024 or later has no year to drop (payment data end at 2023). This is the rule that reproduces the reference
  numbers given for stage 4 (before deduplication, frozen units: pharma 149/1,225, device 20/99).
  95% CI: Wilson.
Writes rerun_fixed_20261117/stage4/fiscal_year_<label>.csv and .md. Prints counts only.
"""
import sys, pathlib, re, math
import pandas as pd

P = pathlib.Path(sys.argv[1]).resolve(); UP = pathlib.Path(sys.argv[2]); LAB = sys.argv[3]
OUT = P / "rerun_fixed_20261117" / "stage4"; OUT.mkdir(parents=True, exist_ok=True)
U = pd.read_pickle(UP)
AS = pd.read_csv(P / "config" / "guidelines_analysis_sets.csv", dtype=str, keep_default_na=False, encoding="utf-8-sig").set_index("key")
G = pd.read_parquet(P / "kg" / "nodes" / "guideline.parquet").set_index("guideline_id")
U["set"] = U.key.map(AS.analysis_set)
TH = {"講演料": "lecture_threshold_man", "原稿料": "manuscript_threshold_man"}
U["thr"] = [float(AS.loc[k, TH[i]]) * 10000 for k, i in zip(U.key, U["item"])]
pend = {k: int(re.match(r"(\d{4})", str(G.loc[k, "disclosure_period_end"])).group(1)) for k in set(U.key)}
U["pend"] = U.key.map(pend); U["alast"] = U.key.map(G.audit_year_last).astype(int)
U["last_dropped"] = (U.year == U.alast) & (U.pend <= 2023)
X = U[(U.set == "主分析集") & U.judge2.isin(["已申报", "未申报"])]

def wilson(k, n, z=1.959963984540054):
    p = k / n; d = 1 + z * z / n; c = (p + z * z / (2 * n)) / d; h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return p, max(0.0, c - h), min(1.0, c + h)
def dedup(x):
    x = x[x.person != ""]
    g = x.groupby(["person", "node", "year"]).judge2.agg(lambda s: "未申报" if set(s) == {"未申报"} else ("已申报" if set(s) == {"已申报"} else "各部不一"))
    return int((g == "未申报").sum()), len(g)
rows = []
for ind, il in (("pharma", "Pharmaceutical"), ("device", "Medical device")):
    x = X[X.prim == ind]
    for cut, cl, s in (("all", "All evaluable units", x), ("2x", "Payment at least twice the threshold", x[x.amt >= 2 * x.thr]),
                       ("2x_nolast", "At least twice the threshold, last year of the period excluded", x[(x.amt >= 2 * x.thr) & ~x.last_dropped])):
        k, n = dedup(s); p, lo, hi = wilson(k, n)
        rows.append(dict(industry=il, subset=cl, cut=cut, units=n, undeclared=k, share=f"{p:.2f}", ci=f"[{lo:.2f}, {hi:.2f}]",
                         units_before_dedup=len(s), undeclared_before_dedup=int((s.judge2 == "未申报").sum())))
D = pd.DataFrame(rows); D.to_csv(OUT / f"fiscal_year_{LAB}.csv", index=False, encoding="utf-8-sig")
print(D.to_string(index=False))
L = [f"| Industry | Units | Evaluable units† | Undeclared | Proportion undeclared [95% CI] |", "|---|---|---:|---:|---|"]
for r in D.itertuples():
    L.append(f"| {r.industry} | {r.subset} | {r.units:,} | {r.undeclared:,} | {r.share} {r.ci} |")
L += ["", "† After deduplication by author × company × year (the paper's rule). Main analysis set (48 guidelines); rules 1 and 2 applied. "
      "Threshold = the guideline's own declaration threshold for the item. The last year of the disclosure period is dropped only for guidelines "
      "whose period ends in 2023 or earlier. 95% CI: Wilson."]
(OUT / f"fiscal_year_{LAB}.md").write_text("\n".join(L) + "\n", encoding="utf-8")
print("guidelines with a dropped last year:", X[X.last_dropped].key.nunique(), "of", X.key.nunique(),
      "| period end differs from last audit year:", sorted({(k, pend[k], int(G.loc[k, 'audit_year_last'])) for k in X.key.unique() if pend[k] != int(G.loc[k, 'audit_year_last']) and pend[k] <= 2023}))
