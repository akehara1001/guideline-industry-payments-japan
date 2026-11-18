# -*- coding: utf-8 -*-
"""Build the release set for v10 (to be pushed to a public GitHub repository after the checks): Desktop/上研/influence_kg/release_v10
  data/units_v10.csv      audit units of the 73 guidelines on the fixed payment tables; authors and payment-data persons replaced by numbers;
                          amounts replaced by a class relative to the guideline's own threshold
  data/guidelines_v10.csv guideline key, title, title year, analysis set, thresholds (10,000 JPY)
  data/companies_v10.csv  company id, name, industry, merged company node
  data/two_channels_pairs_v10.csv  guideline x company pairs of the two-channel comparison (Table 3, S3 Table): group A/B/C, society channel, amounts paid to the issuing societies (JPY)
  data/societies_v10.csv  lead societies: id, English name, code letter of Fig 2 and S1 Fig
  prompts/                the frozen extraction and company-resolution prompts of pipeline v3.1 (sha256 checked against out/pipeline_freeze_v3_1.md)
  code/                   pipeline, analysis and v9 and v10 scripts (copied unchanged)
  README.md
Then checks mechanically that no personal name, no institution of a person and no amount is left (counts only; names are never printed).
Usage: python -X utf8 v10_release.py <project>
"""
import sys, pathlib, shutil, hashlib, re, unicodedata, json
import pandas as pd
P = pathlib.Path(sys.argv[1]).resolve(); R = P / "rerun_fixed_20261117"; REL = P / "release_v10"
REL.mkdir(exist_ok=True)
for x in REL.iterdir():   # empty the folder (the folder itself may be in use as a working directory)
    shutil.rmtree(x) if x.is_dir() else x.unlink()
for d in ["data", "prompts", "code/pipeline", "code/analysis", "code/revised_data", "code/v9", "code/v10"]: (REL / d).mkdir(parents=True)
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
rd = lambda f: pd.read_csv(f, dtype=str, keep_default_na=False, encoding="utf-8-sig")

# ---------------- units
U = pd.read_pickle(R / "work" / "stage2" / "mirror_fixed" / "work" / "stage18" / "units_rule2.pkl")
AS = rd(P / "config" / "guidelines_analysis_sets.csv").set_index("key")
G = pd.read_parquet(P / "kg" / "nodes" / "guideline.parquet").set_index("guideline_id")
TH = {"講演料": "lecture_threshold_man", "原稿料": "manuscript_threshold_man"}
U["thr"] = [float(AS.loc[k, TH[i]]) * 10000 for k, i in zip(U.key, U["item"])]
U["amount_class"] = ["below the guideline's threshold" if a < t else ("at least twice the threshold" if a >= 2 * t else "at or above the threshold") for a, t in zip(U.amt, U.thr)]
_b = U.amount_class == "below the guideline's threshold"
assert (U.below_thr <= _b).all() and (U[_b & ~U.below_thr].judge2 == "无法评价").all()   # not assessable is judged before the threshold rule
pend = {k: int(re.match(r"(\d{4})", str(G.loc[k, "disclosure_period_end"])).group(1)) for k in set(U.key)}
U["last_fiscal_year_excluded_in_S10"] = [(y == int(G.loc[k, "audit_year_last"])) and pend[k] <= 2023 for k, y in zip(U.key, U.year)]
U = U.sort_values(["key", "node", "year", "item", "ind"]).reset_index(drop=True)
amap = {n: f"A{i + 1:04d}" for i, n in enumerate(dict.fromkeys(U.nm))}
pmap = {n: f"Q{i + 1:05d}" for i, n in enumerate(dict.fromkeys(U.person.astype(str)))}
J = {"已申报": "declared", "未申报": "undeclared", "无法评价": "not assessable", "未达该指南的申报门槛": "below the guideline's threshold"}
SET = {"主分析集": "main analysis set", "期间推定层": "period-inferred layer"}
IND = {"pharma": "pharmaceutical", "device": "medical device"}
OUTU = pd.DataFrame({
    "guideline": U.key, "analysis_set": U.key.map(AS.analysis_set).map(SET), "author": U.nm.map(amap), "payment_person": U.person.astype(str).map(pmap),
    "company_id": U.ck, "company_node": U.node, "company_node_industry": U.prim.map(IND), "payment_data": U.ind.map(IND),
    "payment_category": U["item"].map({"講演料": "lecture fees", "原稿料": "manuscript fees"}), "fiscal_year": U.year,
    "amount_class": U.amount_class, "judgment_main": U.judge2.map(J), "judgment_frozen_pipeline": U.judge_frozen.map(J),
    "external_evaluation_committee": U.external, "last_fiscal_year_excluded_in_S10": U.last_fiscal_year_excluded_in_S10})
