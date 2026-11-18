# -*- coding: utf-8 -*-
"""v9 stage 0, check 1: Table 2 row 3 (v3.1 on the five development guidelines vs the corrected adjudication).
Runs the frozen scorer scripts/12_reference_corrected.py unchanged in logic, by text substitution of its paths only:
  person_key.pkl / C_keyed.pkl  -> the pass's payment table and person key
  v3.1 units (work/gl_v3_1/<key>/units_v3.csv) -> the pass's audit outputs
  outputs (reference_r8_corrected.pkl, reference_note.md, score_dev_final.md) -> rerun_fixed_20261117 (never the frozen out/work)
  the acceptance stop (309 / 246) stays in the frozen pass and is recorded (not enforced) in the fixed pass.
Company maps and guidelines_v3_1.csv stay frozen (config/), as in the stage 2 audit mirror.
Usage: python -X utf8 v9s0_dev_rescore.py <project> <gold folder> <pass: frozen|fixed|control>
Writes rerun_fixed_20261117/v9_stage0/<pass>/{reference_note.md,score_dev_final.md} (aggregates) and
       rerun_fixed_20261117/work/v9_stage0/<pass>/{reference_r8_corrected.pkl,B_v3_1.pkl} (names; local only).
Prints aggregates only.
"""
import sys, pathlib, pandas as pd

P = pathlib.Path(sys.argv[1]).resolve(); GOLD = pathlib.Path(sys.argv[2]); PASS = sys.argv[3]
R = P / "rerun_fixed_20261117"
if PASS == "frozen":
    PK, CK, U31, STRICT = P / "work" / "person_key.pkl", P / "work" / "C_keyed.pkl", P / "work" / "gl_v3_1", True
elif PASS == "fixed":
    PK, CK, U31, STRICT = R / "work" / "person_key.pkl", R / "work" / "C_keyed.pkl", R / "work" / "stage2" / "mirror_fixed" / "work" / "gl_v3_1", False
elif PASS == "control":   # 2022 person identifier not used (work/variant_no2022id); for attributing reasons only
    V = R / "work" / "variant_no2022id"
    PK, CK, U31, STRICT = V / "work" / "person_key.pkl", V / "work" / "C_keyed.pkl", V / "mirror" / "work" / "gl_v3_1", False
else:
    raise SystemExit("pass must be frozen, fixed or control")
OUTD = R / "v9_stage0" / PASS; OUTW = R / "work" / "v9_stage0" / PASS
OUTD.mkdir(parents=True, exist_ok=True); OUTW.mkdir(parents=True, exist_ok=True)

src_path = P / "scripts" / "12_reference_corrected.py"
src = src_path.read_text(encoding="utf-8")
SUBS = [
    ('E = pd.read_pickle(WORK/"person_key.pkl")', 'E = pd.read_pickle(PK_PATH)'),
    ('C = pd.read_pickle(WORK/"C_keyed.pkl")', 'C = pd.read_pickle(CK_PATH)'),
    ('REF.to_pickle(WORK/"reference_r8_corrected.pkl")', 'REF.to_pickle(OUTW/"reference_r8_corrected.pkl")'),
    ('(OUT/"reference_note.md").write_text(', '(OUTD/"reference_note.md").write_text('),
    ('if not acc_ok: raise SystemExit(', 'if not acc_ok and STRICT: raise SystemExit('),
    ('WORK/("gl_v3" if ver == "v3" else "gl_v3_1")/key/"units_v3.csv"', '(WORK/"gl_v3" if ver == "v3" else UNITS31)/key/"units_v3.csv"'),
    ('(OUT/"score_dev_final.md").write_text(', '(OUTD/"score_dev_final.md").write_text('),
]
for a, b in SUBS:
    n = src.count(a)
    assert n == 1, (a, n)
    src = src.replace(a, b)
# no other write may remain
for w in ['.to_pickle(WORK', '(OUT/', '.to_csv(']:
    assert w not in src, w

for f in (PK, CK, U31):
    assert f.exists(), f
ns = dict(__name__="__v9s0__", __file__=str(src_path), PK_PATH=PK, CK_PATH=CK, UNITS31=U31, OUTD=OUTD, OUTW=OUTW, STRICT=STRICT)
sys.argv = [str(src_path), str(P), str(GOLD)]
print("pass", PASS, "| person key", PK.relative_to(P), "| units", U31.relative_to(P))
exec(compile(src, str(src_path), "exec"), ns)
print("acceptance 309/246:", ns["acc_ok"], "| evaluable", ns["n_ev"], "declared", ns["n_decl"])

# matched table of v3.1 (the 346 units), saved for the unit-level comparison
REF, load, K = ns["REF"], ns["load"], ns["K"]
U = load("v3_1")
B = REF[REF.assessment.isin(["evaluable", "unassessable"])].merge(U, on=K, how="inner")
B.to_pickle(OUTW / "B_v3_1.pkl")
U.to_pickle(OUTW / "U_v3_1_lecture.pkl")
agree = int((B.judge == B.r8).sum())
print("v3.1 three-class matched units", len(B), "agreeing", agree)
