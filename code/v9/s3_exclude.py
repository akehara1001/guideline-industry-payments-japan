# -*- coding: utf-8 -*-
"""Stage 3: sensitivity analysis without AbbVie x fiscal 2019 and Sun Pharma x fiscal 2022 (both the personal-payment table C and the
society-payment table B), on the fixed payment tables and person key (user decision of 2026-11-18: the fixed version is the main one).
Usage: python s3_exclude.py <project_dir>
Excluded company-years: P023 アッヴィ x 2019 (its rows equal its 2018 rows in C and in B), P094 サンファーマ x 2022 (equal to its 2021 rows).
Personal payments: the units of these company-years are dropped from the fixed units table (rerun_fixed_20261117/work/stage2/mirror_fixed/
  work/stage18/units_rule2.pkl). This equals rerunning the audits without these rows: a unit is member x company x year x item, and the person
  key is kept as it is (only payments are removed). Statistics with the paper's rules (copied from s4_fiscal_year.py, which reproduces 115):
  evaluable = judge2 已申报/未申报; author deduplication by person x company node x year (a group is undeclared when all its units are);
  authors with at least one undeclared unit among authors with an evaluable unit (115). The unexcluded numbers must reproduce 115 (checked).
Society payments (two channels): rerun_fixed_20261117/work/stage2/tc_fixed is copied to work/stage3/tc_fixed_ex and the edges of these
  company-years are removed from PAID_PERSON and PAID_ORG; scripts/120_two_channels.py runs unchanged; then the counting part of
  scripts/twochannel_comparison.py (everything before its 'reproduction checks' section, which compares with ledger literals) runs unchanged
  on both roots (it asserts guideline by guideline that it reproduces script 120 of the same root) -> Table 3 groups.
Set B contribution: for each of the 73 guidelines, whether the company-year paid an issuing society (or a branch) through the society channel
  (学会捐赠 / 学会共同举办) within the guideline's window, how much, and whether the company leaves set B without that year.
Writes rerun_fixed_20261117/stage3/{copies_check,personal,two_channels,setB,setB_by_guideline,setB_amount_once}.csv and run_120_ex.log (counts). Prints counts only.
"""
import sys, pathlib, shutil, subprocess, math
import pandas as pd, numpy as np

P = pathlib.Path(sys.argv[1]).resolve(); R = P / "rerun_fixed_20261117"; OUT = R / "stage3"; OUT.mkdir(parents=True, exist_ok=True)
EX = {("P023", 2019), ("P094", 2022)}; LAB = {"P023": "アッヴィ×2019", "P094": "サンファーマ×2022"}
rd = lambda f: pd.read_csv(f, dtype=str, keep_default_na=False, encoding="utf-8-sig")

# ---------------- 0. the rows really are copies (fixed tables) ----------------
chk = []
C = pd.read_pickle(R / "work" / "C_keyed.pkl")[["company_id", "year", "nm", "inst", "c3", "amt"]]
B = pd.read_pickle(R / "work" / "B_keyed.pkl")[["company_id", "year", "recip_raw", "b5", "amt"]]
for cid, y0, y1 in (("P023", 2018, 2019), ("P094", 2021, 2022)):
    for name, T, cols in (("C", C, ["nm", "inst", "c3", "amt"]), ("C", C, ["c3", "amt"]), ("B", B, ["recip_raw", "b5", "amt"])):
        ta = T[(T.company_id == cid) & (T.year == y0)]; tb = T[(T.company_id == cid) & (T.year == y1)]
        a = ta[cols].astype(object).fillna("").astype(str).value_counts(dropna=False); b = tb[cols].astype(object).fillna("").astype(str).value_counts(dropna=False)
        d = a.sub(b, fill_value=0)
        chk.append(dict(table=name, company=cid, years=f"{y1} vs {y0}", compared_on="+".join(cols), rows_y1=len(tb), rows_y0=len(ta), amount_y1=float(tb.amt.sum()),
                        amount_y0=float(ta.amt.sum()), rows_only_in_y0=int(d[d > 0].sum()), rows_only_in_y1=int(-d[d < 0].sum()), identical_multiset=bool((d == 0).all())))
del C, B
CK = pd.DataFrame(chk); print(CK.to_string(index=False)); CK.to_csv(OUT / "copies_check.csv", index=False, encoding="utf-8-sig")

# ---------------- 1. personal payments ----------------
U = pd.read_pickle(R / "work" / "stage2" / "mirror_fixed" / "work" / "stage18" / "units_rule2.pkl")
AS = rd(P / "config" / "guidelines_analysis_sets.csv").set_index("key"); U["set"] = U.key.map(AS.analysis_set)
U["ex"] = [(n, int(y)) in EX for n, y in zip(U.node, U.year)]
EV = U.judge2.isin(["已申报", "未申报"])
def wilson(k, n, z=1.959963984540054):
    p = k / n; d = 1 + z * z / n; c = (p + z * z / (2 * n)) / d; h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return p, max(0.0, c - h), min(1.0, c + h)
