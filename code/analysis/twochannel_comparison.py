# -*- coding: utf-8 -*-
"""Two channels: comparison groups (user instruction of 2026-11-04). Reads the same frozen inputs as scripts/120_two_channels.py (graph v0.8 only);
does not re-run extraction and changes no frozen file or existing script.
Usage: python scripts/twochannel_comparison.py "<project>"
Reads  kg/nodes/{guideline, company, org}.parquet, kg/edges/{committee_member, paid_person, paid_org, issued_by}.parquet, work/kg_build_v07/members.pkl,
       config/guidelines_analysis_sets.csv, work/stage18/report_numbers.pkl, work/census3/report_numbers.pkl (as script 120);
       work/stage20/two_channels.pkl and out/RESULTS_LEDGER.csv (L1740, L1741) for the reproduction checks only
Writes out/paper/tableS_twochannel_comparison.csv / .xlsx, out/REPORT_twochannel_comparison.md, work/twochannel_comparison/twochannel_comparison.pkl (aggregates),
       and appends new rows (block 14) at the end of out/RESULTS_LEDGER.csv (existing rows untouched; a second run only checks that the rows are the same)
Definitions copied from script 120 without change: authors in disclosure scope, window = audit years up to 2023, audit threshold = max(50 万, rule 2 lecture threshold),
society payments = 学会捐赠 / 学会共同举办 to every issuing society, its branches and regional meetings (meetings are on the society node), in the window.
Unit = guideline x company pair. Company universe of a guideline = the 189 merged company nodes with any published payment record (any paid_person or paid_org edge)
in a year of its window. Groups (a partition of the universe):
  A = paid one author a lecture fee of at least the audit threshold in one window year (set A of script 120: the 1,078 pairs);
  B = paid at least one author a personal payment (any category) in the window, but is not in A;
  C = paid no author any personal payment in the window.
Outcome = the company is in the society channel (set B of script 120). Proportions with Wilson 95% CI; ratios of proportions with the log (Katz) 95% CI, pairs treated as
independent (no adjustment for the same company or guideline appearing in several pairs). Medians and quartiles numpy linear over guidelines with a non-zero denominator.
Sensitivity d: universe restricted to companies that paid any society (学会捐赠 / 学会共同举办 to any recipient) in the window. Descriptive; no test. Prints counts only.
Added 2026-11-04 (manuscript v5, step 1): the paper table (Table S4 of v5): rows all 73 guidelines (main analysis set and period-inferred layer together), main analysis set,
period-inferred layer, sensitivity d (all 73); columns pairs, proportion [95% CI] (pairs), share median (IQR), ratio A vs C (point estimate only); two decimals as in Table S3.
The csv/xlsx now hold this table (the a-d detail stays in the report and in ledger block 14). Its cells are appended to the ledger as block 15 (a second run only checks them).
Stops if group A of the all-73 row does not reproduce Table S3 (1,078 pairs, 0.98 [0.97, 0.99], median share 0.64 (0.47-0.75)).
"""
import pandas as pd, numpy as np, sys, pathlib, math, csv, io, time
sys.stdout.reconfigure(encoding="utf-8")

P = pathlib.Path(sys.argv[1]); KG = P/"kg"; OUTW = P/"work"/"twochannel_comparison"; OUTW.mkdir(parents=True, exist_ok=True)
rd = lambda p: pd.read_csv(p, dtype=str, keep_default_na=False, encoding="utf-8-sig")
AS = rd(P/"config"/"guidelines_analysis_sets.csv").set_index("key")
GL = pd.read_parquet(KG/"nodes"/"guideline.parquet").set_index("guideline_id")
CO = pd.read_parquet(KG/"nodes"/"company.parquet").set_index("company_id")
ORG = pd.read_parquet(KG/"nodes"/"org.parquet", columns=["org_id", "org_type", "parent_org_id"])
CM = pd.read_parquet(KG/"edges"/"committee_member.parquet")
PP = pd.read_parquet(KG/"edges"/"paid_person.parquet", columns=["src_id", "dst_id", "year", "category", "amount"])
PO = pd.read_parquet(KG/"edges"/"paid_org.parquet", columns=["src_id", "dst_id", "year", "category", "amount"])
IB = pd.read_parquet(KG/"edges"/"issued_by.parquet")
MEM = pd.read_pickle(P/"work"/"kg_build_v07"/"members.pkl")
N18 = pd.read_pickle(P/"work"/"stage18"/"report_numbers.pkl"); RN = pd.read_pickle(P/"work"/"census3"/"report_numbers.pkl")
TC = pd.read_pickle(P/"work"/"stage20"/"two_channels.pkl")                       # frozen output of script 120 (checks only)
LAST = 2023; CH2 = ["学会捐赠", "学会共同举办"]
SETS = {"主分析集": [k for k in N18["MAIN"]], "期间推定层": [k for k in N18["INF"]]}
KEYS = SETS["主分析集"] + SETS["期间推定层"]; SETS["全部"] = KEYS
SET_EN = {"主分析集": "Main analysis set (48 guidelines)", "期间推定层": "Period-inferred layer (25 guidelines)", "全部": "All 73 guidelines (reproduction check)"}
GROUPS = ("A", "B", "C")