assert OUTU.notna().all().all(), OUTU.isna().sum()
OUTU.to_csv(REL / "data" / "units_v10.csv", index=False, encoding="utf-8")
# reproduction check from the release file alone: main estimate (Table 4) and S10 rows
def dd(x):
    g = x.groupby(["payment_person", "company_node", "fiscal_year"]).judgment_main.agg(lambda s: "u" if set(s) == {"undeclared"} else ("d" if set(s) == {"declared"} else "m"))
    return int((g == "u").sum()), len(g)
X = OUTU[(OUTU.analysis_set == "main analysis set") & OUTU.judgment_main.isin(["declared", "undeclared"])]
repro = {}
for ind in ["pharmaceutical", "medical device"]:
    x = X[X.company_node_industry == ind]
    repro[ind] = dict(all=dd(x), twice=dd(x[x.amount_class == "at least twice the threshold"]),
                      twice_nolast=dd(x[(x.amount_class == "at least twice the threshold") & ~x.last_fiscal_year_excluded_in_S10]))
assert repro["pharmaceutical"] == dict(all=(730, 3479), twice=(159, 1249), twice_nolast=(116, 942)), repro
assert repro["medical device"] == dict(all=(87, 331), twice=(21, 105), twice_nolast=(18, 78)), repro
# guidelines and companies
GL = AS.loc[sorted(set(U.key)), ["title", "title_year", "analysis_set", "lecture_threshold_man", "manuscript_threshold_man", "threshold_source_class"]].copy()
GL["analysis_set"] = GL.analysis_set.map(SET); GL.index.name = "guideline"; GL.to_csv(REL / "data" / "guidelines_v10.csv", encoding="utf-8")
CM = rd(P / "config" / "company_master.csv")[["company_id", "canonical_name", "ind"]]
NODE = rd(P / "work" / "kg_build_v02" / "company_merge.csv")[["company_id", "node_id", "industry_primary"]]
CO = CM.merge(NODE, on="company_id", how="left")   # written after the pairs: every company of the units and every company merged into a node of the pairs
# ---------------- two channels: guideline x company pairs (Table 3, S3 Table), recomputed with the code of scripts/twochannel_comparison.py
# (definitions of script 120, unchanged) on the inputs of the fixed run (rerun_fixed_20261117/work/stage2/tc_fixed: graph edges rebuilt from the fixed
# payment tables, written by s2_tc_direct.py), then checked guideline by guideline against the aggregates behind the v9/v10 tables
# (mirror_fixed/ledger_root/work/twochannel_comparison/twochannel_comparison.pkl and work/stage20/two_channels.pkl). No person-level column is written.
TCR = R / "work" / "stage2" / "tc_fixed"; KG = TCR / "kg"
GLN = pd.read_parquet(KG / "nodes" / "guideline.parquet").set_index("guideline_id")
CON = pd.read_parquet(KG / "nodes" / "company.parquet").set_index("company_id")
ORG = pd.read_parquet(KG / "nodes" / "org.parquet", columns=["org_id", "org_type", "parent_org_id"])
CMm = pd.read_parquet(KG / "edges" / "committee_member.parquet")
PP = pd.read_parquet(KG / "edges" / "paid_person.parquet", columns=["src_id", "dst_id", "year", "category", "amount"])
PO = pd.read_parquet(KG / "edges" / "paid_org.parquet", columns=["src_id", "dst_id", "year", "category", "amount"])
IB = pd.read_parquet(KG / "edges" / "issued_by.parquet")
MEM = pd.read_pickle(TCR / "work" / "kg_build_v07" / "members.pkl")
N18 = pd.read_pickle(TCR / "work" / "stage18" / "report_numbers.pkl"); RN = pd.read_pickle(TCR / "work" / "census3" / "report_numbers.pkl")
TC = pd.read_pickle(TCR / "work" / "stage20" / "two_channels.pkl")
CMP = pd.read_pickle(R / "work" / "stage2" / "mirror_fixed" / "ledger_root" / "work" / "twochannel_comparison" / "twochannel_comparison.pkl")
AS2 = rd(TCR / "config" / "guidelines_analysis_sets.csv").set_index("key")
LAST = 2023; CH2 = ["学会捐赠", "学会共同举办"]
SETS2 = {"主分析集": list(N18["MAIN"]), "期间推定层": list(N18["INF"])}; KEYS = SETS2["主分析集"] + SETS2["期间推定层"]
assert len(KEYS) == 73 and set(zip(CMm.src_id, CMm.dst_id)) == {(i, g) for g, v in zip(MEM.guideline_id, MEM.node_ids) for i in v}
ISS = {k: sorted(IB.loc[IB.src_id == k, "dst_id"]) for k in KEYS}; assert all(ISS[k] == sorted(RN["ISS"][k]) for k in KEYS)
MEM["scope"] = (MEM.in_scope == "是") | ((MEM.in_scope == "不明") & MEM.listed)
WIN = {k: [y for y in range(int(GLN.loc[k, "audit_year_first"]), int(GLN.loc[k, "audit_year_last"]) + 1) if y <= LAST] for k in KEYS}
THR = {k: max(500_000.0, float(AS2.loc[k, "lecture_threshold_man"]) * 1e4) for k in KEYS}
TGT = {k: set(ISS[k]) | set(ORG.loc[ORG.parent_org_id.isin(ISS[k]), "org_id"]) for k in KEYS}
PPl = PP[PP.category == "讲演"]; POc = PO[PO.category.isin(CH2)]
assert WIN == TC["WIN"] and THR == TC["THR"]
GSOC = {k: v["soc"] for k, v in N18["NUM"]["B7"].items()}
pairs = []
for k in KEYS:
    yrs = WIN[k]; m = MEM[(MEM.guideline_id == k) & MEM.scope].reset_index(drop=True)
    pid2m = {pid: i for i, ids in enumerate(m.node_ids) for pid in ids}
    x = PPl[PPl.dst_id.isin(pid2m) & PPl.year.isin(yrs)].copy(); x["m"] = x.dst_id.map(pid2m)
    s = x.groupby(["src_id", "m", "year"]).amount.sum(); A = set(s[s >= THR[k]].index.get_level_values(0))
    y = POc[POc.dst_id.isin(TGT[k]) & POc.year.isin(yrs)]; s2 = y.groupby("src_id").amount.sum(); SOCB = set(s2[s2 > 0].index)
    ANY = set(PP[PP.dst_id.isin(pid2m) & PP.year.isin(yrs)].src_id)
    Uu = (set(PP.loc[PP.year.isin(yrs), "src_id"]) | set(PO.loc[PO.year.isin(yrs), "src_id"])) & set(CON.index)
    UD = Uu & set(PO.loc[PO.year.isin(yrs) & PO.category.isin(CH2), "src_id"])
    assert A <= ANY <= Uu and SOCB <= Uu
    for c in sorted(Uu):
        amt = float(s2.get(c, 0.0)); assert amt == round(amt)
        pairs.append(dict(guideline=k, analysis_set=SET[AS2.loc[k, "analysis_set"]], lead_society=GSOC[k], window_first_year=min(yrs), window_last_year=max(yrs),
                          company_node=c, company_node_industry=IND[CON.loc[c, "industry_primary"]], group="A" if c in A else ("B" if c in ANY else "C"),
                          paid_issuing_society=c in SOCB, society_payment_jpy=int(amt), paid_any_society_in_window=c in UD))
