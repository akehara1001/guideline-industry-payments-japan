# -*- coding: utf-8 -*-
"""Stage 18, step A2: out/census_final_v5.md again (model extraction, not checked by people), built from 109_census_final_v5.py (stage 17) with:
  - the thresholds of work/stage18/guideline_thresholds.csv (114_derm_unclear.py): the 11 guidelines that take the Japanese Dermatological
    Association's rules are marked 「门槛不清（学会文件不一致）」 at 50 万 (a fourth threshold source; the numbers of the main set do not change);
  - B7 states how many guidelines have device units (figure S needs it);
  - a last section 「敏感性：日本皮膚科学会按细则的 100 万」: rule 2 again with the thresholds of census_sensitivity_root/config/
    guidelines_analysis_sets.csv (no extraction or audit is rerun: the units are the same, only rule 2 is judged again), side by side with 50 万.
Stage-17 description (109_census_final_v5.py): the results with the thresholds completed from the issuing societies' COI rules
-> out/census_final_v5.md. Built from 102_census_final_v4.py (stage 16) with these changes (CC_PROMPT_stage17.md, 步骤 B):
  - B1: the guideline-level thresholds of 108_society_thresholds.py (work/stage17/guideline_thresholds.csv) are written into
    config/guidelines_analysis_sets.csv (three threshold columns, the source, and the new columns threshold_source_class / threshold_society /
    threshold_document / threshold_version_use / threshold_in_guideline); rule 2 is recomputed with them;
  - the third column is renamed 「规则一、二之后」 (still not the official one); B2 per society, B5 and B6 get a column 门槛来源; B2 per society also gets
    the shares after rules 1 and 2; the units moved by rule 2 are shown next to stage 16's;
  - for the paper tables (step C) the file also gives: the per-person distributions of every column (B2, B3), B7 every guideline's undeclared
    share after rules 1 and 2 by industry, B8 the numbers of the flow chart, B9 the errata table.
Stage-16 description of v4 (out/census_final_v4.md): the results with the second rule of the analysis sets (model extraction, not checked by people).
Built from 98_census_final_v3.py (stage 15). Rule 2 (已定的事 1-3): a unit whose payment is below the guideline's own disclosure threshold for that item
(config/guidelines_analysis_sets.csv, 101_thresholds.py; 50 万 when not written or unclear) becomes 「未达该指南的申报门槛」 and leaves the evaluable
denominator; done outside the frozen pipeline, the frozen judgement kept. Changes from v3: the totals of B2 and B3 get a third column 「规则第二条之后」
(all guidelines) next to the two of stage 15; the per-society table of B2 and B5 get the two thresholds and the number of units moved; a new table B6
gives the guidelines of stage 15's list (high undeclared share without flag, and the flagged ones) before and after rule 2.
Stage-15 description of v3 (out/census_final_v3.md): Built from 90_census_final_v2.py with three changes only (CC_PROMPT_stage15.md, 步骤 C): B1 in seven forms; the totals of
B2 and B3 get a column without the flagged guidelines, next to the full numbers (which column is official is not decided in this round); the
per-society table of B2 and the per-guideline table B5 get a column with the flags. Flags from config/extraction_diagnostics.csv (96_extraction_diagnostics.py).
Usage: python 115_census_final_v5_stage18.py "<project>"
Reads  config/guidelines_analysis_sets.csv, config/guidelines_census2.csv, config/guidelines_census3.csv, config/guidelines_expansion_candidates.csv,
       config/guidelines_census.csv, work/expansion/society_rank.csv, work/errata/keys.csv, work/census3/report_numbers.pkl, work/stage14/{rerun_keys.csv,
       narrow_keys.csv}, kg/archive_v0_7 nodes (guideline, society), work/kg_build_v02/company_merge.csv, and per guideline roster_v3.csv,
       member_links.csv, units_v3.csv, metrics_v3.json of the runs: frozen (work/gl_v3_1, census3_root), errata (errata_root, errata2_root,
       census3_errata_root), stage 14 (stage14_root: errata third edition and the period re-set from the cell years), narrow window
       (census3_narrow_root, stage14_narrow_root)
Writes config/guidelines_analysis_sets.csv (threshold columns), out/census_final_v5.md, work/stage18/report_numbers.pkl (aggregate numbers only),
       work/stage18/units_rule2.pkl, census_sensitivity_root/work/units_rule2_sensitivity.pkl (units with names; work only)
Rules: units as before (member x company x item x year, payment >= 500,000 yen; merged company nodes; a same-name group's pharma / device copy of a unit
counted once; primary industry). Item rule of the analysis sets (已定的事 1): a unit whose item is not among the guideline's disclosure items is
无法评价, on top of the frozen judgement (both columns). 冻结流程原数 = the frozen pipeline's judgements with the analysis sets' period parameters (the two
brain-tumour guidelines with their cell years); 勘误后 = with the errata table (9 rows) applied outside the frozen pipeline = the official numbers.
The Japanese Circulation Society's external evaluators are in scope as the pipeline judged (official); the other count is shown as before.
"""
import pandas as pd, numpy as np, sys, pathlib, json, math, re, unicodedata, time

P = pathlib.Path(sys.argv[1]); KG = P/"kg"/"archive_v0_7"
rd = lambda p: pd.read_csv(p, dtype=str, keep_default_na=False, encoding="utf-8-sig")
AS0 = rd(P/"config"/"guidelines_analysis_sets.csv"); GT = rd(P/"work"/"stage18"/"guideline_thresholds.csv").set_index("key"); UNCLEAR = "门槛不清（学会文件不一致）"
SOCDOC = rd(P/"config"/"society_coi_thresholds.csv").set_index("doc")
if "threshold_source_class" not in AS0.columns:
    for c in ("threshold_source_class", "threshold_society", "threshold_document", "threshold_version_use", "threshold_in_guideline"): AS0[c] = ""
for i, r in AS0.iterrows():
    if r.key not in GT.index: continue
    g = GT.loc[r.key]
    AS0.loc[i, "threshold_in_guideline"] = "未写明" if "门槛未写明" in g.s16_flag else "写明"
    AS0.loc[i, "threshold_source_class"] = g.source_class; AS0.loc[i, "threshold_society"] = g.society
    AS0.loc[i, "threshold_document"] = g.doc; AS0.loc[i, "threshold_version_use"] = g.version_use
    AS0.loc[i, "lecture_threshold_man"] = f"{float(g.lecture):g}" if g.source_class != "写在指南里" else r.lecture_threshold_man
    AS0.loc[i, "manuscript_threshold_man"] = f"{float(g.manuscript):g}" if g.source_class != "写在指南里" else r.manuscript_threshold_man
    if g.source_class == "取自发行学会的规定":
        AS0.loc[i, "threshold_unit"] = g.unit; AS0.loc[i, "threshold_source"] = g.source
        AS0.loc[i, "threshold_location"] = f"data_raw/society_coi_policies/{g.society_key}/{SOCDOC.loc[g.doc, 'file']}"
        AS0.loc[i, "threshold_flag"] = "学会规定用现行版本" if g.version_use.startswith("现行版本") else ""
    elif g.source_class == UNCLEAR:
        AS0.loc[i, "threshold_unit"] = g.unit; AS0.loc[i, "threshold_source"] = g.source; AS0.loc[i, "threshold_flag"] = UNCLEAR
        AS0.loc[i, "threshold_location"] = "；".join(f"data_raw/society_coi_policies/{g.society_key}/{SOCDOC.loc[d, 'file']}" for d in g.doc.split("|"))
