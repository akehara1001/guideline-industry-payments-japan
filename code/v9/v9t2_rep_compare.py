# -*- coding: utf-8 -*-
"""v9 Table 2 rows 4-6: the frozen repeat-extraction comparisons (scripts/39, 65, 78, unchanged except paths) on audits rerun with a
chosen payment table and person key. The model extractions are not redone.
  run 1: the stage-2 audit mirror (work/stage2/mirror_frozen or mirror_fixed; stage 9 and 12 keys in work/gl_v3_1, stage 13 in census3_root)
  run 2: work/stage2/v9t2_rep_<pass>/<census_rep_root|census2_rep_root|census3_rep_root>/work/gl_v3_1 (s2_audit_mirror.py with v9_table2/rep_dirs.csv)
Usage: python -X utf8 v9t2_rep_compare.py <project> <pass: frozen|fixed>
Writes rerun_fixed_20261117/v9_table2/rep_<pass>/{census_repeat.md, census2_repeat.md, census3_repeat.md, rows.csv} (aggregates) and
       rerun_fixed_20261117/work/v9_table2/rep_<pass>/*.pkl. For the frozen pass, compares each md with out/ (date line excluded).
"""
import sys, pathlib, io, contextlib, difflib, re
import pandas as pd
P = pathlib.Path(sys.argv[1]).resolve(); PASS = sys.argv[2]; R = P / "rerun_fixed_20261117"
MIR = R / "work" / "stage2" / ("mirror_frozen" if PASS == "frozen" else "mirror_fixed")
REP = R / "work" / "stage2" / f"v9t2_rep_{PASS}"
OD = R / "v9_table2" / f"rep_{PASS}"; OW = R / "work" / "v9_table2" / f"rep_{PASS}"; OD.mkdir(parents=True, exist_ok=True); OW.mkdir(parents=True, exist_ok=True)
JOBS = [("39_census_rep_compare.py", 'R1 = P/"work"/"gl_v3_1"; R2 = P/"census_rep_root"/"work"/"gl_v3_1"', MIR / "work" / "gl_v3_1", REP / "census_rep_root" / "work" / "gl_v3_1",
         "census_repeat.md", 'P/"work"/"census"/"repeat_numbers.pkl"'),
        ("65_census2_rep_compare.py", 'R1 = P/"work"/"gl_v3_1"; R2 = P/"census2_rep_root"/"work"/"gl_v3_1"', MIR / "work" / "gl_v3_1", REP / "census2_rep_root" / "work" / "gl_v3_1",
         "census2_repeat.md", 'P/"work"/"census2"/"repeat_numbers.pkl"'),
        ("78_census3_rep_compare.py", 'R1 = P/"census3_root"/"work"/"gl_v3_1"; R2 = P/"census3_rep_root"/"work"/"gl_v3_1"', MIR / "census3_root" / "work" / "gl_v3_1", REP / "census3_rep_root" / "work" / "gl_v3_1",
         "census3_repeat.md", 'P/"work"/"census3"/"repeat_numbers.pkl"')]
rows = []
for script, r12, R1, R2, md, pk in JOBS:
    sp = P / "scripts" / script; src = sp.read_text(encoding="utf-8")
    for a, b in [(r12, "R1 = R1_PATH; R2 = R2_PATH"), (f'(P/"out"/"{md}").write_text(', '(OD_PATH/MD_NAME).write_text('), (pk, 'OW_PATH/("repeat_numbers_" + MD_NAME + ".pkl")')]:
        assert src.count(a) == 1, (script, a, src.count(a)); src = src.replace(a, b)
    assert R1.exists() and R2.exists(), (R1, R2)
    ns = dict(__name__="__v9t2__", __file__=str(sp), R1_PATH=R1, R2_PATH=R2, OD_PATH=OD, OW_PATH=OW, MD_NAME=md)
    sys.argv = [str(sp), str(P)]
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf): exec(compile(src, str(sp), "exec"), ns)
    new = (OD / md).read_text(encoding="utf-8").splitlines()
    sec = new[new.index(next(l for l in new if "审计：三分类判定" in l)):]
    tot = next(l for l in sec if l.startswith("| 合计 |")); c = [x.strip() for x in tot.strip("|").split("|")]
    n, k = int(c[2].replace(",", "")), int(c[3].replace(",", ""))
    d = None
    if PASS == "frozen":
        old = [l for l in (P / "out" / md).read_text(encoding="utf-8").splitlines() if "生成日期" not in l]
        nw = [l for l in new if "生成日期" not in l]
        d = [l for l in difflib.unified_diff(old, nw, lineterm="", n=0) if l[:1] in "+-" and not l.startswith(("+++", "---"))]
    rows.append(dict(md=md, units_both=n, judge_same=k, differing_lines_vs_frozen_out=(len(d) if d is not None else "")))
    print(md, "| three-class:", f"{k}/{n}", "| differing lines vs frozen out:", len(d) if d is not None else "-")
    if d: print("   ", [x[:160] for x in d[:6]])
pd.DataFrame(rows).to_csv(OD / "rows.csv", index=False, encoding="utf-8-sig")