fm = lambda k, n: (lambda p, lo, hi: f"{p:.2f} [{lo:.2f}, {hi:.2f}] ({k:,}/{n:,})")(*wilson(k, n))
def stats(x):
    x = x[x.person != ""]
    g = x.groupby(["person", "node", "year"]).judge2.agg(lambda s: "未申报" if set(s) == {"未申报"} else "x")
    pp = x.groupby("person").judge2.agg(lambda s: (s == "未申报").any())   # 115: an author with at least one undeclared unit
    return int((g == "未申报").sum()), len(g), int(pp.sum()), len(pp)
rows = []
for sname in ("主分析集", "期间推定层"):
    for ind in ("pharma", "device"):
        x = U[(U.set == sname) & (U.prim == ind) & EV]
        k0, n0, a0, b0 = stats(x); k1, n1, a1, b1 = stats(x[~x.ex])
        e = x[x.ex]
        rows.append(dict(set=sname, industry=ind, units_excluded=len(e), undeclared_units_excluded=int((e.judge2 == "未申报").sum()),
                         excluded_by=str(e.groupby("node").size().rename(index=LAB).to_dict()),
                         dedup_fixed=fm(k0, n0), dedup_excluded=fm(k1, n1), authors_fixed=fm(a0, b0), authors_excluded=fm(a1, b1)))
PR = pd.DataFrame(rows); print(PR.to_string(index=False)); PR.to_csv(OUT / "personal.csv", index=False, encoding="utf-8-sig")
# 115 reproduction (fixed, s2_115_fixed.log): main rule2 dedup pharma (730, 3479) device (87, 331), person pharma (302, 544) device (45, 99); inferred (343, 1408) (7, 18)
want = {("主分析集", "pharma"): ("(730/3,479)", "(302/544)"), ("主分析集", "device"): ("(87/331)", "(45/99)"), ("期间推定层", "pharma"): ("(343/1,408)", "(138/246)"),
        ("期间推定层", "device"): ("(7/18)", "(6/13)")}
for r in PR.itertuples():
    assert r.dedup_fixed.endswith(want[(r.set, r.industry)][0]) and r.authors_fixed.endswith(want[(r.set, r.industry)][1]), (r.set, r.industry, r.dedup_fixed, r.authors_fixed)
print("unexcluded statistics reproduce 115 (fixed): ok")

# ---------------- 2. two channels ----------------
TC0 = R / "work" / "stage2" / "tc_fixed"; TC1 = R / "work" / "stage3" / "tc_fixed_ex"
if TC1.exists(): shutil.rmtree(TC1)
shutil.copytree(TC0, TC1, ignore=shutil.ignore_patterns("s20", "run_120.log", "twochannel_comparison"))
for f in ("paid_person.parquet", "paid_org.parquet"):
    e = pd.read_parquet(TC1 / "kg" / "edges" / f); m = np.array([(s, int(y)) in EX for s, y in zip(e.src_id, e.year)])
    chk_e = e[m].groupby(["src_id", "year"]).agg(edges=("amount", "size"), amount=("amount", "sum")).reset_index()
    print(f, "removed", chk_e.to_dict("records")); e[~m].to_parquet(TC1 / "kg" / "edges" / f, index=False)
r = subprocess.run([sys.executable, "-X", "utf8", str(P / "scripts" / "120_two_channels.py"), str(TC1)], capture_output=True, text=True, encoding="utf-8")
(OUT / "run_120_ex.log").write_text(r.stdout + "\n" + r.stderr, encoding="utf-8"); assert r.returncode == 0, r.stderr[-500:]
src = (P / "scripts" / "twochannel_comparison.py").read_text(encoding="utf-8")
cut = "# ---------------------------------------------------------------- reproduction checks (stop if they fail)\n"; assert src.count(cut) == 1
head = src.split(cut)[0]
def table3(root):
    argv0 = sys.argv; sys.argv = ["twochannel_comparison.py", str(root)]; NS = {"__name__": "tc_head"}
    try: exec(compile(head, str(P / "scripts" / "twochannel_comparison.py"), "exec"), NS)
    finally: sys.argv = argv0
    return NS