# ---------------------------------------------------------------- definitions of script 120, unchanged
assert len(KEYS) == 73 and len(SETS["主分析集"]) == 48 and len(SETS["期间推定层"]) == 25
assert set(zip(CM.src_id, CM.dst_id)) == {(i, g) for g, v in zip(MEM.guideline_id, MEM.node_ids) for i in v}
ISS = {k: sorted(IB.loc[IB.src_id == k, "dst_id"]) for k in KEYS}
assert all(ISS[k] == sorted(RN["ISS"][k]) for k in KEYS)
MEM["scope"] = (MEM.in_scope == "是") | ((MEM.in_scope == "不明") & MEM.listed)
WIN = {k: [y for y in range(int(GL.loc[k, "audit_year_first"]), int(GL.loc[k, "audit_year_last"]) + 1) if y <= LAST] for k in KEYS}
THR = {k: max(500_000.0, float(AS.loc[k, "lecture_threshold_man"]) * 1e4) for k in KEYS}
TGT = {k: set(ISS[k]) | set(ORG.loc[ORG.parent_org_id.isin(ISS[k]), "org_id"]) for k in KEYS}
PPl = PP[PP.category == "讲演"]; POc = PO[PO.category.isin(CH2)]
assert WIN == TC["WIN"] and THR == TC["THR"]
def members(k):
    m = MEM[(MEM.guideline_id == k) & MEM.scope].reset_index(drop=True)
    return {pid: i for i, ids in enumerate(m.node_ids) for pid in ids}, len(m)

# ---------------------------------------------------------------- groups for each guideline
PER = {}
for k in KEYS:
    yrs = WIN[k]; pid2m, nm_ = members(k)
    x = PPl[PPl.dst_id.isin(pid2m) & PPl.year.isin(yrs)].copy(); x["m"] = x.dst_id.map(pid2m)
    s = x.groupby(["src_id", "m", "year"]).amount.sum(); A = set(s[s >= THR[k]].index.get_level_values(0))     # set A of script 120
    y = POc[POc.dst_id.isin(TGT[k]) & POc.year.isin(yrs)]; s2 = y.groupby("src_id").amount.sum(); SOCB = set(s2[s2 > 0].index)   # set B of script 120 (society channel)
    xa = PP[PP.dst_id.isin(pid2m) & PP.year.isin(yrs)].copy(); xa["m"] = xa.dst_id.map(pid2m)
    ANY = set(xa.src_id)                                                                 # any personal payment to an author in the window
    U = (set(PP.loc[PP.year.isin(yrs), "src_id"]) | set(PO.loc[PO.year.isin(yrs), "src_id"])) & set(CO.index)       # any published payment record in the window
    UD = U & set(PO.loc[PO.year.isin(yrs) & PO.category.isin(CH2), "src_id"])           # sensitivity d: paid any society in the window
    assert A <= ANY <= U and SOCB <= U
    G = {"A": A, "B": ANY - A, "C": U - ANY}
    big = xa[xa.src_id.isin(G["B"])].groupby(["src_id", "m", "year", "category"]).amount.sum()
    b_other_over = set(big[big >= THR[k]].index.get_level_values(0))                    # B companies with another category at or above the threshold
    assert "讲演" not in set(big[big >= THR[k]].index.get_level_values(3))              # (B has no lecture fee at the threshold, by definition)
    amt = s2.reindex(sorted(U), fill_value=0.0); tot = float(s2.sum())
    PER[k] = dict(U=len(U), UD=len(UD), n={g: len(G[g]) for g in GROUPS}, s={g: len(G[g] & SOCB) for g in GROUPS},
                  nd={g: len(G[g] & UD) for g in GROUPS}, sd={g: len(G[g] & UD & SOCB) for g in GROUPS},
                  total=tot, amt={g: float(s2.reindex(sorted(G[g])).fillna(0).sum()) for g in GROUPS}, b_other_over=len(b_other_over))
    # reproduction of script 120, guideline by guideline
    r = TC["RES"]["main"][k]["all"]
    assert (PER[k]["n"]["A"], PER[k]["s"]["A"], len(SOCB)) == (r["A"], r["AB"], r["B"]) and abs(tot - r["total"]) < 0.5 and abs(PER[k]["amt"]["A"] - r["fromA"]) < 0.5, k
    assert abs(sum(PER[k]["amt"].values()) - tot) < 0.5                                   # every society payer is in the universe

# ---------------------------------------------------------------- statistics
Z = 1.959963984540054
def wilson(k, n):
    p = k / n; d = 1 + Z * Z / n; c = (p + Z * Z / (2 * n)) / d; h = Z * math.sqrt(p * (1 - p) / n + Z * Z / (4 * n * n)) / d
    return p, max(0.0, c - h), min(1.0, c + h)
def ratio(k1, n1, k2, n2):
    if min(k1, k2) == 0: return None
    r = (k1 / n1) / (k2 / n2); se = math.sqrt(1 / k1 - 1 / n1 + 1 / k2 - 1 / n2)
    return r, r * math.exp(-Z * se), r * math.exp(Z * se)
def mq(v):
    v = [x for x in v if x is not None]
    return (tuple(np.percentile(v, [50, 25, 75])) + (len(v),)) if v else None
