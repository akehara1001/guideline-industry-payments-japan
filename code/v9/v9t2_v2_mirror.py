# -*- coding: utf-8 -*-
"""v9 Table 2 rows 1 and 2: rerun the frozen v2 audit (scripts/04_guideline_pilot.py audit, unchanged) on the five guidelines in a mirror,
with a chosen payment table and person key; then the frozen R8 scorer (scripts/07_score_vs_r8.py v2, unchanged except paths).
The model extraction is not redone: the saved extraction and company resolution (work/gl/<key>) are copied into the mirror.
Usage: python -X utf8 v9t2_v2_mirror.py <project> <gold folder> <pass>
  pass frozen_s3 : work/archive_stage3/{person_key,C_keyed}.pkl  (the tables the stage-2 v2 audit ran with, 2026-10-11 03:28)
  pass frozen_cur: work/{person_key,C_keyed}.pkl                (frozen tables after the stage-4 person-key change)
  pass fixed     : rerun_fixed_20261117/work/{person_key,C_keyed}.pkl
Mirror (names): rerun_fixed_20261117/work/v9_table2/v2_<pass>/{config, work/gl/<key>, work/gl_v3/<key>, out}
Counts: rerun_fixed_20261117/v9_table2/v2_<pass>/{summary.csv, compare_to_frozen.csv, score_v2_vs_r8.md, heldout_rows.csv}
Prints counts only.
"""
import sys, pathlib, shutil, io, contextlib, importlib.util, json, hashlib
import pandas as pd

P = pathlib.Path(sys.argv[1]).resolve(); GOLD = pathlib.Path(sys.argv[2]); PASS = sys.argv[3]
R = P / "rerun_fixed_20261117"
PKL = {"frozen_s3": P / "work" / "archive_stage3", "frozen_cur": P / "work", "fixed": R / "work"}[PASS]
# person-key module (name normalisation) the run used: the stage-3 one for the frozen v2 run and scorer (both ran before the stage-4
# change of 2026-10-11 18:00), the current one otherwise (the fixed person key was built with it)
PKMOD = P / "scripts" / "03_person_key.py"
if PASS == "frozen_s3":   # the stage-3 module reads its sibling ref_aim3_1_units_and_stoppers.py (unchanged since 2026-10-04): place both in work
    PKD = R / "work" / "v9_table2" / "pkmod_stage3"; PKD.mkdir(parents=True, exist_ok=True)
    shutil.copy2(P / "work" / "archive_stage3" / "03_person_key_stage3.py", PKD / "03_person_key.py")
    shutil.copy2(P / "scripts" / "ref_aim3_1_units_and_stoppers.py", PKD / "ref_aim3_1_units_and_stoppers.py")
    PKMOD = PKD / "03_person_key.py"
def load_with_pk(path, name):
    src = path.read_text(encoding="utf-8"); a = 'HERE/"03_person_key.py"'
    assert src.count(a) == 1, (path, src.count(a))
    return src.replace(a, "PKMOD_PATH")
M = R / "work" / "v9_table2" / f"v2_{PASS}"; OD = R / "v9_table2" / f"v2_{PASS}"
assert "rerun_fixed_20261117" in str(M)
if M.exists(): shutil.rmtree(M)
M.mkdir(parents=True); OD.mkdir(parents=True, exist_ok=True); (M / "out").mkdir()
KEYS = ["breast_2022", "pancreas_2022", "esophagus_2022", "liver_2021", "lung_2022"]; HELDOUT = KEYS[1:]
shutil.copytree(P / "config", M / "config")
for k in KEYS:
    shutil.copytree(P / "work" / "gl" / k, M / "work" / "gl" / k)
    if (P / "work" / "gl_v3" / k).exists(): shutil.copytree(P / "work" / "gl_v3" / k, M / "work" / "gl_v3" / k)

_real = pd.read_pickle; CACHE = {}
def read_pickle(path, *a, **k):
    name = pathlib.Path(path).name
    if name in ("person_key.pkl", "C_keyed.pkl"):
        if name not in CACHE: CACHE[name] = _real(PKL / name)
        return CACHE[name]
    return _real(path, *a, **k)
pd.read_pickle = read_pickle