N0 = table3(TC0); N1 = table3(TC1)
T0 = pd.read_pickle(TC0 / "work" / "stage20" / "two_channels.pkl"); T1 = pd.read_pickle(TC1 / "work" / "stage20" / "two_channels.pkl")
rows = []
for sname in ("全部", "主分析集", "期间推定层"):
    for ind in ("all", "pharma", "device"):
        a, b = T0["POOL"]["main"][sname][ind], T1["POOL"]["main"][sname][ind]
        rows.append(dict(set=sname, industry=ind, item="S3: set A also in set B (pairs)", fixed=fm(a["AB"], a["A"]), excluded=fm(b["AB"], b["A"])))
        rows.append(dict(set=sname, industry=ind, item="S3: share of society payments from set A, median (IQR)", fixed=a["med_share"], excluded=b["med_share"]))
        rows.append(dict(set=sname, industry=ind, item="S3: pooled share from set A", fixed=f"{a['fromA'] / a['total']:.2f}", excluded=f"{b['fromA'] / b['total']:.2f}"))
        rows.append(dict(set=sname, industry=ind, item="S3: society payers (set B, pairs) / society amount (10,000 JPY)", fixed=f"{a['B']:,} / {a['total'] / 1e4:,.0f}", excluded=f"{b['B']:,} / {b['total'] / 1e4:,.0f}"))
    for g in ("A", "B", "C"):
        m0, m1 = N0["RES"][sname]["main"], N1["RES"][sname]["main"]
        rows.append(dict(set=sname, industry="all", item=f"Table 3 group {g}: pairs whose company paid the issuing society", fixed=fm(m0["s"][g], m0["n"][g]), excluded=fm(m1["s"][g], m1["n"][g])))
        s0, s1 = N0["RES"][sname]["share"][g], N1["RES"][sname]["share"][g]
        rows.append(dict(set=sname, industry="all", item=f"Table 3 group {g}: share of society payments, median (IQR)", fixed=f"{s0[0]:.2f} ({s0[1]:.2f}–{s0[2]:.2f})", excluded=f"{s1[0]:.2f} ({s1[1]:.2f}–{s1[2]:.2f})"))
    ac0, ac1 = N0["RES"][sname]["main"]["AC"], N1["RES"][sname]["main"]["AC"]
    rows.append(dict(set=sname, industry="all", item="Table 3 ratio A vs C", fixed=f"{ac0[0]:.2f}", excluded=f"{ac1[0]:.2f}"))
TR = pd.DataFrame(rows); print(TR.to_string(index=False)); TR.to_csv(OUT / "two_channels.csv", index=False, encoding="utf-8-sig")

# ---------------- 3. how much of set B and of the society amount these company-years are ----------------
POc = N0["POc"]; TGT = N0["TGT"]; WIN = N0["WIN"]; SETS = N0["SETS"]; PPl = N0["PPl"]; THR = N0["THR"]
def setA(k):   # set A of script 120 (the same lines as twochannel_comparison.py)
    pid2m, _ = N0["members"](k); x = PPl[PPl.dst_id.isin(pid2m) & PPl.year.isin(WIN[k])].copy(); x["m"] = x.dst_id.map(pid2m)
    s_ = x.groupby(["src_id", "m", "year"]).amount.sum(); return set(s_[s_ >= THR[k]].index.get_level_values(0))
rows = []
for k in SETS["全部"]:
    y = POc[POc.dst_id.isin(TGT[k]) & POc.year.isin(WIN[k])]; s = y.groupby("src_id").amount.sum(); SOCB = set(s[s > 0].index); tot = float(s.sum())
    for cid, yr in sorted(EX):
        if yr not in WIN[k]: continue
        a_yr = float(y[(y.src_id == cid) & (y.year == yr)].amount.sum()); a_all = float(s.get(cid, 0.0))
        rows.append(dict(key=k, set="主分析集" if k in SETS["主分析集"] else "期间推定层", company=LAB[cid], year_in_window=True, in_setB=cid in SOCB,
                         paid_in_that_year=a_yr > 0, amount_that_year=a_yr, amount_window=a_all, leaves_setB=(cid in SOCB) and (a_all - a_yr) <= 0,
                         society_total=tot, in_setA=cid in setA(k)))
SB = pd.DataFrame(rows)
SB.to_csv(OUT / "setB_by_guideline.csv", index=False, encoding="utf-8-sig")
summ = []
for (sn, co), g in SB.groupby(["set", "company"]):
    summ.append(dict(set=sn, company=co, guidelines_with_year_in_window=len(g), in_setB=int(g.in_setB.sum()), paid_in_that_year=int(g.paid_in_that_year.sum()),
                     leave_setB_without_that_year=int(g.leaves_setB.sum()), in_setA_and_setB=int((g.in_setA & g.in_setB).sum()), amount_that_year_10k=round(g.amount_that_year.sum() / 1e4),
                     share_of_society_amount_of_those_guidelines=f"{g.amount_that_year.sum() / g.society_total.sum():.3f}"))
SM = pd.DataFrame(summ); print(SM.to_string(index=False)); SM.to_csv(OUT / "setB.csv", index=False, encoding="utf-8-sig")
uniq = {LAB[c]: float(POc[(POc.src_id == c) & (POc.year == y) & POc.dst_id.isin(set().union(*TGT.values()))].amount.sum()) for c, y in EX}
print("society-channel amount of each company-year to the issuing societies of the 73 guidelines (counted once):", {k: round(v / 1e4) for k, v in uniq.items()}, "(10,000 JPY)")
pd.DataFrame([dict(company=k, amount_10k_once=round(v / 1e4)) for k, v in uniq.items()]).to_csv(OUT / "setB_amount_once.csv", index=False, encoding="utf-8-sig")