f3 = lambda e: f"{e[0]:.3f} [{e[1]:.3f}, {e[2]:.3f}]"
RES = {}
for sname, ks in SETS.items():
    R = {}
    for tag, nk, sk in (("main", "n", "s"), ("d", "nd", "sd")):
        n = {g: sum(PER[k][nk][g] for k in ks) for g in GROUPS}; s_ = {g: sum(PER[k][sk][g] for k in ks) for g in GROUPS}
        R[tag] = dict(n=n, s=s_, p={g: wilson(s_[g], n[g]) if n[g] else None for g in GROUPS},
                      AC=ratio(s_["A"], n["A"], s_["C"], n["C"]), AB=ratio(s_["A"], n["A"], s_["B"], n["B"]),
                      U=sum(PER[k]["U" if tag == "main" else "UD"] for k in ks))
    R["per_guideline"] = {g: mq([PER[k]["s"][g] / PER[k]["n"][g] if PER[k]["n"][g] else None for k in ks]) for g in GROUPS}
    R["share"] = {g: mq([PER[k]["amt"][g] / PER[k]["total"] if PER[k]["total"] > 0 else None for k in ks]) for g in GROUPS}
    R["pooled_share_A"] = sum(PER[k]["amt"]["A"] for k in ks) / sum(PER[k]["total"] for k in ks)
    R["b_other_over"] = sum(PER[k]["b_other_over"] for k in ks)
    RES[sname] = R

# ---------------------------------------------------------------- reproduction checks (stop if they fail)
LG = rd(P/"out"/"RESULTS_LEDGER.csv").set_index("编号")
al = RES["全部"]["main"]; chk = {}
chk["A pairs = 1,078 (L1740)"] = al["n"]["A"] == 1078 and "1,078" in LG.loc["L1740", "数值"]
chk["A pairs paying the society = 1,057 (L1740)"] = al["s"]["A"] == 1057
chk["A proportion = 0.98 (L1740)"] = f"{al['p']['A'][0]:.2f}" == "0.98" and "0.98，95% CI [0.97, 0.99]" in LG.loc["L1740", "数值"]
chk["share of society payments from A, median = 0.64, IQR 0.47-0.75, 73 guidelines (L1741)"] = (lambda m: (f"{m[0]:.2f}", f"{m[1]:.2f}", f"{m[2]:.2f}", m[3]) == ("0.64", "0.47", "0.75", 73))(RES["全部"]["share"]["A"]) \
    and "0.64（四分位距 0.47–0.75，73 部）" in LG.loc["L1741", "数值"]
chk["pooled share from A = 0.62 (L1740)"] = f"{RES['全部']['pooled_share_A']:.2f}" == "0.62"
for sname in ("主分析集", "期间推定层"):
    pl = TC["POOL"]["main"][sname]["all"]
    chk[f"{sname}: A pairs and A pairs paying the society equal script 120 ({pl['A']}, {pl['AB']})"] = (RES[sname]["main"]["n"]["A"], RES[sname]["main"]["s"]["A"]) == (pl["A"], pl["AB"])
    med = RES[sname]["share"]["A"]; want = pl["med_share"]
    chk[f"{sname}: median share from A equals script 120 ({want})"] = want.startswith(f"{med[0]:.2f}（四分位距 {med[1]:.2f}–{med[2]:.2f}，{med[3]} 部）")
chk["every guideline: set A, A paying the society, society payers, total and amount from A equal script 120 (73/73)"] = True     # asserted above
if not all(chk.values()):
    print("REPRODUCTION FAILED:", [c for c, v in chk.items() if not v]); sys.exit(1)

# ---------------------------------------------------------------- paper table (manuscript v5, Table S4; user instruction of 2026-11-04, v5 step 1)
# Rows: all 73 guidelines (main analysis set and period-inferred layer together), main analysis set, period-inferred layer, sensitivity d (all 73).
# Columns: pairs; proportion paying the issuing society [95% CI] (pairs); share of society payments, median (IQR); ratio A vs C (point estimate only).
# Two decimals, formatted as in Table S3 (scripts/120_two_channels.py: f"{x:.2f}"). The shares do not change under sensitivity d (every company that paid
# the issuing society is in the restricted universe: SOCB <= UD), so they are not repeated there.
f2p = lambda e, k, n: f"{e[0]:.2f} [{e[1]:.2f}, {e[2]:.2f}] ({k:,}/{n:,})"
f2m = lambda m: f"{m[0]:.2f} ({m[1]:.2f}–{m[2]:.2f})"
f2r = lambda e: f"{e[0]:.2f}"
PANELS = [("A", "全部", "main", "Panel A. All analyzed guidelines (73)"), ("B", "主分析集", "main", "Panel B. Main analysis set (48 guidelines)"),
          ("C", "期间推定层", "main", "Panel C. Period-inferred layer (25 guidelines)"),
          ("D", "全部", "d", "Panel D. Sensitivity analysis: companies restricted to those that paid any society, all analyzed guidelines (73)")]
GLAB = {"A": "Group A: paid an author above the threshold", "B": "Group B: paid authors below the threshold", "C": "Group C: paid no author"}
PT = []
for pk, sname, tag, plab in PANELS:
    R = RES[sname][tag]
    for g in GROUPS:
        PT.append(dict(panel=pk, panel_label=plab, sname=sname, tag=tag, group=g, label=GLAB[g], pairs=f"{R['n'][g]:,}", prop=f2p(R["p"][g], R["s"][g], R["n"][g]),
                       share=f2m(RES[sname]["share"][g]) if tag == "main" else "—", ratio=f2r(R["AC"]) if g == "A" else "—"))