AS0.to_csv(P/"config"/"guidelines_analysis_sets.csv", index=False, encoding="utf-8-sig")
AS = AS0.set_index("key")
C2 = rd(P/"config"/"guidelines_census2.csv"); C3 = rd(P/"config"/"guidelines_census3.csv").set_index("key")
CAND = rd(P/"config"/"guidelines_expansion_candidates.csv"); RANK = rd(P/"work"/"expansion"/"society_rank.csv")
CEN = rd(P/"config"/"guidelines_census.csv"); JCS = set(CEN[CEN.group == "循環器学会全数"].key)
RN = pd.read_pickle(P/"work"/"census3"/"report_numbers.pkl"); KEYS = RN["KEYS"]; NEW13 = set(RN["new13"]); ISS = RN["ISS"]
RR = rd(P/"work"/"stage14"/"rerun_keys.csv").set_index("key"); NK = set(rd(P/"work"/"stage14"/"narrow_keys.csv").key)
GN = pd.read_parquet(KG/"nodes"/"guideline.parquet").set_index("guideline_id")
SOC = pd.read_parquet(KG/"nodes"/"society.parquet").set_index("society_id"); SNAME = SOC.name
cmg = rd(P/"work"/"kg_build_v02"/"company_merge.csv").set_index("company_id"); prim_of = cmg.drop_duplicates("node_id").set_index("node_id").industry_primary
E1KEYS = set(rd(P/"work"/"errata"/"keys.csv").key); E2KEYS = {"liver_2021", "jds_dm_2024"}
E3KEYS = set(rd(P/"census3_errata_root"/"config"/"guidelines_v3_1.csv").key)
LAB = {"pharma": "制药", "device": "器械"}; CLS = ["已申报", "未申报", "无法评价"]; ITEM = {"講演料": "lecture_item", "原稿料": "manuscript_item"}
MAIN = [k for k in KEYS if AS.loc[k, "analysis_set"] == "主分析集"]; INF = [k for k in KEYS if AS.loc[k, "analysis_set"] == "期间推定层"]
SCOPE = [k for k in KEYS if AS.loc[k, "in_scope"] == "是"]; NOITEM = [k for k in SCOPE if AS.loc[k, "analysis_set"].startswith("口径集")]
DG = rd(P/"config"/"extraction_diagnostics.csv").set_index("key"); FLAG = {k: DG.loc[k, "flag"] for k in DG.index if DG.loc[k, "flag"]}
THR = {k: {"講演料": float(AS.loc[k, "lecture_threshold_man"]) * 10000, "原稿料": float(AS.loc[k, "manuscript_threshold_man"]) * 10000}
       for k in AS.index if AS.loc[k, "lecture_threshold_man"] != ""}
BELOW = "未达该指南的申报门槛"; R12 = "规则一、二之后"
SRC_SHORT = {"写在指南里": "", "取自发行学会的规定": "（学会规定）", "未写明": "（未写明）", UNCLEAR: "（门槛不清）"}
def src_cell(k):
    c = AS.loc[k, "threshold_source_class"] if "threshold_source_class" in AS.columns else ""
    return {"写在指南里": "写在指南里", "取自发行学会的规定": f"学会规定（{AS.loc[k, 'threshold_society']}）", "未写明": "未写明",
            UNCLEAR: f"门槛不清（{AS.loc[k, 'threshold_society']}的文件不一致）"}.get(c, "—")


def wilson(k, n, z=1.959963984540054):
    p = k / n; d = 1 + z * z / n; c = (p + z * z / (2 * n)) / d; h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return p, max(0.0, c - h), min(1.0, c + h)
fmt = lambda k, n: (lambda p, lo, hi: f"{p:.2f}，95% CI [{lo:.2f}, {hi:.2f}]（{k:,}/{n:,}）")(*wilson(k, n)) if n else "—（0）"


def vdir(k, ver):
    if ver == "narrow": return P/("stage14_narrow_root" if k in NK else "census3_narrow_root")/"work"/"gl_v3_1"/k
    if k in RR.index and (ver == "all" or "期间" in RR.loc[k, "why"]): return P/"stage14_root"/"work"/"gl_v3_1"/k
    if k in NEW13: return P/("census3_errata_root" if (ver == "all" and k in E3KEYS) else "census3_root")/"work"/"gl_v3_1"/k
    if ver == "all" and k in E2KEYS: return P/"errata2_root"/"work"/"gl_v3_1"/k
    if ver == "all" and k in E1KEYS: return P/"errata_root"/"work"/"gl_v3_1"/k
    return P/"work"/"gl_v3_1"/k


def load(k, ver):
    d = vdir(k, ver)
    RV = rd(d/"roster_v3.csv"); LK = rd(d/"member_links.csv"); U = rd(d/"units_v3.csv"); M = json.loads((d/"metrics_v3.json").read_text(encoding="utf-8"))
    RV["evaluable"] = (RV.in_scope == "是") | ((RV.in_scope == "不明") & (RV.listed == "True"))
    ext = RV.set_index("nm").roles.str.contains("外部評価")
    pid = {(r.nm, r.ind): str(int(float(r.person_id))) for r in LK.itertuples() if r.person_id}
    U["node"] = U.ck.map(cmg.node_id).fillna(U.ck); U["prim"] = U.node.map(prim_of).fillna(U.ind); U["year"] = U.year.astype(int)
    U = U.sort_values("ind", key=lambda s: s.map({"pharma": 0, "device": 1}), kind="stable").drop_duplicates(["nm", "node", "item", "year"])
    U["person"] = [pid.get((n, i), "") for n, i in zip(U.nm, U.ind)]
    U["external"] = U.nm.map(ext).fillna(False).astype(bool) & (k in JCS); U["key"] = k
    U["judge_frozen"] = U.judge
    off = pd.Series([bool(AS.loc[k, ITEM[it]] == "否") if it in ITEM else False for it in U["item"]], index=U.index, dtype=bool)   # explicit bool (empty frames keep str dtype with .map)
    U.loc[off, "judge"] = "无法评价"; U["item_rule"] = off
    U["amt"] = pd.to_numeric(U.amt_pay, errors="coerce")
    below = pd.Series([bool(k in THR and it in THR[k] and a < THR[k][it]) for it, a in zip(U["item"], U["amt"])], index=U.index, dtype=bool) & U.judge.isin(["已申报", "未申报"])
    U["judge2"] = U.judge.where(~below, BELOW); U["below_thr"] = below
    ident = {n: (pid.get((n, "pharma")) or pid.get((n, "device")) or "R:" + n) for n in RV.nm}
    return dict(RV=RV, U=U, M=M, linked={n for (n, i) in pid}, ident=ident)


D = {v: {k: load(k, v) for k in KEYS} for v in ("orig", "all")}
D["narrow"] = {k: load(k, "narrow") for k in INF}


def undecl(U, ind, drop_ext):
    x = U[(U.prim == ind) & U.judge.isin(["已申报", "未申报"])]
    if drop_ext: x = x[~x.external]
    return int((x.judge == "未申报").sum()), len(x)


