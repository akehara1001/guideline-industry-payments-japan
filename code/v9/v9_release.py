# -*- coding: utf-8 -*-
"""Build the release set for v9 (not published, not pushed): Desktop/上研/influence_kg/release_v9
  data/units_v9.csv       audit units of the 73 guidelines on the fixed payment tables; authors and payment-data persons replaced by numbers;
                          amounts replaced by a class relative to the guideline's own threshold
  data/guidelines_v9.csv  guideline key, title, title year, analysis set, thresholds (10,000 JPY)
  data/companies_v9.csv   company id, name, industry, merged company node
  prompts/                the frozen extraction and company-resolution prompts of pipeline v3.1 (sha256 checked against out/pipeline_freeze_v3_1.md)
  code/                   pipeline, analysis and v9 scripts (copied unchanged)
  README.md
Then checks mechanically that no personal name, no institution of a person and no amount is left (counts only; names are never printed).
Usage: python -X utf8 v9_release.py <project>
"""
import sys, pathlib, shutil, hashlib, re, unicodedata, json
import pandas as pd
P = pathlib.Path(sys.argv[1]).resolve(); R = P / "rerun_fixed_20261117"; REL = P / "release_v9"
REL.mkdir(exist_ok=True)
for x in REL.iterdir():   # empty the folder (the folder itself may be in use as a working directory)
    shutil.rmtree(x) if x.is_dir() else x.unlink()
for d in ["data", "prompts", "code/pipeline", "code/analysis", "code/revised_data", "code/v9"]: (REL / d).mkdir(parents=True)
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
assert (U.below_thr <= _b).all() and (U[_b & ~U.below_thr].judge2 == "无法评价").all()   # unassessable is judged before the threshold rule
pend = {k: int(re.match(r"(\d{4})", str(G.loc[k, "disclosure_period_end"])).group(1)) for k in set(U.key)}
U["last_fiscal_year_excluded_in_S10"] = [(y == int(G.loc[k, "audit_year_last"])) and pend[k] <= 2023 for k, y in zip(U.key, U.year)]
U = U.sort_values(["key", "node", "year", "item", "ind"]).reset_index(drop=True)
amap = {n: f"A{i + 1:04d}" for i, n in enumerate(dict.fromkeys(U.nm))}
pmap = {n: f"Q{i + 1:05d}" for i, n in enumerate(dict.fromkeys(U.person.astype(str)))}
J = {"已申报": "declared", "未申报": "undeclared", "无法评价": "unassessable", "未达该指南的申报门槛": "below the guideline's threshold"}
SET = {"主分析集": "main analysis set", "期间推定层": "period-inferred layer"}
IND = {"pharma": "pharmaceutical", "device": "medical device"}
OUTU = pd.DataFrame({
    "guideline": U.key, "analysis_set": U.key.map(AS.analysis_set).map(SET), "author": U.nm.map(amap), "payment_person": U.person.astype(str).map(pmap),
    "company_id": U.ck, "company_node": U.node, "company_node_industry": U.prim.map(IND), "payment_data": U.ind.map(IND),
    "payment_category": U["item"].map({"講演料": "lecture fees", "原稿料": "manuscript fees"}), "fiscal_year": U.year,
    "amount_class": U.amount_class, "judgment_main": U.judge2.map(J), "judgment_frozen_pipeline": U.judge_frozen.map(J),
    "external_evaluation_committee": U.external, "last_fiscal_year_excluded_in_S10": U.last_fiscal_year_excluded_in_S10})