import types
m04 = types.ModuleType("m04v2"); m04.__file__ = str(P / "scripts" / "04_guideline_pilot.py"); m04.PKMOD_PATH = PKMOD
exec(compile(load_with_pk(P / "scripts" / "04_guideline_pilot.py", "m04v2"), m04.__file__, "exec"), m04.__dict__)
rows = []
for k in KEYS:
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf): m04.cmd_audit(M, GOLD, k, M / "out" / f"audit_{k}.md")
    m = json.loads((M / "work" / "gl" / k / "metrics.json").read_text(encoding="utf-8"))
    rows.append(dict(key=k, units=m["units"]["total"], primary_agree=m["primary"]["agree"], primary_n=m["primary"]["n"],
                     secondary_agree=m["secondary"]["agree"], secondary_n=m["secondary"]["n"]))
S = pd.DataFrame(rows); S.to_csv(OD / "summary.csv", index=False, encoding="utf-8-sig")
h = S[S.key.isin(HELDOUT)]
print(S.to_string(index=False)); print(f"held-out four (Table 2 row 1): {int(h.primary_agree.sum())}/{int(h.primary_n.sum())}")

# compare with the frozen outputs in work/gl/<key>
cmp = []
for k in KEYS:
    A, B = P / "work" / "gl" / k, M / "work" / "gl" / k
    ma = json.loads((A / "metrics.json").read_text(encoding="utf-8")); mb = json.loads((B / "metrics.json").read_text(encoding="utf-8"))
    ma.pop("generated", None); mb.pop("generated", None)
    cmp.append(dict(key=k, file="metrics.json (without generated)", same=ma == mb))
    for sh in ["pharma_units", "secondary_common", "gold_units", "device_units"]:
        a = pd.read_excel(A / "audit_units.xlsx", sheet_name=sh); b = pd.read_excel(B / "audit_units.xlsx", sheet_name=sh)
        cmp.append(dict(key=k, file=f"audit_units.xlsx:{sh}", same=a.equals(b), rows_frozen=len(a), rows_mirror=len(b)))
    for f in ["member_links.csv", "company_map.csv"]:
        cmp.append(dict(key=k, file=f, same=hashlib.sha256((A / f).read_bytes()).hexdigest() == hashlib.sha256((B / f).read_bytes()).hexdigest()))
    ra = [l for l in (A / "report_section.md").read_text(encoding="utf-8").splitlines() if "生成日期" not in l]
    rb = [l for l in (B / "report_section.md").read_text(encoding="utf-8").splitlines() if "生成日期" not in l]
    cmp.append(dict(key=k, file="report_section.md (without date line)", same=ra == rb))
CP = pd.DataFrame(cmp); CP.to_csv(OD / "compare_to_frozen.csv", index=False, encoding="utf-8-sig")
print("compare with frozen work/gl:", int(CP.same.sum()), "/", len(CP), "same")

# Table 2 row 2: the frozen scorer, v2, on the mirror (paths only)
src_path = P / "scripts" / "07_score_vs_r8.py"; src = load_with_pk(src_path, "s07")
ns = dict(__name__="__v9t2__", __file__=str(src_path), PKMOD_PATH=PKMOD)
sys.argv = [str(src_path), str(M), str(GOLD / "revise3" / "R8_main_cells.csv"), "v2", str(OD / "score_v2_vs_r8.md")]
buf = io.StringIO()
with contextlib.redirect_stdout(buf): exec(compile(src, str(src_path), "exec"), ns)
a = [l for l in (P / "out" / "score_v2_vs_r8.md").read_text(encoding="utf-8").splitlines() if "生成日期" not in l]
b = [l for l in (OD / "score_v2_vs_r8.md").read_text(encoding="utf-8").splitlines() if "生成日期" not in l]
import difflib
diff = [l for l in difflib.unified_diff(a, b, lineterm="", n=0) if l[:1] in "+-" and not l.startswith(("+++", "---"))]
print("score_v2_vs_r8.md vs frozen out (without date line): differing lines", len(diff)); print("person-key module:", PKMOD.name)
tot = [l for l in b if l.startswith("| 合计 |")]
print("row-2 total line:", tot[:1])