def dedup(U, ind, drop_ext):
    x = U[(U.prim == ind) & U.judge.isin(["已申报", "未申报"]) & (U.person != "")]
    if drop_ext: x = x[~x.external]
    g = x.groupby(["person", "node", "year"]).judge.agg(lambda s: "未申报" if set(s) == {"未申报"} else ("已申报" if set(s) == {"已申报"} else "各部不一"))
    return int((g == "未申报").sum()), len(g), int((g == "已申报").sum()), int((g == "各部不一").sum())


def per_person(U, ind, drop_ext):
    x = U[(U.prim == ind) & U.judge.isin(["已申报", "未申报"]) & (U.person != "")]
    if drop_ext: x = x[~x.external]
    und = x[x.judge == "未申报"].drop_duplicates(["person", "node", "year", "item"]).groupby("person").size()
    persons = sorted(set(x.person)); cnt = pd.Series(0, index=persons).add(und, fill_value=0).astype(int)
    return int((cnt >= 1).sum()), len(persons), {"0": int((cnt == 0).sum()), "1": int((cnt == 1).sum()), "2–4": int(cnt.between(2, 4).sum()), "5 以上": int((cnt >= 5).sum())}


cat = lambda keys, ver="all": pd.concat([D[ver][k]["U"] for k in keys], ignore_index=True)
NUM = {}
TITLE = {k: AS.loc[k, "title"] for k in KEYS}
L = ["# 审计结果定版：分析集，第 18 阶段版（模型抽取，未经人工核对）", "",
     f"生成脚本：`scripts/86_errata3_setup.py`–`scripts/90_census_final_v2.py`、`scripts/96_extraction_diagnostics.py`、`scripts/98_census_final_v3.py`、`scripts/101_thresholds.py`、`scripts/102_census_final_v4.py`、`scripts/105_society_assign.py`–`scripts/108_society_thresholds.py`、`scripts/109_census_final_v5.py`、`scripts/114_derm_unclear.py`、`scripts/115_census_final_v5_stage18.py`。生成日期：{time.strftime('%Y-%m-%d')}。**本文件的审计数字都来自模型抽取，未经人工核对**"
     "（开发集五部之外没有人工参照）。只含汇总数；是描述，不做检验，不下结论。比例都附 Wilson 95% CI。", "",
     "单元 = 委员 × 企业 × 项目（讲演费、稿费）× 年，付款过 50 万日元（冻结流程的门槛）；企业按合并后的节点，同名组在两张表里的同一单元只算一次，行业按主行业。"
     "付款数据：制药 2016–2023 年，器械 2019–2023 年。", "",
     "分析集（第 14 阶段已定的事 6；逐部见 B5 和 `config/guidelines_analysis_sets.csv`）：", "",
     f"- 口径集：25 个学会、标题年份 2022–2025 年、已审计的指南，{len(SCOPE)} 部。",
     f"- 主分析集：口径集里期间写明（含写明出自单元格）、开示项目含讲演费或稿费的指南，{len(MAIN)} 部。论文的正式数出自这里。",
     f"- 期间推定层：口径集里期间推定、开示项目含讲演费或稿费的指南，{len(INF)} 部，只作分层结果。",
     f"- 口径集里开示项目既不含讲演费也不含稿费的 {len(NOITEM)} 部，不进未申报比例，单独计数（B1）。",
     "- 口径以外的 3 部（`esophagus_2022`、`liver_2021`、`pancreas_2022`）不进审计结果。", "",
     "分析集的规则（在冻结流程之外，冻结流程的原判定保留）：一个单元的项目不在这部指南的开示项目里，这个单元记「无法评价」。"
     "「冻结流程原数」= 冻结流程的判定（两部脑肿瘤指南用单元格里的年份作期间）；「勘误后」= 勘误表 9 行在冻结流程之外采用后的判定，为正式数。"
     "日本循環器学会的外部評価委員：按流程的判定算在范围内，另列不算在范围内的数。", "",
     f"抽取诊断的标记（`out/extraction_diagnostics.md`；只按抽取指标，不看未申报比例）：有标记的指南 {len(FLAG)} 部（" + "、".join(f"`{k}` {v}" for k, v in FLAG.items()) + "）。"
     "分析集规则第二条（第 16 阶段）：单元的付款金额低于这部指南对这个项目的申报门槛，记「未达该指南的申报门槛」，不进可评价的分母。"
     "门槛的来源（第 17、18 阶段）：写在指南里的按指南（`out/thresholds.md`）；指南没写的取自发行学会的利益相反规定（`out/society_thresholds.md`）；两处都没有的按 50 万日元并标「未写明」；"
     f"学会的文件之间金额不一致的按 50 万日元并标「{UNCLEAR}」（第 18 阶段；按另一份文件的金额算的敏感性在本文件最后一节）。"
     f"本版：写在指南里 {int((AS.threshold_source_class == '写在指南里').sum())} 部、取自发行学会的规定 {int((AS.threshold_source_class == '取自发行学会的规定').sum())} 部、"
     f"{UNCLEAR} {int((AS.threshold_source_class == UNCLEAR).sum())} 部、未写明 {int((AS.threshold_source_class == '未写明').sum())} 部。"
     f"B2、B3 的合计表并列「勘误后（全部指南）」「勘误后，去掉有标记的指南」「{R12}（全部指南）」三列；**哪一列作正式数，这一轮仍不定，等人工核对的结果。**", ""]

# ---------------------------------------------------------------- B1
X1 = CAND[(CAND.supplement != "True") & ~CAND.title.str.contains("麻酔薬および麻酔関連薬")].copy()
X1 = X1.merge(C2[["society_id", "title", "title_year", "key", "include"]], on=["society_id", "title", "title_year"], how="left")
X1["gkey"] = np.where(X1.audited_key != "", X1.audited_key, np.where(X1.include == "是", X1.key, ""))
gk = X1[X1.gkey != ""].groupby("guideline_group").gkey.agg(lambda s: sorted(set(s)))
assert all(len(v) == 1 for v in gk), "a guideline group maps to two keys"
X1["gkey"] = X1.guideline_group.map(lambda g: gk[g][0] if g in gk.index else "")
FORMS6 = ["按个人分项目（可审计）", "按个人但不分项目", "按个人但开示项目不含讲演费和稿费", "只有总括声明", "没有", "按个人列出企业名但全文取不到", "取不到"]
def form6(r):
    k = r.gkey
    if k in SCOPE: return FORMS6[2] if k in NOITEM else FORMS6[0]
    if k in C3.index and C3.loc[k, "layout"] == "乙": return FORMS6[1]
    if k in C3.index and C3.loc[k, "status"] == "取不到": return FORMS6[6]
    if r.coi_form in ("只有总括声明", "没有", "取不到"): return r.coi_form
    if r.coi_form == "按个人只写有无": return FORMS6[1]
    return FORMS6[5]                                                   # per person with company names, but the full text was not obtainable: not audited
X1["form6"] = X1.apply(form6, axis=1)
X1["fulltext_missing"] = X1.form6 == FORMS6[5]
L += ["## B1. 公开形式的全貌（25 个学会，标题年份 2022–2025 年的诊疗指南）", "",
      "口径同第 12 阶段（合办只算写明共同编集或发行的学会；「監修」算发行学会；药品使用指南、追補等不单独算）；同一部指南在合办的几个学会下各算一次，最后一行去掉重复。"
      "「按个人分项目（可审计）」= 已用冻结流程审计、开示项目含讲演费或稿费的；「按个人但不分项目」= 第 13 阶段判为版式乙的；"
      "「按个人但开示项目不含讲演费和稿费」= 已审计、但开示项目里两项都没有的；「按个人列出企业名但全文取不到」= 清点时公开形式为按个人列出企业名、但全文取不到而没有审计的；"
      "「取不到」= 公开形式不明的（含第 13 阶段改记的 Minds 阅读器 2 部）。", "",
      "| 学会 | 指南数 | " + " | ".join(FORMS6) + " |", "|---|---|" + "---|" * len(FORMS6)]