S3C = rd(P/"out"/"paper"/"tableS3_two_channels.csv")
s3 = lambda rk, ck: S3C[(S3C.rkey == rk) & (S3C.ckey.str.rstrip("✱†‡§¶‖") == ck)].text.iloc[0]
pt = lambda pk, g: next(r for r in PT if r["panel"] == pk and r["group"] == g)
chk_t = {}
for pk, sname in (("A", "全部"), ("B", "主分析集"), ("C", "期间推定层")):
    a = pt(pk, "A"); rk = f"all.pool.{sname}"
    chk_t[f"Table S4 panel {pk}, group A = Table S3 total row ({s3(rk, 'Guideline-company pairs in set A')}; {s3(rk, 'Share of set A also in set B [95% CI] (pairs)')}; "
          f"{s3(rk, 'Share of society payments from set A, median (IQR)')})"] = (a["pairs"], a["prop"], a["share"]) == (
        s3(rk, "Guideline-company pairs in set A"), s3(rk, "Share of set A also in set B [95% CI] (pairs)"), s3(rk, "Share of society payments from set A, median (IQR)"))
chk_t["Table S4 panel A, group A: 1,078 pairs, 0.98, median share 0.64"] = (pt("A", "A")["pairs"], pt("A", "A")["prop"][:4], pt("A", "A")["share"][:4]) == ("1,078", "0.98", "0.64")
chk_t["Table S4 panel D, group A equals panel A, group A (restriction keeps every group A company)"] = (pt("D", "A")["pairs"], pt("D", "A")["prop"]) == (pt("A", "A")["pairs"], pt("A", "A")["prop"])
chk_t["groups partition the universe in every panel (A + B + C = pairs in the universe)"] = all(
    sum(RES[s][t]["n"][g] for g in GROUPS) == RES[s][t]["U"] for _, s, t, _ in PANELS)
if not all(chk_t.values()):
    print("TABLE S4 CHECK FAILED:", [c for c, v in chk_t.items() if not v]); sys.exit(1)
BOO = {s: RES[s]["b_other_over"] for s in ("全部", "主分析集", "期间推定层")}
assert BOO["全部"] == BOO["主分析集"] + BOO["期间推定层"]
S4_NOTES = [
    ("✱", "Unit: guideline-company pair. For each guideline, the companies are those with any published payment record (a personal or institutional payment) in a year of the guideline's audit window, "
          "divided into three groups by their personal payments within the window to the guideline's authors within the disclosure scope. Group A: lecture fees reaching the guideline's audit threshold "
          "to one author in at least one year (set A of Table S3). Group B: a personal payment of any category to at least one author, without meeting the definition of group A. Group C: no personal "
          "payment to any author. Descriptive only; no statistical tests."),
    ("†", "The company paid the issuing societies (all co-issuers together, including their branches and the scientific meetings they host) donations or co-sponsorship fees within the same window "
          "(set B of Table S3). Pairs are summed over guidelines; shares of pairs carry Wilson 95% confidence intervals (CIs). The intervals treat guideline-company pairs as independent; because the "
          "same company appears in several guidelines, the intervals are narrower than they should be."),
    ("‡", "Share of the donations and co-sponsorship fees received by the issuing societies within the window that came from the group's companies, per guideline, summarized as median and "
          "interquartile range (IQR, first to third quartile) across guidelines; no CI because the share is not a count."),
    ("§", "Share of pairs whose company paid the issuing society in group A divided by that in group C; point estimate only. —, not applicable."),
    ("¶", f"Includes pairs in which a payment in another category (consulting, manuscript or other fees) reached the audit threshold for one author in one year: {BOO['全部']:,} pairs in all analyzed "
          f"guidelines, {BOO['主分析集']:,} in the main analysis set and {BOO['期间推定层']:,} in the period-inferred layer."),
    ("‖", "Companies restricted to those that paid donations or co-sponsorship fees to any society within the window. The shares of society payments are not shown (—) because the restriction does "
          "not change them: every company that paid the issuing society is in the restricted universe."),
]
S4_TITLE = ("Table S4. The two channels by the companies' payments to the guideline's authors: guideline-company pairs in three groups, 73 guidelines from 25 medical societies in Japan, "
            "title years 2022 to 2025")
S4_HEAD = ["Panel and group", "Guideline-company pairs", "Share of pairs whose company paid the issuing society [95% CI] (pairs)", "Share of society payments from the group, median (IQR)",
           "Ratio of shares, group A vs group C"]
S4_HSYM = ["", "", "†", "‡", "§"]

# ---------------------------------------------------------------- table (a to d): kept in memory for the report only (the csv/xlsx now carry the paper table)
rows = []
def add(sec, sname, item, guidelines, pairs, with_soc, est):
    rows.append({"Section": sec, "Analysis set": SET_EN[sname], "Item": item, "Guidelines": guidelines, "Pairs": pairs, "Pairs with society payment": with_soc, "Estimate [95% CI]": est})