PR = pd.DataFrame(pairs)
# check against the aggregates behind the tables, guideline by guideline (exact)
for k in KEYS:
    g = PR[PR.guideline == k]; per = CMP["PER"][k]
    for gr in "ABC":
        h = g[g.group == gr]; hd = h[h.paid_any_society_in_window]
        assert (len(h), int(h.paid_issuing_society.sum()), len(hd), int(hd.paid_issuing_society.sum())) == (per["n"][gr], per["s"][gr], per["nd"][gr], per["sd"][gr]), (k, gr)
        assert h.society_payment_jpy.sum() == round(per["amt"][gr]), (k, gr)
    assert g.society_payment_jpy.sum() == round(per["total"]) and len(g) == per["U"] and int(g.paid_any_society_in_window.sum()) == per["UD"], k
    r = TC["RES"]["main"][k]["all"]
    assert (int((g.group == "A").sum()), int(((g.group == "A") & g.paid_issuing_society).sum()), int(g.paid_issuing_society.sum())) == (r["A"], r["AB"], r["B"]), k
    assert g[g.group == "A"].society_payment_jpy.sum() == round(r["fromA"]) and g.society_payment_jpy.sum() == round(r["total"]), k
PR.to_csv(REL / "data" / "two_channels_pairs_v10.csv", index=False, encoding="utf-8")
CO = CO[CO.company_id.isin(set(U.ck)) | CO.node_id.isin(set(PR.company_node))]
assert set(PR.company_node) <= set(CO.node_id) and set(U.ck) <= set(CO.company_id) and set(U.node) <= set(CO.node_id), "company table incomplete"
CO.rename(columns={"canonical_name": "company", "ind": "industry", "node_id": "company_node", "industry_primary": "company_node_industry"}).to_csv(REL / "data" / "companies_v10.csv", index=False, encoding="utf-8")

