# -*- coding: utf-8 -*-
"""v9 Table 2: old (frozen, reproduced) and new (fixed payment table and person key) for all six rows, Wilson 95% CI as in 111.
Usage: python -X utf8 v9t2_summary.py <project>
Writes rerun_fixed_20261117/v9_table2/table2_old_new.csv and .json (counts only)."""
import sys, pathlib, math, json, re
import pandas as pd
P = pathlib.Path(sys.argv[1]).resolve(); R = P / "rerun_fixed_20261117"; T = R / "v9_table2"
def wilson(k, n, z=1.959963984540054):   # same as scripts/111_validation_summary.py
    p = k / n; d = 1 + z * z / n; c = (p + z * z / (2 * n)) / d; h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return p, max(0.0, c - h), min(1.0, c + h)
fmt = lambda k, n: (lambda p, lo, hi: f"{p:.2f} [{lo:.2f}, {hi:.2f}]")(*wilson(k, n))
def held(ps):
    s = pd.read_csv(T / f"v2_{ps}" / "summary.csv"); h = s[s.key != "breast_2022"]; return int(h.primary_agree.sum()), int(h.primary_n.sum())
def r8(ps):
    l = next(x for x in (T / f"v2_{ps}" / "score_v2_vs_r8.md").read_text(encoding="utf-8").splitlines() if x.startswith("| 合计 |"))
    m = re.search(r"（(\d+)/(\d+)）", l); return int(m.group(1)), int(m.group(2))
def dev(ps):
    l = next(x for x in (R / "v9_stage0" / ps / "score_dev_final.md").read_text(encoding="utf-8").splitlines() if x.startswith("| 合计 |"))
    m = re.findall(r"（(\d+)/(\d+)）", l)[-1]; return int(m[0]), int(m[1])
def rep(ps, md):
    r = pd.read_csv(T / f"rep_{ps}" / "rows.csv").set_index("md"); return int(r.loc[md, "judge_same"]), int(r.loc[md, "units_both"])
V8 = [(254, 262), (273, 280), (339, 346), (400, 400), (710, 712), (207, 207)]   # Table 2 of v8 (out/paper/table2_validation.csv)
rows = []
for i, (lab, fo, fx) in enumerate([
        ("Earlier frozen version vs manual data entry, held-out guidelines", held("frozen_s3"), held("fixed")),
        ("Earlier frozen version vs a published final adjudication", r8("frozen_s3"), r8("fixed")),
        ("Final frozen version vs the corrected adjudication, development guidelines", dev("frozen"), dev("fixed")),
        ("Final frozen version, repeated extraction, first sample", rep("frozen", "census_repeat.md"), rep("fixed", "census_repeat.md")),
        ("Final frozen version, repeated extraction, second sample", rep("frozen", "census2_repeat.md"), rep("fixed", "census2_repeat.md")),
        ("Final frozen version, repeated extraction, third sample", rep("frozen", "census3_repeat.md"), rep("fixed", "census3_repeat.md"))]):
    rows.append(dict(row=i + 1, comparison=lab, v8=f"{V8[i][0]}/{V8[i][1]}", reproduced=f"{fo[0]}/{fo[1]}", reproduced_ok=fo == V8[i],
                     old_agreement=fmt(*V8[i]), new=f"{fx[0]}/{fx[1]}", new_units=fx[1], new_agree=fx[0], new_agreement=fmt(*fx),
                     two_decimals_same=fmt(*V8[i]).split(" ")[0] == fmt(*fx).split(" ")[0], ci_same=fmt(*V8[i]) == fmt(*fx)))
D = pd.DataFrame(rows); D.to_csv(T / "table2_old_new.csv", index=False, encoding="utf-8-sig")
(T / "table2_old_new.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
pd.set_option("display.width", 250); print(D.drop(columns=["comparison"]).to_string(index=False))
print("all reproduced:", bool(D.reproduced_ok.all()), "| agreement (2 decimals) unchanged in every row:", bool(D.two_decimals_same.all()))