GDESC = {"A": "Group A: lecture fee at or above the audit threshold to an author", "B": "Group B: personal payment to an author, none meeting group A", "C": "Group C: no personal payment to any author"}
for tag, sec in (("main", "a"), ("d", "d")):
    for sname, ks in SETS.items():
        R = RES[sname][tag]
        for g in GROUPS:
            add(f"{sec}. Proportion of pairs whose company paid the issuing society" + (" (universe: companies that paid any society)" if tag == "d" else ""), sname, GDESC[g], len(ks),
                f"{R['n'][g]:,}", f"{R['s'][g]:,}", f3(R["p"][g]) if R["p"][g] else "—")
        for lab, key in (("Ratio of proportions, A vs C", "AC"), ("Ratio of proportions, A vs B", "AB")):
            add(f"{sec}. Ratio of proportions" + (" (universe: companies that paid any society)" if tag == "d" else ""), sname, lab, len(ks), "", "", f3(R[key]) if R[key] else "—")
    if tag == "main":
        for sname, ks in SETS.items():
            for g in GROUPS:
                m = RES[sname]["per_guideline"][g]
                add("b. Proportion by guideline, median [IQR]", sname, GDESC[g] + (f" ({m[3]} guidelines with pairs in the group)" if m else ""), len(ks), "", "", f3(m) if m else "—")
        for sname, ks in SETS.items():
            for g in GROUPS:
                m = RES[sname]["share"][g]
                add("c. Share of the issuing society's payments from the group's companies, median [IQR] by guideline", sname, GDESC[g] + (f" ({m[3]} guidelines)" if m else ""), len(ks), "", "", f3(m) if m else "—")
TAB = pd.DataFrame(rows)

# ---------------------------------------------------------------- ledger rows (block 14), appended at the end; existing rows untouched
BLOCK = "14 两条通道的对照组"; SRC_T = "out/paper/tableS_twochannel_comparison.csv"; SCRIPT = "scripts/twochannel_comparison.py"; STATUS = "模型抽取，未经人工核对"
DEF = ("（单位 = 指南 × 企业；企业全集 = 该指南审计窗口内有任何公开付款记录的合并企业节点；A = 给开示范围内的作者付过不低于审计门槛的讲演费（即两条通道的集合 A）；"
       "B = 给作者付过个人付款但不属于 A；C = 没有给任何作者付过个人付款；结果 = 同一窗口给发行学会付过学会捐赠或学会共同举办费；定义同 scripts/120_two_channels.py；图谱 v0.8）")
SJP = {"主分析集": "主分析集", "期间推定层": "期间推定层", "全部": "全部 73 部"}
fmt_p = lambda e, k, n: f"{e[0]:.3f}，95% CI [{e[1]:.3f}, {e[2]:.3f}]（{k:,}/{n:,}）"
fmt_r = lambda e: f"{e[0]:.3f}，95% CI [{e[1]:.3f}, {e[2]:.3f}]" if e else "—"
fmt_m = lambda m: f"{m[0]:.3f}（四分位距 {m[1]:.3f}–{m[2]:.3f}，{m[3]} 部）" if m else "—"
NEWROWS = []
for tag, pre in (("main", "【两条通道的对照组】"), ("d", "【两条通道的对照组·敏感性 d：企业全集限定为窗口内给任何学会付过学会捐赠或共同举办费的企业】")):
    for sname in SETS:
        R = RES[sname][tag]
        for g in GROUPS:
            NEWROWS.append((f"{pre}{SJP[sname]}，{g} 组：指南 × 企业的对子数{DEF}", f"{R['n'][g]:,}", "§ a" if tag == "main" else "§ d"))
            NEWROWS.append((f"{pre}{SJP[sname]}，{g} 组：给发行学会付过款的对子的比例{DEF}", fmt_p(R["p"][g], R["s"][g], R["n"][g]) if R["p"][g] else "—", "§ a" if tag == "main" else "§ d"))
        NEWROWS.append((f"{pre}{SJP[sname]}：比例之比 A 对 C（对数法 95% CI，对子按独立处理）{DEF}", fmt_r(R["AC"]), "§ a" if tag == "main" else "§ d"))
        NEWROWS.append((f"{pre}{SJP[sname]}：比例之比 A 对 B（对数法 95% CI，对子按独立处理）{DEF}", fmt_r(R["AB"]), "§ a" if tag == "main" else "§ d"))
for sname in SETS:
    for g in GROUPS:
        NEWROWS.append((f"【两条通道的对照组】{SJP[sname]}，{g} 组：各部指南给发行学会付过款的对子比例的中位数（分母为 0 的指南不算）{DEF}", fmt_m(RES[sname]["per_guideline"][g]), "§ b"))
for sname in SETS:
    for g in GROUPS:
        NEWROWS.append((f"【两条通道的对照组】{SJP[sname]}，{g} 组：发行学会在窗口内收到的学会捐赠和共同举办费里来自该组企业的份额，各部指南的中位数{DEF}", fmt_m(RES[sname]["share"][g]), "§ c"))
lp = P/"out"/"RESULTS_LEDGER.csv"; raw = lp.read_bytes()
cur = list(csv.DictReader(io.StringIO(raw.decode("utf-8-sig"))))
mine = [r for r in cur if r["块"] == BLOCK]
DRY = len(sys.argv) > 2 and sys.argv[2] == "--dry"
if DRY:
    ledger_note = "试运行，台账未动。"
elif mine:                                                                                  # second run: verify, do not append
    assert [(r["说明"], r["数值"]) for r in mine] == [(a, b) for a, b, _ in NEWROWS], "block 14 rows differ from this run"
    ids = [r["编号"] for r in mine]; ledger_note = f"台账第 14 块已存在（{ids[0]}–{ids[-1]}），本次核对相同，未追加。"