B1 = {}
for r in RANK.itertuples():
    d = X1[X1.society_id == r.society_id]; fc = d.form6.value_counts()
    B1[r.society_id] = dict(name=r.name, total=len(d), forms={f: int(fc.get(f, 0)) for f in FORMS6})
    L += [f"| {r.name} | {len(d)} | " + " | ".join(str(int(fc.get(f, 0))) for f in FORMS6) + " |"]
U1 = X1.drop_duplicates("guideline_group"); fc = U1.form6.value_counts()
L += [f"| **合计（去重）** | {len(U1)} | " + " | ".join(str(int(fc.get(f, 0))) for f in FORMS6) + " |", ""]
nft = int(U1.fulltext_missing.sum())
L += [f"「按个人分项目（可审计）」{int(fc.get(FORMS6[0], 0))} 部 = 主分析集 {len(MAIN)} 部 + 期间推定层 {len(INF)} 部（其中有抽取诊断标记的 {len(FLAG)} 部）。", ""]
NUM["B1"] = dict(total=len(U1), forms={f: int(fc.get(f, 0)) for f in FORMS6}, fulltext_missing=nft, societies=B1)
SRCS = ("写在指南里", "取自发行学会的规定", "未写明", UNCLEAR)
def b1b(d):
    au = d[d.form6.isin([FORMS6[0], FORMS6[2]])]; it = d[d.form6 == FORMS6[0]]
    sc = [int((it.gkey.map(lambda k: AS.loc[k, "threshold_source_class"]) == c).sum()) for c in SRCS]
    return dict(total=len(d), audited=len(au), items=len(it), src=sc)
L += ["## B1b. 每个学会：已审计的指南和申报门槛的来源", "",
      "口径同 B1（合办的在各学会下各算一次，最后一行去掉重复）。「已审计」= B1 的「按个人分项目（可审计）」加「按个人但开示项目不含讲演费和稿费」（口径集）；"
      "门槛来源只对开示项目含讲演费或稿费的指南（主分析集和期间推定层）。", "",
      f"| 学会 | 指南数 | 已审计 | 其中开示项目含讲演费或稿费 | 门槛写在指南里 | 门槛取自发行学会的规定 | 门槛未写明 | {UNCLEAR} |", "|---|---|---|---|---|---|---|---|"]
B1B = {}
for r in RANK.itertuples():
    v = b1b(X1[X1.society_id == r.society_id]); B1B[r.society_id] = dict(name=r.name, **v)
    L += [f"| {r.name} | {v['total']} | {v['audited']} | {v['items']} | " + " | ".join(str(x) for x in v["src"]) + " |"]
v = b1b(U1); B1B["total"] = dict(name="合计（去重）", **v)
L += [f"| **合计（去重）** | {v['total']} | {v['audited']} | {v['items']} | " + " | ".join(str(x) for x in v["src"]) + " |", ""]
NUM["B1b"] = B1B


# ---------------------------------------------------------------- B2-B4 helpers
def totals(keys, sec, ver_pairs=True):
    out = {}
    Uo, Ua = cat(keys, "orig"), cat(keys, "all"); kx = [k for k in keys if k not in FLAG]; Ux = cat(kx, "all"); U2 = Ua.assign(judge=Ua.judge2)
    for kind, f in (("raw", undecl), ("dedup", dedup)):
        for ind in ("pharma", "device"):
            for ex in (False, True):
                out[(kind, ind, ex)] = (f(Uo, ind, ex), f(Ua, ind, ex), f(Ux, ind, ex), f(U2, ind, ex))
    for ind in ("pharma", "device"):
        for ex in (False, True):
            out[("person", ind, ex)] = (per_person(Uo, ind, ex), per_person(Ua, ind, ex), per_person(Ux, ind, ex), per_person(U2, ind, ex))
    out["n_excl"] = (len(keys), len(kx))
    return out


def total_tables(T, title_note, pre):
    M = []
    for kind, lab in (("raw", "去重前"), ("dedup", "按 人 × 企业 × 年 去重后")):
        M += [f"#### {pre} 未申报比例（{lab}）", "", f"| 行业 | 日本循環器学会的外部評価委員 | 冻结流程原数 | 勘误后（全部指南，{T['n_excl'][0]} 部） | 勘误后，去掉有标记的指南（{T['n_excl'][1]} 部） | {R12}（全部指南） |", "|---|---|---|---|---|---|"]
        for ind in ("pharma", "device"):
            for ex in (False, True):
                a, b, c, d = T[(kind, ind, ex)]
                M += [f"| {LAB[ind]} | {'不算在范围内' if ex else '算在范围内'} | {fmt(a[0], a[1])} | {fmt(b[0], b[1])} | {fmt(c[0], c[1])} | {fmt(d[0], d[1])} |"]
        M += [""]
    M += [f"#### {pre} 按人：至少有一个未申报单元的人", "", f"对象：{title_note}开示范围内、连上付款表、在该行业至少有一个可评价单元的委员；同一人在几部指南里只算一次。", "",
          f"| 行业 | 日本循環器学会的外部評価委員 | 勘误后（全部指南） | 每人未申报单元数 0 / 1 / 2–4 / 5 以上（勘误后，全部指南） | 勘误后，去掉有标记的指南 | 冻结流程原数 | {R12}（全部指南） |", "|---|---|---|---|---|---|---|"]
    for ind in ("pharma", "device"):
        for ex in (False, True):
            a, b, c, d = T[("person", ind, ex)]
            M += [f"| {LAB[ind]} | {'不算在范围内' if ex else '算在范围内'} | {fmt(b[0], b[1])} | {' / '.join(str(v) for v in b[2].values())} | {fmt(c[0], c[1])} | {fmt(a[0], a[1])} | {fmt(d[0], d[1])} |"]
    M += ["", f"#### {pre} 每人未申报单元数的分布（各列）", "", "人数；对象同上表（各列的分母是该列「至少有一个未申报单元的人」的分母）。", "",
          "| 行业 | 日本循環器学会的外部評価委員 | 列 | 人数 | 0 | 1 | 2–4 | 5 以上 |", "|---|---|---|---|---|---|---|---|"]
    for ind in ("pharma", "device"):
        for ex in (False, True):
            a, b, c, d = T[("person", ind, ex)]
            for lab_, x in (("冻结流程原数", a), ("勘误后（全部指南）", b), ("勘误后，去掉有标记的指南", c), (f"{R12}（全部指南）", d)):
                M += [f"| {LAB[ind]} | {'不算在范围内' if ex else '算在范围内'} | {lab_} | {x[1]:,} | " + " | ".join(f"{v:,}" for v in x[2].values()) + " |"]
    return M + [""]


def thr_summary(ks, item):
    c = {}
    for k in ks:
        lab = f"{float(AS.loc[k, f'{item}_threshold_man']):g}" + SRC_SHORT.get(AS.loc[k, "threshold_source_class"], "")
        c[lab] = c.get(lab, 0) + 1
    return "、".join(f"{a}：{b}" for a, b in sorted(c.items()))