assert OUTU.notna().all().all(), OUTU.isna().sum()
OUTU.to_csv(REL / "data" / "units_v9.csv", index=False, encoding="utf-8")
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
GL["analysis_set"] = GL.analysis_set.map(SET); GL.index.name = "guideline"; GL.to_csv(REL / "data" / "guidelines_v9.csv", encoding="utf-8")
CM = rd(P / "config" / "company_master.csv")[["company_id", "canonical_name", "ind"]]
NODE = rd(P / "work" / "kg_build_v02" / "company_merge.csv")[["company_id", "node_id", "industry_primary"]]
CO = CM.merge(NODE, on="company_id", how="left"); CO = CO[CO.company_id.isin(set(U.ck))]
CO.rename(columns={"canonical_name": "company", "ind": "industry", "node_id": "company_node", "industry_primary": "company_node_industry"}).to_csv(REL / "data" / "companies_v9.csv", index=False, encoding="utf-8")
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
               "rerun_fixed_20261117/scripts/v9_release.py"]}
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
readme = f"""# Release set for manuscript v9 (not yet published)

Industry payments to clinical practice guideline committees and to the issuing societies in Japan: an audit of 25 medical societies, 2022 to 2025.

This folder holds the audit units behind the main estimate, the frozen prompts of the extraction pipeline and the analysis code. It holds no name of a person, no institution of a person and no payment amount. The payment data themselves are public: they are the payments that pharmaceutical and medical device companies disclose. For pharmaceutical personal payments in 2018, 2019, 2022 and 2023, the analysis used the revised version of the pharmaceutical payment database (製薬マネーデータベース) dated 17 November 2026 (S1 Text, section 1, lists the four files and their MD5 checksums).

## data/units_v9.csv ({len(OUTU):,} rows)

One row per audit unit: guideline × author × company node × payment category × fiscal year, for the 73 guidelines of the main analysis set (48) and the period-inferred layer (25).

| Column | Content |
|---|---|
| guideline | guideline key (data/guidelines_v9.csv) |
| analysis_set | main analysis set or period-inferred layer |
| author | committee member, replaced by a number (A0001 to A{n_auth:04d}); the same number for the same normalized name across guidelines |
| payment_person | the person in the payment data to whom the author was linked, replaced by a number (Q00001 to Q{n_pers:05d}); used for the deduplication by author × company × year |
| company_id, company_node | paying company and the merged company (data/companies_v9.csv) |
| company_node_industry | industry of the merged company (pharmaceutical or medical device); the industry used in the paper |
| payment_data | the data set in which the payment was disclosed |
| payment_category | lecture fees or manuscript fees |
| fiscal_year | Japanese fiscal year of the payment (April to March) |
| amount_class | the amount relative to the guideline's own declaration threshold for the category: below the guideline's threshold, at or above the threshold, at least twice the threshold. Every unit reached the audit threshold of JPY 500,000. |
| judgment_main | judgment of the main estimate (company-name corrections, item rule and threshold rule applied): declared, undeclared, unassessable, below the guideline's threshold |
| judgment_frozen_pipeline | judgment of the frozen pipeline before the corrections |
| external_evaluation_committee | the author was a member of the external evaluation committee of one society |
| last_fiscal_year_excluded_in_S10 | the unit lies in the last fiscal year of a declaration period that ended in 2023 or earlier (S10 Table) |

Check from this file alone (main analysis set, judgment_main declared or undeclared, deduplicated to payment_person × company_node × fiscal_year; a group is undeclared when all its units are undeclared):
pharmaceutical 730 of 3,479 undeclared (Table 4); at least twice the threshold 159 of 1,249; also outside the last fiscal year 116 of 942 (S10 Table);
medical device 87 of 331, 21 of 105 and 18 of 78.

## prompts/

The extraction prompt and the company-resolution prompt of pipeline v3.1, frozen on 11 October 2026. The sha256 of the frozen originals (as in the project's freeze record) are prompt_extraction_v3.md {ORIG_SHA.get('prompt_extraction_v3.md', sha(REL / 'prompts' / 'prompt_extraction_v3.md'))[:12]}… and prompt_company_resolve_v2.md {ORIG_SHA.get('prompt_company_resolve_v2.md', sha(REL / 'prompts' / 'prompt_company_resolve_v2.md'))[:12]}…. In these copies, and in {', '.join(x for x in REDACTED if not x.startswith('prompts'))}, the local user folder in file paths is replaced with &lt;user&gt;; nothing else differs from the files as run.

## code/

- pipeline/: building the payment tables (01), company keys (02), person keys (03, with its institution and specialty reference table), conversion of guideline documents to text (06) and the audit of pipeline v3.1 (04, frozen).
- analysis/: the analysis sets and their estimates (115), the paper tables and figures (113), the two channels (120, twochannel_comparison.py) and the pharmaceutical-device overlap (122).
- revised_data/: reading the revised 2018, 2019, 2022 and 2023 pharmaceutical files with the frozen 01 (mixload.py and its four settings).
- v9/: the AbbVie 2019 and Sun Pharma 2022 check (s3), the fiscal-year analysis of S10 Table (s4), the Table 2 recomputation (v9s0, v9t2) and this release script.

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
CH = pd.DataFrame(res); CH.to_csv(R / "v9_audit" / "release_checks.csv", index=False, encoding="utf-8-sig")
cols = list(OUTU.columns)
summary = dict(units=len(OUTU), authors=n_auth, payment_persons=n_pers, columns=cols, amount_columns=[c for c in cols if re.search("amt|amount_jpy|yen", c)],
               name_set=len(NAMESET), roster_names=len(names_roster), institution_set=len(insts), files=len(CH),
               files_with_name_hits=CH[CH.name_hits > 0].file.tolist(), files_with_roster_name_hits=CH[CH.roster_name_hits > 0].file.tolist(),
               files_with_institution_hits=CH[CH.institution_hits > 0].file.tolist(), csv_numbers_6plus=int(CH.numbers_6plus_digits_in_csv.fillna(0).sum()), repro=repro)
(R / "v9_audit" / "release_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
print(json.dumps({k: v for k, v in summary.items() if k != "columns"}, ensure_ascii=False, default=str))
print(CH.to_string(index=False))