else:
    start = max(int(r["编号"][1:]) for r in cur) + 1
    buf = io.StringIO(); w = csv.writer(buf, lineterminator="\r\n")
    for j, (desc, val, sec) in enumerate(NEWROWS):
        assert "；" not in val
        w.writerow([f"L{start + j}", BLOCK, desc, val, f"{SRC_T}、out/REPORT_twochannel_comparison.md {sec}", SCRIPT, STATUS])
    assert raw.endswith(b"\r\n")
    with open(lp, "ab") as fh: fh.write(buf.getvalue().encode("utf-8"))
    assert lp.read_bytes()[:len(raw)] == raw                                              # existing bytes unchanged
    ids = [f"L{start}", f"L{start + len(NEWROWS) - 1}"]; ledger_note = f"台账第 14 块新追加 {len(NEWROWS)} 行（{ids[0]}–{ids[-1]}）；已有 {len(cur):,} 行逐字节不变。"

# ---------------------------------------------------------------- ledger rows (block 15): the cells of the paper table (two decimals), appended at the end; existing rows untouched
BLOCK15 = "15 两条通道的对照组（论文表）"; SRC15 = "out/paper/tableS_twochannel_comparison.csv"
SJP15 = {"全部": "全部 73 部", "主分析集": "主分析集", "期间推定层": "期间推定层"}
def2 = lambda tag: DEF[:-1] + ("；论文 v5 的 Table S4，两位小数，与 Table S3 同一写法）" if tag == "main" else
                               "；敏感性 d：企业全集限定为窗口内给任何学会付过学会捐赠或共同举办费的企业；论文 v5 的 Table S4 面板 D，两位小数）")
NEW15 = []                                                                                  # (description, value, table cell key)
for pk, sname, tag, plab in PANELS:
    R = RES[sname][tag]; pre = f"【两条通道的对照组·论文表 面板 {pk}】{SJP15[sname]}"
    for g in GROUPS:
        e = R["p"][g]; NEW15.append((f"{pre}，{g} 组：给发行学会付过款的对子的比例{def2(tag)}", f"{e[0]:.2f}，95% CI [{e[1]:.2f}, {e[2]:.2f}]（{R['s'][g]:,}/{R['n'][g]:,}）", (pk, g, "prop")))
    if tag == "main":
        for g in GROUPS:
            m = RES[sname]["share"][g]
            NEW15.append((f"{pre}，{g} 组：发行学会在窗口内收到的学会捐赠和共同举办费里来自该组企业的份额，各部指南的中位数{def2(tag)}", f"{m[0]:.2f}（四分位距 {m[1]:.2f}–{m[2]:.2f}，{m[3]} 部）", (pk, g, "share")))
    NEW15.append((f"{pre}：比例之比 A 对 C 的点估计（不给区间）{def2(tag)}", f"{R['AC'][0]:.2f}", (pk, "A", "ratio")))
for sname in ("全部", "主分析集", "期间推定层"):
    NEW15.append((f"【两条通道的对照组·论文表 脚注¶】{SJP15[sname]}，B 组里某一作者某一年某一类别（讲演费以外：咨询、稿费、其他）达到审计门槛的对子数{DEF}", f"{BOO[sname]:,}", ("note", sname, "boo")))
raw2 = lp.read_bytes(); cur2 = list(csv.DictReader(io.StringIO(raw2.decode("utf-8-sig")))); mine15 = [r for r in cur2 if r["块"] == BLOCK15]
ID15 = {}
if DRY:
    ledger_note15 = "试运行，台账未动。"
elif mine15:
    assert [(r["说明"], r["数值"]) for r in mine15] == [(a, b) for a, b, _ in NEW15], "block 15 rows differ from this run"
    ID15 = {key: r["编号"] for r, (_, _, key) in zip(mine15, NEW15)}; ledger_note15 = f"台账第 15 块已存在（{mine15[0]['编号']}–{mine15[-1]['编号']}），本次核对相同，未追加。"
else:
    start = max(int(r["编号"][1:]) for r in cur2) + 1
    buf = io.StringIO(); w = csv.writer(buf, lineterminator="\r\n")
    for j, (desc, val, key) in enumerate(NEW15):
        assert "；" not in val
        w.writerow([f"L{start + j}", BLOCK15, desc, val, f"{SRC15}、out/REPORT_twochannel_comparison.md § e", SCRIPT, STATUS]); ID15[key] = f"L{start + j}"
    assert raw2.endswith(b"\r\n")
    with open(lp, "ab") as fh: fh.write(buf.getvalue().encode("utf-8"))
    assert lp.read_bytes()[:len(raw2)] == raw2
    ledger_note15 = f"台账第 15 块新追加 {len(NEW15)} 行（L{start}–L{start + len(NEW15) - 1}）；已有 {len(cur2):,} 行逐字节不变。"
# block 14 rows that hold the pair counts of the paper table
LG2 = rd(lp).set_index("编号") if not DRY else LG
def id14(tag, sname, g):
    pre = "【两条通道的对照组】" if tag == "main" else "【两条通道的对照组·敏感性 d：企业全集限定为窗口内给任何学会付过学会捐赠或共同举办费的企业】"
    hit = LG2[(LG2["块"] == BLOCK) & LG2["说明"].str.startswith(f"{pre}{SJP[sname]}，{g} 组：指南 × 企业的对子数")]
    return hit.index[0] if len(hit) == 1 else "(dry)"