# reproduction of Table 3 and the S3 Table total row from the release file alone (two decimals, half up; Wilson for proportions)
import math
from decimal import Decimal, ROUND_HALF_UP
from fractions import Fraction
def hu2(x): return str((Decimal(x.numerator) / Decimal(x.denominator)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)) if isinstance(x, Fraction) else str(Decimal(repr(float(x))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
def wil(k, n, z=1.959963984540054):
    p = k / n; d = 1 + z * z / n; c = (p + z * z / (2 * n)) / d; h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d; return max(0.0, c - h), min(1.0, c + h)
def pq(v, q):
    v = sorted(v); hh = (len(v) - 1) * Fraction(q, 100); lo = math.floor(hh); hi = math.ceil(hh); return v[lo] + (hh - lo) * (v[hi] - v[lo])
T3 = {}
for lab, sel in (("A all 73", PR), ("B main 48", PR[PR.analysis_set == "main analysis set"]), ("C inferred 25", PR[PR.analysis_set == "period-inferred layer"]), ("D universe d", PR[PR.paid_any_society_in_window])):
    row = {}
    for gr in "ABC":
        h = sel[sel.group == gr]; n_, s_ = len(h), int(h.paid_issuing_society.sum()); lo, hi = wil(s_, n_)
        tot = sel.groupby("guideline").society_payment_jpy.sum(); fa = h.groupby("guideline").society_payment_jpy.sum().reindex(tot.index, fill_value=0)
        sh = [Fraction(int(fa[k]), int(tot[k])) for k in tot.index if tot[k] > 0]
        row[gr] = f"{n_:,} | {hu2(Fraction(s_, n_))} [{hu2(lo)}, {hu2(hi)}] ({s_:,}/{n_:,}) | {hu2(pq(sh, 50))} ({hu2(pq(sh, 25))}–{hu2(pq(sh, 75))})"
    a = sel[sel.group == "A"]; c = sel[sel.group == "C"]
    row["ratio A vs C"] = hu2(Fraction(int(a.paid_issuing_society.sum()), len(a)) / Fraction(int(c.paid_issuing_society.sum()), len(c)))
    T3[lab] = row
S3TOT = dict(pairs_A=int((PR.group == "A").sum()), A_paying_society=int(((PR.group == "A") & PR.paid_issuing_society).sum()),
             payments_10000_jpy=f"{Decimal(int(PR.society_payment_jpy.sum())) / 10000:,.0f}")
pair_repro = dict(table3=T3, s3_total=S3TOT)
# every cell of Table 3 in manuscript_v10.docx equals the reproduction from the release file alone; S3 Table total row likewise
import docx as _docx
_t3 = _docx.Document(P / "paper" / "v10" / "manuscript_v10.docx").tables[4]
_panel = None; _ok = 0; _n = 0
for r in [[c.text.strip() for c in row.cells] for row in _t3.rows][1:]:
    if r[0].startswith("Panel"):
        _panel = {"A": "A all 73", "B": "B main 48", "C": "C inferred 25", "D": "D universe d"}[r[0][6]]; continue
    g = r[0][6]; mine = T3[_panel][g].split(" | ")
    if _panel == "D universe d": mine[2] = "—"   # panel D prints no share (the shares do not depend on the restriction of the universe)
    for shown, want in zip(r[1:4], mine):
        _n += 1; _ok += re.sub(r"[✱†‡§¶‖]", "", shown) == want
    if g == "A":
        _n += 1; _ok += re.sub(r"[✱†‡§¶‖]", "", r[4]) == T3[_panel]["ratio A vs C"]
_s3 = _docx.Document(P / "paper" / "v10" / "supplementary_v10.docx").tables[2]
_rows3 = {row.cells[0].text.strip(): [c.text.strip() for c in row.cells] for row in _s3.rows if row.cells[0].text.startswith("Total")}
_tot = _rows3["Total, all analyzed guidelines"]
_s3ok = (_tot[2], _tot[3].split(" (")[1].rstrip(")"), _tot[4]) == (f"{S3TOT['pairs_A']:,}", f"{S3TOT['A_paying_society']:,}/{S3TOT['pairs_A']:,}", S3TOT["payments_10000_jpy"])
for _lab, _set in (("Total, main analysis set", "main analysis set"), ("Total, period-inferred layer", "period-inferred layer")):
    _x = PR[PR.analysis_set == _set]
    _s3ok = _s3ok and _rows3[_lab][4] == f"{Decimal(int(_x.society_payment_jpy.sum())) / 10000:,.0f}" and _rows3[_lab][2] == f"{int((_x.group == 'A').sum()):,}"
pair_repro["docx_check"] = dict(table3_cells_equal=f"{_ok}/{_n}", s3_total_row_equal=_s3ok)
assert _ok == _n and _s3ok, pair_repro["docx_check"]
# societies (lead societies; English names and code letters as in the paper tables, from scripts/113_paper_tables.py)
import ast
src113 = (P / "scripts" / "113_paper_tables.py").read_text(encoding="utf-8")
SOC_EN = ast.literal_eval(re.search(r"^SOC_EN = (\{.*?\})$", src113, re.S | re.M).group(1))
FRAME = list(rd(P / "work" / "expansion" / "society_rank.csv").society_id); CODEL = {s_: chr(ord("A") + j) for j, s_ in enumerate(FRAME)}
SO = pd.DataFrame([dict(society_id=s_, society=SOC_EN[s_], code_in_fig2_and_s1fig=CODEL[s_], guidelines_in_this_study=int(sum(1 for k in KEYS if GSOC[k] == s_))) for s_ in FRAME])
SO.to_csv(REL / "data" / "societies_v10.csv", index=False, encoding="utf-8")
assert set(PR.lead_society) <= set(SO.society_id)

# ---------------- prompts (frozen v3.1)
fz = (P / "out" / "pipeline_freeze_v3_1.md").read_text(encoding="utf-8")
for f in ["config/prompt_extraction_v3.md", "config/prompt_company_resolve_v2.md"]:
    h = sha(P / f); assert h in fz, f; shutil.copy2(P / f, REL / "prompts" / pathlib.Path(f).name)
# ---------------- code
CODE = {"pipeline": ["scripts/01_build_tables.py", "scripts/02_company_master.py", "scripts/03_person_key.py", "scripts/ref_aim3_1_units_and_stoppers.py",
                     "scripts/06_doc_to_text_v3_1.py", "scripts/04_guideline_pilot_v3_1.py"],
        "analysis": ["scripts/115_census_final_v5_stage18.py", "scripts/113_paper_tables.py", "scripts/120_two_channels.py", "scripts/122_overlap.py",
                     "scripts/twochannel_comparison.py"],
        "revised_data": ["rerun_fixed_20261117/scripts/mixload.py", "rerun_fixed_20261117/config_load/sources.csv", "rerun_fixed_20261117/config_load/column_map_fixed.csv",
                         "rerun_fixed_20261117/config_load/name_rules.csv", "rerun_fixed_20261117/config_load/code_override.csv"],
        "v9": ["rerun_fixed_20261117/scripts/s3_exclude.py", "rerun_fixed_20261117/scripts/s4_fiscal_year.py", "rerun_fixed_20261117/scripts/v9s0_dev_rescore.py",
               "rerun_fixed_20261117/scripts/v9t2_v2_mirror.py", "rerun_fixed_20261117/scripts/v9t2_rep_compare.py", "rerun_fixed_20261117/scripts/v9t2_summary.py",
               "rerun_fixed_20261117/scripts/v9_release.py"],
        "v10": ["rerun_fixed_20261117/scripts/v10_rounding.py", "rerun_fixed_20261117/scripts/v10_ledger_halfup.py", "rerun_fixed_20261117/scripts/v10_release.py"]}
for d, fs in CODE.items():
    for f in fs: shutil.copy2(P / f, REL / "code" / d / pathlib.Path(f).name)
assert sha(REL / "code" / "pipeline" / "04_guideline_pilot_v3_1.py") in fz
# the local user folder in file paths carries a personal name: replace it with <user> in the copies (the originals keep their sha256)
HOME = pathlib.Path.home().name; ORIG_SHA = {}; REDACTED = []
for f in list((REL / "code").rglob("*")) + list((REL / "prompts").rglob("*")):
    if not f.is_file(): continue
    t = f.read_text(encoding="utf-8")
    t2 = re.sub(r"(Users[\\/]+)" + re.escape(HOME), lambda m: m.group(1) + "<user>", t)
    if t2 != t:
        ORIG_SHA[f.name] = sha(f); f.write_text(t2, encoding="utf-8"); REDACTED.append(str(f.relative_to(REL)))
    assert HOME not in f.read_text(encoding="utf-8"), f
# ---------------- README
n_auth, n_pers = len(amap), len(pmap)
t3md = "\n".join(f"| {lab} | {r['A']} | {r['B']} | {r['C']} | {r['ratio A vs C']} |" for lab, r in pair_repro["table3"].items())
_redacted = ", ".join(x for x in REDACTED if not x.startswith("prompts"))
_sha_ext = ORIG_SHA.get("prompt_extraction_v3.md", sha(REL / "prompts" / "prompt_extraction_v3.md"))[:12]
_sha_res = ORIG_SHA.get("prompt_company_resolve_v2.md", sha(REL / "prompts" / "prompt_company_resolve_v2.md"))[:12]
readme = f"""# Industry payments to clinical practice guideline committees and to the issuing societies in Japan

Data and code for the manuscript "Industry payments to clinical practice guideline committees and to the issuing societies in Japan: an audit of 25 medical societies, 2022 to 2025".

The repository holds the audit units behind the main estimate, the guideline-company pairs behind the comparison of the two channels, the frozen prompts of the extraction pipeline and the analysis code. It holds no name of a person, no institution of a person and no amount paid to a person.

## Payment data

The payment data are public: they are the payments that pharmaceutical and medical device companies disclose. Personal payments of pharmaceutical companies in 2018, 2019, 2022 and 2023 come from the revised version of the pharmaceutical payment database (製薬マネーデータベース) dated 17 November 2026; S1 Text, section 1, of the manuscript lists the four files and their MD5 checksums. That version does not include the later re-acquisition of the AbbVie 2019 and Sun Pharma 2022 records. In fiscal year 2022, persons are defined by the person identifier of that version. Institutional payments (donations and co-sponsorship fees paid to medical societies) are those the companies disclosed for 2016 to 2023.

## Definitions

- Unit: one author × one company × one fiscal year × one payment category (lecture fees or manuscript fees) in which the company paid the author at least JPY 500,000 (the audit threshold) in a year within the guideline's declaration period.
- Declaration threshold: the amount from which the guideline asked its authors to declare a payment, taken from the guideline or, when the guideline did not state it, from the conflict-of-interest rules of the issuing society (data/guidelines_v10.csv, in 10,000 JPY).
- Judgment of a unit: declared (the author's declaration lists the company in that category and year), undeclared (it does not), not assessable (the documents do not allow a judgment, including a payment category outside the guideline's disclosed items), below the guideline's threshold (not counted).
- Amount class of a unit (data/units_v10.csv): the amount relative to the guideline's own declaration threshold for the category. "at or above the threshold" means at least the threshold and less than twice the threshold; "at least twice the threshold" means twice the threshold or more; "below the guideline's threshold" means less than the threshold. Every unit reached the audit threshold of JPY 500,000.
- Window of a guideline (two channels): the guideline's audit years, up to 2023 (the last year of the payment data).
- Groups of a guideline-company pair (two channels): A, the company paid one author of the guideline a lecture fee of at least the audit threshold (the larger of JPY 500,000 and the guideline's lecture-fee threshold) in one window year; B, the company paid at least one author a personal payment of any category in the window but is not in A; C, the company paid no author any personal payment in the window. The companies of a guideline are the merged companies with any published payment record (personal or institutional) in a window year.
- Society channel: the company paid the issuing societies of the guideline (each issuing society, its branches and regional meetings, and its meetings) society donations or co-sponsorship fees in the window.

## data/units_v10.csv ({len(OUTU):,} rows)

One row per audit unit: guideline × author × company node × payment category × fiscal year, for the 73 guidelines of the main analysis set (48) and the period-inferred layer (25).

| Column | Content |
|---|---|
| guideline | guideline key (data/guidelines_v10.csv) |
| analysis_set | main analysis set (declaration period stated) or period-inferred layer (period inferred from the title year) |
| author | committee member, replaced by a number (A0001 to A{n_auth:04d}); the same number for the same normalized name across guidelines |
| payment_person | the person in the payment data to whom the author was linked, replaced by a number (Q00001 to Q{n_pers:05d}); used for the deduplication by author × company × year |
| company_id, company_node | paying company and the merged company (data/companies_v10.csv) |
| company_node_industry | industry of the merged company (pharmaceutical or medical device); the industry used in the paper |
| payment_data | the data set in which the payment was disclosed (pharmaceutical or medical device) |
| payment_category | lecture fees or manuscript fees |
| fiscal_year | Japanese fiscal year of the payment (April to March) |
| amount_class | below the guideline's threshold, at or above the threshold, at least twice the threshold (see Definitions) |
| judgment_main | judgment of the main estimate (company-name corrections, item rule and threshold rule applied): declared, undeclared, not assessable, below the guideline's threshold |
| judgment_frozen_pipeline | judgment of the frozen pipeline before the corrections: declared, undeclared, not assessable |
| external_evaluation_committee | the author was a member of the external evaluation committee of one society (True or False) |
| last_fiscal_year_excluded_in_S10 | the unit lies in the last fiscal year of a declaration period that ended in 2023 or earlier (S10 Table) |

Check from this file alone (main analysis set, judgment_main declared or undeclared, deduplicated to payment_person × company_node × fiscal_year; a group is undeclared when all its units are undeclared):
pharmaceutical 730 of 3,479 undeclared (Table 4); at least twice the threshold 159 of 1,249; also outside the last fiscal year 116 of 942 (S10 Table);
medical device 87 of 331, 21 of 105 and 18 of 78.

## data/two_channels_pairs_v10.csv ({len(PR):,} rows)

One row per guideline × company pair of the 73 guidelines: the source of Table 3 and of panels A to C of S3 Table.

| Column | Content |
|---|---|
| guideline | guideline key (data/guidelines_v10.csv) |
| analysis_set | main analysis set or period-inferred layer |
| lead_society | lead society of the guideline (data/societies_v10.csv); the rows of S3 Table |
| window_first_year, window_last_year | the guideline's window (calendar years of the payment data) |
| company_node | merged company (data/companies_v10.csv) |
| company_node_industry | pharmaceutical or medical device (panels B and C of S3 Table) |
| group | A, B or C (see Definitions) |
| paid_issuing_society | the company is in the society channel of the guideline (True or False) |
| society_payment_jpy | the amount the company paid the issuing societies of the guideline in the window, in JPY (society donations and co-sponsorship fees; 0 when none). Amounts paid to organizations, not to persons. |
| paid_any_society_in_window | the company paid any medical society donations or co-sponsorship fees in the window (True or False); the companies of panel D of Table 3 |

Check from this file alone (proportion of pairs whose company paid the issuing society, Wilson 95% CI, with pairs; share of the society payments from the group: median (quartiles) over the guidelines with a non-zero total, numpy-linear quartiles; ratio of the proportions, group A vs group C; two decimals, rounded half up):

| Table 3 panel | Group A: pairs, proportion, share | Group B | Group C | Ratio A vs C |
|---|---|---|---|---|
{t3md}

S3 Table, total row: {pair_repro['s3_total']['pairs_A']:,} pairs in group A, {pair_repro['s3_total']['A_paying_society']:,} of them paying the issuing society; payments to the issuing societies {pair_repro['s3_total']['payments_10000_jpy']} (10,000 JPY). Panel D of S3 Table (other definitions of the two sets) needs code/analysis/120_two_channels.py.

## data/guidelines_v10.csv, data/companies_v10.csv, data/societies_v10.csv

- guidelines_v10.csv: guideline key, title as published, title year, analysis set, declaration thresholds for lecture fees and manuscript fees (10,000 JPY), source class of the threshold (写在指南里 = stated in the guideline; 取自发行学会的规定 = taken from the issuing society's rules; values as in the project files).
- companies_v10.csv: company id, company name, industry of the company, the merged company (company_node) and its industry.
- societies_v10.csv: the 25 sampled societies: id, English name, code letter in Fig 2 and S1 Fig, number of guidelines of this study whose lead society it is.

## prompts/

The extraction prompt and the company-resolution prompt of pipeline v3.1, frozen on 11 October 2026. The sha256 of the frozen originals (as in the project's freeze record) are prompt_extraction_v3.md {_sha_ext}… and prompt_company_resolve_v2.md {_sha_res}…. In these copies, and in {_redacted}, the local user folder in file paths is replaced with &lt;user&gt;; nothing else differs from the files as run.

## code/

- pipeline/: building the payment tables (01), company keys (02), person keys (03, with its institution and specialty reference table), conversion of guideline documents to text (06) and the audit of pipeline v3.1 (04, frozen).
- analysis/: the analysis sets and their estimates (115), the paper tables and figures (113), the two channels (120, twochannel_comparison.py) and the pharmaceutical-device overlap (122).
- revised_data/: reading the revised 2018, 2019, 2022 and 2023 pharmaceutical files with the frozen 01 (mixload.py and its four settings).
- v9/: the AbbVie 2019 and Sun Pharma 2022 check (s3), the fiscal-year analysis of S10 Table (s4), the Table 2 recomputation (v9s0, v9t2) and the earlier release script.
- v10/: re-rounding half up of the proportions in the tables and figures (v10_rounding.py, v10_ledger_halfup.py) and the script that built this repository (v10_release.py).

The scripts are copied as they were run; their paths point to the project folders. The model extraction outputs, the guideline documents and the payment files are not included.
"""
(REL / "README.md").write_text(readme, encoding="utf-8")

# ---------------- mechanical checks: names, institutions, amounts
sys.path.insert(0, str(P / "scripts"))
import importlib.util
spec = importlib.util.spec_from_file_location("pk", P / "scripts" / "03_person_key.py"); pk = importlib.util.module_from_spec(spec); spec.loader.exec_module(pk)
names_roster = set()
for f in list(P.glob("*/work/gl_v3_1/*/roster_v3.csv")) + list(P.glob("work/gl_v3_1/*/roster_v3.csv")):
    names_roster |= set(rd(f).nm)
names_roster.discard("")
E = pd.read_pickle(R / "work" / "person_key.pkl"); names_pay = set(E.nm[E.nm.str.len() >= 3]); del E
C = pd.read_pickle(R / "work" / "C.pkl")
insts = set();
for col in [c for c in ["inst", "dept"] if c in C.columns]:
    insts |= {unicodedata.normalize("NFKC", str(x)).replace(" ", "").replace("　", "") for x in C[col].dropna().unique()}
del C
insts = {x for x in insts if len(x) >= 4}
NAMESET = {n for n in names_roster if len(n) >= 2} | names_pay
CJK = re.compile(r"[㐀-鿿぀-ヿ豈-﫿々〆ヶ]+")
res = []
for f in sorted(REL.rglob("*")):
    if not f.is_file(): continue
    t = unicodedata.normalize("NFKC", f.read_text(encoding="utf-8", errors="ignore")).replace(" ", "").replace("　", "")
    runs = CJK.findall(t)
    nh = sum(1 for r in runs for L in range(2, min(12, len(r)) + 1) for i in range(len(r) - L + 1) if r[i:i + L] in NAMESET)
    nh_roster = sum(1 for r in runs for L in range(2, min(12, len(r)) + 1) for i in range(len(r) - L + 1) if r[i:i + L] in names_roster)
    ih = sum(1 for r in runs for L in range(4, min(40, len(r)) + 1) for i in range(len(r) - L + 1) if r[i:i + L] in insts)
    big = len(re.findall(r"(?<![\w.])\d{6,}(?![\w.])", t)) if f.suffix == ".csv" else None
    res.append(dict(file=str(f.relative_to(REL)), cjk_runs=len(runs), name_hits=nh, roster_name_hits=nh_roster, institution_hits=ih, numbers_6plus_digits_in_csv=big))
CH = pd.DataFrame(res); CH.to_csv(R / "v10_audit" / "release_checks.csv", index=False, encoding="utf-8-sig")
cols = list(OUTU.columns)
_six = re.compile(r"\d{6,}")
pr_six_outside = int(sum(PR[c].astype(str).str.fullmatch(_six).sum() for c in PR.columns if c != "society_payment_jpy"))
pr_six_inside = int(PR.society_payment_jpy.astype(str).str.fullmatch(_six).sum())
ua_rel = {str(f.relative_to(REL)): len(re.findall("unassessable", f.read_text(encoding="utf-8", errors="ignore"), re.I)) for f in REL.rglob("*") if f.is_file()}
summary = dict(pairs_six_digit_numbers_outside_society_payment=pr_six_outside, pairs_six_digit_numbers_in_society_payment=pr_six_inside,
               unassessable_in_readme_and_data={k: v for k, v in ua_rel.items() if k == "README.md" or k.startswith("data")},
               unassessable_in_code={k: v for k, v in ua_rel.items() if v and not (k == "README.md" or k.startswith("data"))},
               units=len(OUTU), pairs=len(PR), pair_columns=list(PR.columns), amount_columns_pairs=[c for c in PR.columns if 'jpy' in c], pair_repro=pair_repro, authors=n_auth, payment_persons=n_pers, columns=cols, amount_columns=[c for c in cols if re.search("amt|amount_jpy|yen", c)],
               name_set=len(NAMESET), roster_names=len(names_roster), institution_set=len(insts), files=len(CH),
               files_with_name_hits=CH[CH.name_hits > 0].file.tolist(), files_with_roster_name_hits=CH[CH.roster_name_hits > 0].file.tolist(),
               files_with_institution_hits=CH[CH.institution_hits > 0].file.tolist(), csv_numbers_6plus=int(CH.numbers_6plus_digits_in_csv.fillna(0).sum()), repro=repro)
(R / "v10_audit" / "release_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
print(json.dumps({k: v for k, v in summary.items() if k != "columns"}, ensure_ascii=False, default=str))
print(CH.to_string(index=False))