# ---------------------------------------------------------------- B2 main analysis set
T2 = totals(MAIN, "B2"); NUM["B2"] = T2
L += [f"## B2. 主分析集（{len(MAIN)} 部）", "", "### B2 合计", ""] + total_tables(T2, "主分析集的指南里", "B2")
L += ["### B2 每个学会", "", "一部合办的指南算进每个发行学会。人数按付款表的个人键认（连不上付款表的按规范化姓名）。比例为勘误后、外部評価委員算在范围内。", "",
      f"| 学会 | 指南数 | 委员人次 | 委员人数 | 可评价单元 制药 / 器械 | 未申报比例 制药（去重后） | 未申报比例 器械（去重后） | 至少一个未申报单元的人 制药 | 至少一个未申报单元的人 器械 | 有标记的指南 | 讲演费门槛（万日元：部数） | 稿费门槛（万日元：部数） | 规则第二条改记的单元 | 门槛来源（部数） | 未申报比例 制药（去重后，{R12}） | 未申报比例 器械（去重后，{R12}） | 至少一个未申报单元的人 制药（{R12}） | 至少一个未申报单元的人 器械（{R12}） |",
      "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
S2 = {}
socs = list(RANK.society_id) + sorted({s for k in MAIN for s in ISS[k]} - set(RANK.society_id))
for sid in socs:
    ks = sorted({k for k in MAIN if sid in ISS[k]})
    if not ks: continue
    U = cat(ks); times = sum(len(D["all"][k]["RV"]) for k in ks); ppl = len({D["all"][k]["ident"][n] for k in ks for n in D["all"][k]["RV"].nm})
    ev = [undecl(U, ind, False)[1] for ind in ("pharma", "device")]
    dd = {ind: dedup(U, ind, False) for ind in ("pharma", "device")}; pp = {ind: per_person(U, ind, False) for ind in ("pharma", "device")}
    U2_ = U.assign(judge=U.judge2); dd2 = {ind: dedup(U2_, ind, False) for ind in ("pharma", "device")}; pp2 = {ind: per_person(U2_, ind, False) for ind in ("pharma", "device")}
    srcc = pd.Series([AS.loc[k, "threshold_source_class"] for k in ks]).value_counts()
    src_txt = "、".join(f"{c}：{int(srcc[c])}" for c in ("写在指南里", "取自发行学会的规定", UNCLEAR, "未写明") if c in srcc.index)
    S2[sid] = dict(name=SNAME.get(sid, sid), guidelines=len(ks), times=times, persons=ppl, ev=ev, dd=dd, pp=pp, dd2=dd2, pp2=pp2, src=src_txt)
    L += [f"| {SNAME.get(sid, sid)} | {len(ks)} | {times:,} | {ppl:,} | {ev[0]:,} / {ev[1]:,} | {fmt(dd['pharma'][0], dd['pharma'][1])} | {fmt(dd['device'][0], dd['device'][1])} | "
          f"{fmt(pp['pharma'][0], pp['pharma'][1])} | {fmt(pp['device'][0], pp['device'][1])} | {'、'.join(f'`{k}` {FLAG[k]}' for k in ks if k in FLAG) or '—'} | "
          f"{thr_summary(ks, 'lecture')} | {thr_summary(ks, 'manuscript')} | {int(U.below_thr.sum())} | {src_txt} | {fmt(dd2['pharma'][0], dd2['pharma'][1])} | {fmt(dd2['device'][0], dd2['device'][1])} | "
          f"{fmt(pp2['pharma'][0], pp2['pharma'][1])} | {fmt(pp2['device'][0], pp2['device'][1])} |"]
    S2[sid]["flagged"] = [k for k in ks if k in FLAG]
L += [""]; NUM["B2_soc"] = S2

# ---------------------------------------------------------------- B3 period-inferred layer
T3 = totals(INF, "B3"); NUM["B3"] = T3
Un = cat(INF, "narrow")
NUM["B3_narrow"] = {("dedup", ind): dedup(Un, ind, False) for ind in ("pharma", "device")} | {("raw", ind): undecl(Un, ind, False) for ind in ("pharma", "device")} | \
                   {("person", ind): per_person(Un, ind, False) for ind in ("pharma", "device")}
L += [f"## B3. 期间推定层（{len(INF)} 部；分层结果）", "", "### B3 合计（推定的 3 年窗口）", ""] + total_tables(T3, "期间推定层的指南里", "B3")
NB = NUM["B3_narrow"]
L += ["### B3 窄窗口（推定的 3 年里只用中间一年；勘误后；外部評価委員算在范围内）", "",
      "期间推定层的指南把期间设为中间一年重跑冻结审计（`census3_narrow_root`；勘误第三版涉及的 2 部在 `stage14_narrow_root`），分析集的项目规则照用。", "",
      "| 行 | 未申报比例 制药（去重前） | 未申报比例 器械（去重前） | 未申报比例 制药（去重后） | 未申报比例 器械（去重后） | 至少一个未申报单元的人 制药 | 至少一个未申报单元的人 器械 |", "|---|---|---|---|---|---|---|",
      f"| 窄窗口 | {fmt(*NB[('raw', 'pharma')])} | {fmt(*NB[('raw', 'device')])} | {fmt(*NB[('dedup', 'pharma')][:2])} | {fmt(*NB[('dedup', 'device')][:2])} | "
      f"{fmt(*NB[('person', 'pharma')][:2])} | {fmt(*NB[('person', 'device')][:2])} |", ""]

# ---------------------------------------------------------------- B4 scope set (reference)
T4 = totals(SCOPE, "B4"); NUM["B4"] = T4
L += [f"## B4. 口径集合计（{len(SCOPE)} 部；对照）", "",
      f"口径集全部指南（主分析集 {len(MAIN)}、期间推定层 {len(INF)}、开示项目不含讲演费和稿费 {len(NOITEM)}；后者的单元按规则全部无法评价）。勘误后，外部評価委員算在范围内。", "",
      "| 行 | 未申报比例 制药（去重前） | 未申报比例 器械（去重前） | 未申报比例 制药（去重后） | 未申报比例 器械（去重后） | 至少一个未申报单元的人 制药 | 至少一个未申报单元的人 器械 |", "|---|---|---|---|---|---|---|",
      f"| 口径集合计 | {fmt(*T4[('raw', 'pharma', False)][1])} | {fmt(*T4[('raw', 'device', False)][1])} | {fmt(*T4[('dedup', 'pharma', False)][1][:2])} | "
      f"{fmt(*T4[('dedup', 'device', False)][1][:2])} | {fmt(*T4[('person', 'pharma', False)][1][:2])} | {fmt(*T4[('person', 'device', False)][1][:2])} |", ""]
for lab, T in (("主分析集", T2), ("期间推定层", T3)):
    L[-1:-1] = [f"| {lab}（同上，作对照） | {fmt(*T[('raw', 'pharma', False)][1])} | {fmt(*T[('raw', 'device', False)][1])} | {fmt(*T[('dedup', 'pharma', False)][1][:2])} | "
                f"{fmt(*T[('dedup', 'device', False)][1][:2])} | {fmt(*T[('person', 'pharma', False)][1][:2])} | {fmt(*T[('person', 'device', False)][1][:2])} |"]

# ---------------------------------------------------------------- B5 per guideline
L += ["## B5. 每部指南（勘误后的判定，分析集规则已用；模型抽取，未经人工核对）", "",
      "「项目外」= 项目不在这部指南的开示项目里、按规则改记无法评价的单元数（已含在无法评价里）。审计年份为冻结审计用的期间。", "",
      "| 指南 | 分析集 | 发行学会 | 年 | 期间 | 开示项目 讲演费 / 稿费 | 委员（名单） | 开示范围内 | 连上付款表 | 审计年份 | 单元 制药 / 器械 | 制药：已申报 / 未申报 / 无法评价 | 器械：已申报 / 未申报 / 无法评价 | 项目外 | 抽取诊断的标记 | 讲演费门槛（万日元） | 稿费门槛（万日元） | 规则第二条改记的单元 | 门槛来源 |",
      "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
B5 = []
thr_cell = lambda k, item: f"{float(AS.loc[k, f'{item}_threshold_man']):g}" + SRC_SHORT.get(AS.loc[k, "threshold_source_class"], "")
order = MAIN + INF + NOITEM + [k for k in KEYS if k not in SCOPE]
for k in order:
    d = D["all"][k]; RV, U = d["RV"], d["U"]; yrs = d["M"]["years"]
    jc = lambda ind: U[U.prim == ind].judge.value_counts().reindex(CLS, fill_value=0)
    part = any(y > 2023 for y in yrs); ys = f"{yrs[0]}–{yrs[-1]}" + ("（2024 年以后没有付款数据）" if part else "")
    a = AS.loc[k]
    B5.append(dict(key=k, set=a.analysis_set, up=int((U.prim == "pharma").sum()), ud=int((U.prim == "device").sum()), item_rule=int(U.item_rule.sum())))
    L += [f"| {TITLE[k]}（`{k}`） | {a.analysis_set} | {'、'.join(SNAME.get(s, s) for s in ISS[k])} | {a.title_year} | {a.period_class} | {a.lecture_item} / {a.manuscript_item} | "
          f"{len(RV)} | {int(RV.evaluable.sum())} | {len(d['linked'] & set(RV.nm))} | {ys} | {int((U.prim == 'pharma').sum())} / {int((U.prim == 'device').sum())} | "
          + " / ".join(str(int(jc("pharma")[c])) for c in CLS) + " | " + " / ".join(str(int(jc("device")[c])) for c in CLS) + f" | {int(U.item_rule.sum())} | {FLAG.get(k, '—' if k in DG.index else '（不在诊断范围）')} | "
          + (f"{thr_cell(k, 'lecture')} | {thr_cell(k, 'manuscript')} | {int(U.below_thr.sum())} | {src_cell(k)} |" if k in THR else "— | — | — | — |")]
L += [""]
# ---------------------------------------------------------------- rule 2: units moved, B6
MV = []
for k in MAIN + INF:
    U = D["all"][k]["U"]; b = U[U.below_thr]
    MV.append(dict(key=k, set=AS.loc[k, "analysis_set"], moved=len(b), was_undeclared=int((b.judge == "未申报").sum()), was_declared=int((b.judge == "已申报").sum()),
                   lecture=thr_cell(k, "lecture"), manuscript=thr_cell(k, "manuscript")))
MV = pd.DataFrame(MV); MV16 = pd.DataFrame(pd.read_pickle(P/"work"/"stage16"/"report_numbers.pkl")["NUM"]["moved"]).set_index("key")
MV["moved16"] = MV.key.map(MV16.moved).fillna(0).astype(int); MV["source"] = [src_cell(k) for k in MV.key]
mvk = MV[(MV.moved > 0) | (MV.moved16 > 0)]
L += ["## 规则第二条改记的单元（主分析集和期间推定层）", "",
      f"改记「{BELOW}」的单元共 {int(MV.moved.sum())} 个，在 {len(mvk)} 部指南里；原判未申报 {int(MV.was_undeclared.sum())} 个、已申报 {int(MV.was_declared.sum())} 个（勘误后、项目规则之后的判定；去重前）。", "",
      f"与第 16 阶段（`out/archive_stage16/census_final_v4.md`）相比，改记的单元数不同的指南 {int((MV.moved != MV.moved16).sum())} 部；第 16 阶段共 {int(MV.moved16.sum())} 个。", "",
      "| 指南 | 分析集 | 讲演费门槛（万日元） | 稿费门槛（万日元） | 门槛来源 | 改记的单元（第 16 阶段） | 改记的单元（本版） | 原判未申报 | 原判已申报 |", "|---|---|---|---|---|---|---|---|---|"]
L += [f"| `{r.key}` | {r.set} | {r.lecture} | {r.manuscript} | {r.source} | {r.moved16} | {r.moved} | {r.was_undeclared} | {r.was_declared} |" for r in mvk.itertuples()] + [""]
def gshare(U, j):
    x = U[U[j].isin(["已申报", "未申报"]) & (U.person != "")]
    g = x.groupby(["person", "node", "year"])[j].agg(lambda s: "未申报" if set(s) == {"未申报"} else "其他") if len(x) else pd.Series(dtype=str)
    return int((g == "未申报").sum()), len(g)
LIST = list(DG[(DG["flag"] != "") | (DG.high_unflagged == "True")].index)
L += ["## B6. 规则第二条之前后：第 15 阶段「未申报比例 0.50 以上而没有标记」的指南和有标记的指南", "",
      "每部指南内按 人 × 企业 × 年 去重，制药和器械合计（同 `out/extraction_diagnostics.md` 的算法）；勘误后。", "",
      f"| 指南 | 组 | 讲演费门槛（万日元） | 稿费门槛（万日元） | 规则第二条之前 | 规则第二条之后（{R12}） | 改记的单元 | 门槛来源 |", "|---|---|---|---|---|---|---|---|"]
B6 = {}
for k in LIST:
    U = D["all"][k]["U"]; a = gshare(U, "judge"); b = gshare(U, "judge2"); B6[k] = (a, b, int(U.below_thr.sum()))
    L += [f"| `{k}` | {'有标记（' + FLAG[k] + '）' if k in FLAG else '未申报比例高而没有标记'} | {thr_cell(k, 'lecture')} | {thr_cell(k, 'manuscript')} | {fmt(*a)} | {fmt(*b)} | {int(U.below_thr.sum())} | {src_cell(k)} |"]
L += [""]
# ---------------------------------------------------------------- B7 every guideline after rules 1 and 2, by industry (forest plot, supplement)
def prim_soc(k):
    if "S022" in ISS[k]: return "S022"
    if len(ISS[k]) == 1: return ISS[k][0]
    c2 = C2.set_index("key")
    return c2.loc[k, "society_id"] if k in c2.index else ISS[k][0]
L += [f"## B7. 每部指南的未申报比例（{R12}；按行业；指南内按 人 × 企业 × 年 去重）", "",
      "主分析集和期间推定层。勘误后、外部評価委員按流程的判定算在范围内；分母 = 指南内按 人 × 企业 × 年 去重后、规则一和规则二之后仍可评价的单元（同一组里讲演费、稿费判定不一的算进分母，不算未申报）。"
      "「主学会」= 清点时列在其下的学会（日本循環器学会合办的算日本循環器学会），只用于分组。", "",
      "| 指南 | 分析集 | 主学会 | 年 | 期间 | 委员（名单） | 制药 可评价单元 | 制药 未申报 | 制药 未申报比例 | 器械 可评价单元 | 器械 未申报 | 器械 未申报比例 | 讲演费门槛（万日元） | 稿费门槛（万日元） | 门槛来源 | 抽取诊断的标记 |",
      "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
B7 = {}
for k in MAIN + INF:
    d = D["all"][k]; U2_ = d["U"].assign(judge=d["U"].judge2); a = AS.loc[k]
    dp, dd_ = dedup(U2_, "pharma", False), dedup(U2_, "device", False)
    B7[k] = dict(set=a.analysis_set, soc=prim_soc(k), year=a.title_year, period=a.period_class, roster=len(d["RV"]), ph=dp[:2], dv=dd_[:2],
                 lec=thr_cell(k, "lecture"), man=thr_cell(k, "manuscript"), src=src_cell(k), flag=FLAG.get(k, "—"))
    L += [f"| `{k}` | {a.analysis_set} | {SNAME.get(prim_soc(k), prim_soc(k))} | {a.title_year} | {a.period_class} | {len(d['RV'])} | {dp[1]:,} | {dp[0]:,} | {fmt(dp[0], dp[1])} | "
          f"{dd_[1]:,} | {dd_[0]:,} | {fmt(dd_[0], dd_[1])} | {thr_cell(k, 'lecture')} | {thr_cell(k, 'manuscript')} | {src_cell(k)} | {FLAG.get(k, '—')} |"]
L += ["", f"有器械可评价单元（{R12}，去重后）的指南：主分析集 {sum(B7[k]['dv'][1] > 0 for k in MAIN)} 部，期间推定层 {sum(B7[k]['dv'][1] > 0 for k in INF)} 部。", ""]
# ---------------------------------------------------------------- B8 flow-chart numbers
def flow(keys):
    Us = cat(keys); U2_ = Us.assign(judge=Us.judge2); RVs = [D["all"][k]["RV"] for k in keys]
    return dict(g=len(keys), times=sum(len(r) for r in RVs), persons=len({D["all"][k]["ident"][n] for k in keys for n in D["all"][k]["RV"].nm}),
                inscope=sum(int(r.evaluable.sum()) for r in RVs), linked=sum(len(D["all"][k]["linked"] & set(D["all"][k]["RV"].nm)) for k in keys),
                u=[int((Us.prim == i).sum()) for i in ("pharma", "device")], ev=[undecl(U2_, i, False)[1] for i in ("pharma", "device")],
                dd=[dedup(U2_, i, False)[1] for i in ("pharma", "device")])
B8 = {lab: flow(ks) for lab, ks in (("口径集", SCOPE), ("主分析集", MAIN), ("期间推定层", INF), ("开示项目不含讲演费和稿费", NOITEM))}
L += ["## B8. 流程的数字（图 1 用；勘误后，规则一、二之后，外部評価委員按流程的判定）", "",
      "委员人次 = 各部名单行数之和；委员人数 = 同一人在几部里只算一次（按付款表的个人键，连不上的按规范化姓名）；开示范围内、连上付款表按人次；单元 = 过冻结流程门槛的单元（含无法评价，去重前）。", "",
      "| 集合 | 指南 | 委员人次 | 委员人数 | 开示范围内（人次） | 连上付款表（人次） | 单元 制药 | 单元 器械 | 可评价 制药（去重前） | 可评价 器械（去重前） | 可评价 制药（去重后） | 可评价 器械（去重后） |",
      "|---|---|---|---|---|---|---|---|---|---|---|---|"]
for lab, v in B8.items():
    L += [f"| {lab} | {v['g']} | {v['times']:,} | {v['persons']:,} | {v['inscope']:,} | {v['linked']:,} | {v['u'][0]:,} | {v['u'][1]:,} | {v['ev'][0]:,} | {v['ev'][1]:,} | {v['dd'][0]:,} | {v['dd'][1]:,} |"]
L += [""]
# ---------------------------------------------------------------- B9 errata table
ERR = rd(P/"config"/"company_alias_errata.csv"); CN = pd.read_parquet(P/"kg"/"nodes"/"company.parquet").set_index("company_id").canonical_name
L += [f"## B9. 勘误表（`config/company_alias_errata.csv`，{len(ERR)} 行；在冻结流程之外采用）", "",
      "| 申报写法 | 对应节点 | 节点的企业名 | 依据 | 定于哪个阶段 |", "|---|---|---|---|---|"]
L += [f"| {r.申报写法} | {r.对应节点} | {CN.get(r.对应节点, '—')} | {r.依据} | {r.定于哪个阶段} |" for r in ERR.itertuples()] + [""]
# ---------------------------------------------------------------- sensitivity: the society's other document
ASS = rd(P/"census_sensitivity_root"/"config"/"guidelines_analysis_sets.csv").set_index("key")
THS = {k: {"講演料": float(ASS.loc[k, "lecture_threshold_man"]) * 10000, "原稿料": float(ASS.loc[k, "manuscript_threshold_man"]) * 10000}
       for k in ASS.index if ASS.loc[k, "lecture_threshold_man"] != ""}
SK = [k for k in MAIN + INF if AS.loc[k, "threshold_source_class"] == UNCLEAR]
for k in MAIN + INF:
    U_ = D["all"][k]["U"]
    bs = pd.Series([bool(k in THS and it in THS[k] and a < THS[k][it]) for it, a in zip(U_["item"], U_["amt"])], index=U_.index, dtype=bool) & U_.judge.isin(["已申报", "未申报"])
    U_["judge2s"] = U_.judge.where(~bs, BELOW); U_["below_s"] = bs
sens = lambda keys: cat(keys).assign(judge=lambda d: d.judge2s); offi = lambda keys: cat(keys).assign(judge=lambda d: d.judge2)
SV = {}
for lab, ks in (("主分析集", MAIN), ("期间推定层", INF)):
    Uo_, Us_ = offi(ks), sens(ks)
    SV[lab] = {(kind, ind): ((dedup if kind == "dedup" else per_person)(Uo_, ind, False)[:2], (dedup if kind == "dedup" else per_person)(Us_, ind, False)[:2])
               for kind in ("dedup", "person") for ind in ("pharma", "device")}
MS_ = []
for k in MAIN + INF:
    U_ = D["all"][k]["U"]; b = U_[U_.below_s]
    MS_.append(dict(key=k, set=AS.loc[k, "analysis_set"], moved=int(U_.below_thr.sum()), moved_s=len(b), und=int((b.judge == "未申报").sum()), dec=int((b.judge == "已申报").sum()),
                    lec=f"{float(ASS.loc[k, 'lecture_threshold_man']):g}", man=f"{float(ASS.loc[k, 'manuscript_threshold_man']):g}"))
MS_ = pd.DataFrame(MS_); msk = MS_[(MS_.moved > 0) | (MS_.moved_s > 0)]
PG = {}
for k in SK:
    U_ = D["all"][k]["U"]
    PG[k] = {ind: (dedup(U_.assign(judge=U_.judge2), ind, False)[:2], dedup(U_.assign(judge=U_.judge2s), ind, False)[:2]) for ind in ("pharma", "device")}
    PG[k]["moved_s"] = int(U_.below_s.sum())
alt_l = sorted({f"{float(ASS.loc[k, 'lecture_threshold_man']):g}" for k in SK}); alt_m = sorted({f"{float(ASS.loc[k, 'manuscript_threshold_man']):g}" for k in SK})
socs_ = sorted({AS.loc[k, "threshold_society"] for k in SK})
L += [f"## 敏感性：{'、'.join(socs_)}按细则的 {'、'.join(alt_l)} 万", "",
      f"门槛标「{UNCLEAR}」的 {len(SK)} 部（主分析集 {sum(k in MAIN for k in SK)}、期间推定层 {sum(k in INF for k in SK)}）正式按 50 万日元；这里改用学会细则的金额（讲演费 {'、'.join(alt_l)} 万、稿费 {'、'.join(alt_m)} 万），"
      "其余指南不变（`census_sensitivity_root/config/guidelines_analysis_sets.csv`）。规则第二条在冻结流程之外做，单元与正式数相同，只把规则第二条再判一次；没有重跑抽取和审计。勘误后，外部評価委員按流程的判定算在范围内。", "",
      "### 敏感性：改记的单元（按指南）", "",
      f"敏感性下改记「{BELOW}」的单元共 {int(MS_.moved_s.sum())} 个，在 {int((MS_.moved_s > 0).sum())} 部指南里（正式数：{int(MS_.moved.sum())} 个，{int((MS_.moved > 0).sum())} 部）。", "",
      "| 指南 | 分析集 | 讲演费门槛（敏感性，万日元） | 稿费门槛（敏感性，万日元） | 改记的单元（正式，50 万） | 改记的单元（敏感性） | 敏感性改记的里原判未申报 | 原判已申报 |", "|---|---|---|---|---|---|---|---|"]
L += [f"| `{r.key}` | {r.set} | {r.lec} | {r.man} | {r.moved} | {r.moved_s} | {r.und} | {r.dec} |" for r in msk.itertuples()] + [""]
L += ["### 敏感性：主分析集和期间推定层的合计", "", f"| 集合 | 行 | {R12}（正式） | 敏感性 |", "|---|---|---|---|"]
for lab in SV:
    for kind, ind, rl in (("dedup", "pharma", "制药（去重后）"), ("dedup", "device", "器械（去重后）"), ("person", "pharma", "按人 制药"), ("person", "device", "按人 器械")):
        a_, b_ = SV[lab][(kind, ind)]; L += [f"| {lab} | {rl} | {fmt(*a_)} | {fmt(*b_)} |"]
L += ["", f"### 敏感性：标「{UNCLEAR}」的各部（指南内按 人 × 企业 × 年 去重）", "",
      f"| 指南 | 分析集 | 制药（{R12}，正式） | 制药（敏感性） | 器械（{R12}，正式） | 器械（敏感性） | 敏感性改记的单元 |", "|---|---|---|---|---|---|---|"]
for k in SK:
    v_ = PG[k]; L += [f"| `{k}` | {AS.loc[k, 'analysis_set']} | {fmt(*v_['pharma'][0])} | {fmt(*v_['pharma'][1])} | {fmt(*v_['device'][0])} | {fmt(*v_['device'][1])} | {v_['moved_s']} |"]
L += [""]
NUM["SENS"] = dict(keys=SK, totals=SV, moved=MS_.to_dict("records"), per=PG, alt=(alt_l, alt_m), socs=socs_)
pd.to_pickle(cat(MAIN + INF)[["key", "nm", "node", "ck", "item", "year", "ind", "prim", "person", "judge", "judge2", "judge2s", "below_thr", "below_s", "amt", "external"]],
             P/"census_sensitivity_root"/"work"/"units_rule2_sensitivity.pkl")
NUM["B5"] = B5; NUM["moved"] = MV.to_dict("records"); NUM["B6"] = B6; NUM["B7"] = B7; NUM["B8"] = B8; NUM["sets"] = dict(scope=len(SCOPE), main=len(MAIN), inferred=len(INF), no_item=len(NOITEM), outside=len(KEYS) - len(SCOPE))
(P/"out"/"census_final_v5.md").write_text("\n".join(L), encoding="utf-8")
(P/"work"/"stage18").mkdir(parents=True, exist_ok=True)
pd.to_pickle(dict(NUM=NUM, MAIN=MAIN, INF=INF, SCOPE=SCOPE, NOITEM=NOITEM, KEYS=KEYS, ISS=ISS, FLAG=FLAG, ERR=len(ERR)), P/"work"/"stage18"/"report_numbers.pkl")
pd.to_pickle(cat(MAIN + INF)[["key", "nm", "node", "ck", "item", "year", "ind", "prim", "person", "judge", "judge2", "judge_frozen", "item_rule", "below_thr", "amt", "external"]],
             P/"work"/"stage18"/"units_rule2.pkl")
O16 = pd.read_pickle(P/"work"/"stage17"/"units_rule2.pkl"); O17 = pd.read_pickle(P/"work"/"stage18"/"units_rule2.pkl")
jk = ["key", "nm", "node", "item", "year"]; MJ = O16.merge(O17, on=jk, how="outer", suffixes=("_16", "_17"), indicator=True)
print("units stage 17 / 18", len(O16), len(O17), "| only in one", int((MJ._merge != "both").sum()), "| judge2 changed", int((MJ._merge == "both").sum() - (MJ.judge2_16 == MJ.judge2_17).sum()))
print("sets", NUM["sets"], "| B1 total", NUM["B1"]["total"], NUM["B1"]["forms"], "| fulltext missing", nft)
for lab, T in (("B2 main", T2), ("B3 inferred", T3), ("B4 scope", T4)):
    print(lab, "dedup pharma", T[("dedup", "pharma", False)][1][:2], "device", T[("dedup", "device", False)][1][:2],
          "| person pharma", T[("person", "pharma", False)][1][:2], "device", T[("person", "device", False)][1][:2],
          "| orig dedup pharma", T[("dedup", "pharma", False)][0][:2], "device", T[("dedup", "device", False)][0][:2],
          "| excl dedup pharma", T[("dedup", "pharma", False)][2][:2], "device", T[("dedup", "device", False)][2][:2],
          "| excl person pharma", T[("person", "pharma", False)][2][:2], "device", T[("person", "device", False)][2][:2], "| keys", T["n_excl"],
          "| rule2 dedup pharma", T[("dedup", "pharma", False)][3][:2], "device", T[("dedup", "device", False)][3][:2],
          "| rule2 person pharma", T[("person", "pharma", False)][3][:2], "device", T[("person", "device", False)][3][:2])
print("moved", int(MV.moved.sum()), "in", int((MV.moved > 0).sum()), "guidelines | was undeclared", int(MV.was_undeclared.sum()), "declared", int(MV.was_declared.sum()),
      "| stage 16", int(MV.moved16.sum()), "| guidelines with a different count", int((MV.moved != MV.moved16).sum()))
print("threshold source", AS.loc[MAIN + INF, "threshold_source_class"].value_counts().to_dict())
print("B8", {k: (v["g"], v["times"], v["persons"], v["ev"], v["dd"]) for k, v in B8.items()})
print("SENS guidelines", len(SK), "| moved", int(MS_.moved.sum()), "->", int(MS_.moved_s.sum()), "in", int((MS_.moved_s > 0).sum()), "guidelines")
for lab in SV: print("SENS", lab, {f"{a}|{b}": v for (a, b), v in SV[lab].items()})
for k in SK: print("SENS", k, PG[k])
for k, (a, b, m) in B6.items(): print("B6", k, a, "->", b, "| moved", m)
print("B3 narrow dedup", NB[("dedup", "pharma")][:2], NB[("dedup", "device")][:2], "| person", NB[("person", "pharma")][:2], NB[("person", "device")][:2])