OUTROWS = []
for pk, sname, tag, plab in PANELS:
    OUTROWS.append({"Panel": pk, "Row": plab + ("‖" if pk == "D" else ""), S4_HEAD[1]: "", S4_HEAD[2]: "", S4_HEAD[3]: "", S4_HEAD[4]: "", "Ledger": ""})
    for g in GROUPS:
        r = pt(pk, g); ids = [id14(tag, sname, g), ID15.get((pk, g, "prop"), "(dry)")] + ([ID15.get((pk, g, "share"), "(dry)")] if tag == "main" else []) + \
                           ([ID15.get((pk, "A", "ratio"), "(dry)")] if g == "A" else [])
        OUTROWS.append({"Panel": pk, "Row": r["label"] + ("¶" if g == "B" and pk != "D" else ""), S4_HEAD[1]: r["pairs"], S4_HEAD[2]: r["prop"], S4_HEAD[3]: r["share"], S4_HEAD[4]: r["ratio"],
                        "Ledger": "|".join(ids)})
OUT = pd.DataFrame(OUTROWS)
OUT.columns = ["Panel", S4_HEAD[0]] + [h + s for h, s in zip(S4_HEAD[1:], S4_HSYM[1:])] + ["Ledger"]
OUT.to_csv(P/"out"/"paper"/"tableS_twochannel_comparison.csv", index=False, encoding="utf-8-sig")
with pd.ExcelWriter(P/"out"/"paper"/"tableS_twochannel_comparison.xlsx", engine="openpyxl") as xw:
    OUT.to_excel(xw, index=False, sheet_name="Table S4", startrow=1)
    ws = xw.sheets["Table S4"]; ws.cell(row=1, column=1, value=S4_TITLE + "✱")
    for j, (s, t) in enumerate(S4_NOTES): ws.cell(row=len(OUT) + 4 + j, column=1, value=f"{s} {t}")
    for col, wd in zip("ABCDEFG", (7, 62, 12, 34, 26, 16, 34)): ws.column_dimensions[col].width = wd

# ---------------------------------------------------------------- report
def tline(tag, sname):
    R = RES[sname][tag]
    return [f"| {SJP[sname]} | {g} | {R['n'][g]:,} | {R['s'][g]:,} | {f3(R['p'][g]) if R['p'][g] else '—'} |" for g in GROUPS]
L = ["# 两条通道的对照组：指南 × 企业的对子分三组", "",
     f"生成脚本：`scripts/twochannel_comparison.py`。生成日期：{time.strftime('%Y-%m-%d')}。只读图谱 v0.8 和冻结的输入（与 `scripts/120_two_channels.py` 相同），没有重跑抽取，没有改冻结件和已有脚本。"
     "作者名单和开示范围是冻结流程的模型抽取，未经人工核对。只含汇总数。", "",
     "## 定义", "",
     "- 期间、作者集合、门槛、学会付款：沿用 `scripts/120_two_channels.py`（论文 v4 的 Table S3，交接文档第 10 节的「表 2 两条通道」）一字不改。作者 = 开示范围内的委员（in_scope 为「是」，或「不明」且列在开示文件里）；"
     "期间 = 该指南的审计年份（付款数据只到 2023 年）；门槛 = 50 万日元与规则第二条的讲演费门槛中较高的，按某一作者某一年从某一企业收到的讲演费合计判断；学会付款 = 期间内给全部发行学会（含支部、地方会、主办的学术集会）的学会捐赠和学会共同举办费。",
     "- 分析单位：指南 × 企业的对子。企业全集：图谱 189 家合并企业中，在该指南期间内有任何公开付款记录（任何个人付款或机构付款的边）的企业。",
     "- A 组：期间内给该指南至少一名作者付过门槛以上讲演费的企业（= 两条通道的集合 A，73 部合计 1,078 对）。",
     "- B 组：给至少一名作者付过个人付款（任何类别），但不属于 A 组。即没有一笔讲演费达到门槛；其他类别（稿费、顾问费等）的金额不设限制，B 组里某一作者某一年某一类别达到门槛的对子数另列在下面。",
     "- C 组：期间内没有给该指南任何作者付过个人付款。",
     "- 结果：该企业在同一期间给发行学会付过款（= 两条通道的集合 B）。",
     "- 比例附 Wilson 95% CI；比例之比用对数法（Katz）95% CI，对子按独立处理（同一企业、同一指南出现在多个对子里，没有调整，区间偏窄）。各部指南的中位数和四分位距用 numpy 线性插值，分母为 0 的指南不算。描述性，不做检验。",
     "- 敏感性 d：企业全集限定为期间内给任何学会付过学会捐赠或学会共同举办费（收款方不限于发行学会）的企业，重算 a。", "",
     "## 与两条通道（1,078、0.98、0.64）的一致性", ""] + [f"- {c}：{'一致' if v else '不一致'}" for c, v in chk.items()] + [
     f"- 每部指南的学会付款合计 = A、B、C 三组企业的付款之和（73/73），即付过学会的企业都在企业全集里。", "",
     "## a. 三组的对子数和给发行学会付款的比例", "", "| 分析集 | 组 | 对子 | 其中给学会付过款 | 比例 [95% CI] |", "|---|---|---|---|---|"]
for sname in SETS: L += tline("main", sname)
L += ["", "| 分析集 | A 对 C [95% CI] | A 对 B [95% CI] | 企业全集的对子合计 |", "|---|---|---|---|"]
for sname in SETS:
    R = RES[sname]["main"]; L += [f"| {SJP[sname]} | {f3(R['AC']) if R['AC'] else '—'} | {f3(R['AB']) if R['AB'] else '—'} | {R['U']:,} |"]
L += ["", f"B 组里某一作者某一年某一类别（讲演费以外）达到门槛的对子：主分析集 {RES['主分析集']['b_other_over']:,}、期间推定层 {RES['期间推定层']['b_other_over']:,}、全部 {RES['全部']['b_other_over']:,}。", "",
      "## b. 按指南的比例：中位数 [四分位距]", "", "| 分析集 | A | B | C |", "|---|---|---|---|"]
for sname in SETS:
    pg = RES[sname]["per_guideline"]; L += [f"| {SJP[sname]} | " + " | ".join(f"{f3(pg[g])}（{pg[g][3]} 部）" if pg[g] else "—" for g in GROUPS) + " |"]
L += ["", "## c. 发行学会收到的学会捐赠和共同举办费里来自三组企业的份额：各部指南的中位数 [四分位距]", "", "| 分析集 | A | B | C |", "|---|---|---|---|"]
for sname in SETS:
    sh = RES[sname]["share"]; L += [f"| {SJP[sname]} | " + " | ".join(f"{f3(sh[g])}（{sh[g][3]} 部）" if sh[g] else "—" for g in GROUPS) + " |"]
L += ["", f"A 组份额的合并值（金额相加）：主分析集 {RES['主分析集']['pooled_share_A']:.3f}、期间推定层 {RES['期间推定层']['pooled_share_A']:.3f}、全部 {RES['全部']['pooled_share_A']:.3f}（两条通道表的 0.62）。", "",
      "## d. 敏感性：企业全集限定为期间内给任何学会付过款的企业", "", "| 分析集 | 组 | 对子 | 其中给发行学会付过款 | 比例 [95% CI] |", "|---|---|---|---|---|"]
for sname in SETS: L += tline("d", sname)
L += ["", "| 分析集 | A 对 C [95% CI] | A 对 B [95% CI] | 企业全集的对子合计 |", "|---|---|---|---|"]
for sname in SETS:
    R = RES[sname]["d"]; L += [f"| {SJP[sname]} | {f3(R['AC']) if R['AC'] else '—'} | {f3(R['AB']) if R['AB'] else '—'} | {R['U']:,} |"]
L += ["", "## e. 论文表（论文 v5 的 Table S4）", "",
      "行序：全部 73 部（主分析集与期间推定层合并）、主分析集 48 部、期间推定层 25 部、敏感性 d（全部 73 部）。两位小数，写法与 Table S3 相同。A 对 C 的比值只给点估计。"
      "敏感性 d 不改变份额（给发行学会付过款的企业都在限定后的企业全集里），所以面板 D 的份额不重复列出。", "",
      f"**{S4_TITLE}✱**", "", "| " + " | ".join(h + s for h, s in zip(S4_HEAD, S4_HSYM)) + " |", "|---|---|---|---|---|"]
for pk, sname, tag, plab in PANELS:
    L += [f"| **{plab}{'‖' if pk == 'D' else ''}** | | | | |"]
    for g in GROUPS:
        r = pt(pk, g); L += [f"| {r['label']}{'¶' if g == 'B' and pk != 'D' else ''} | {r['pairs']} | {r['prop']} | {r['share']} | {r['ratio']} |"]
L += [""] + [f"{s} {t}" for s, t in S4_NOTES] + ["", "论文表的核对：", ""] + [f"- {c}：{'一致' if v else '不一致'}" for c, v in chk_t.items()]
L += ["", "## 输出", "", "- `out/paper/tableS_twochannel_comparison.csv` 和 `.xlsx`：论文表（§ e 的行序和写法；`Ledger` 列为各行数字的台账编号：对子数在第 14 块，比例、份额、比值在第 15 块）。"
      "a 到 d 的三位小数在本报告和台账第 14 块。",
      f"- {ledger_note}", f"- {ledger_note15}", "- `work/twochannel_comparison/twochannel_comparison.pkl`：各部指南的组大小和金额（汇总数）。", ""]
(P/"out"/"REPORT_twochannel_comparison.md").write_text("\n".join(L), encoding="utf-8")
pd.to_pickle(dict(PER=PER, RES=RES, SETS=SETS, checks=chk, paper_table=PT, paper_checks=chk_t, notes=S4_NOTES, title=S4_TITLE, head=S4_HEAD, hsym=S4_HSYM, ledger15=ID15),
             OUTW/"twochannel_comparison.pkl")
for sname in SETS:
    R = RES[sname]["main"]; D = RES[sname]["d"]
    print(sname, {g: (R["n"][g], R["s"][g], round(R["p"][g][0], 3) if R["p"][g] else None) for g in GROUPS}, "AC", tuple(round(x, 3) for x in R["AC"]) if R["AC"] else None,
          "AB", tuple(round(x, 3) for x in R["AB"]) if R["AB"] else None, "| share med", {g: round(RES[sname]["share"][g][0], 3) if RES[sname]["share"][g] else None for g in GROUPS},
          "| d", {g: (D["n"][g], round(D["p"][g][0], 3) if D["p"][g] else None) for g in GROUPS}, "AC_d", tuple(round(x, 3) for x in D["AC"]) if D["AC"] else None)
print("checks", all(chk.values()), "| table S4 checks", all(chk_t.values()), "|", ledger_note, "|", ledger_note15)
for r in PT: print(r["panel"], r["group"], r["pairs"], r["prop"], r["share"], r["ratio"])
