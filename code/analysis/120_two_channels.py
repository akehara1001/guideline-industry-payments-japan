# -*- coding: utf-8 -*-
"""Stage 19, step A (stage 20: sensitivity 3 = channel 2 with every category of institutional payment; the total of the guidelines co-issued by
societies outside the 25 sampled; the decided notes; the pickle goes to work/stage20): the two channels for the 73 guidelines of the analysis sets (main 48, period-inferred 25), read from graph v0.8 only.
Usage: python 120_two_channels.py "<project>"
Reads  kg/nodes/{guideline, company, org, society}.parquet, kg/edges/{committee_member, paid_person, paid_org, issued_by}.parquet (v0.8, not changed),
       work/kg_build_v07/members.pkl (which Person nodes are one committee member; checked against COMMITTEE_MEMBER), config/guidelines_analysis_sets.csv
       (analysis set, title year, lecture threshold), work/expansion/society_rank.csv, work/stage18/report_numbers.pkl (group society of each guideline),
       work/census3/report_numbers.pkl (issuing societies; checked against ISSUED_BY), out/RESULTS_LEDGER.csv (block 6, for the code check);
       for checks only: the rosters behind the official numbers (roster_v3.csv of the runs, set comparison of in-scope members, nothing printed)
Writes out/two_channels.md, work/stage19/two_channels.pkl (aggregate numbers only)
Definitions (CC_PROMPT_stage19.md, 步骤 A):
  members  = the guideline's committee members in disclosure scope (in_scope 是, or 不明 and listed in the COI file = the official numbers' rule);
             a member linked to two Person nodes is one member (payments of both nodes summed)
  window   = the guideline's audit years (Guideline.audit_year_first..last), payment data up to 2023
  set A    = companies (merged nodes) that paid one member a lecture fee in one window year of at least the audit threshold
             (max of 50 万 and the guideline's lecture threshold of rule 2)
  set B    = companies that paid the issuing societies (every ISSUED_BY society; itself, its branches / regional meetings = Org nodes whose parent is it,
             and its meetings, mapped to the society node) society donations or co-sponsorship (category 学会捐赠 / 学会共同举办, as stage 7) in the window
  amounts  = those payments to the issuing societies in the window; from A = paid by companies in A
  industry = the company node's primary industry (pharma / device); every quantity again within each industry
  sensitivity 1: A = any individual payment (any category, no threshold); sensitivity 2: window = title year -3 .. -1 (payment data up to 2023)
Pooled = guideline x company pairs and amounts added over the guidelines (a society's payments in overlapping windows count once per guideline).
Proportions of counts with Wilson 95% CI; amount shares are not counts and get no CI. Medians and quartiles (numpy linear) over guidelines with a
non-zero denominator. Descriptive; no test. Prints counts only.
"""
import pandas as pd, numpy as np, sys, pathlib, math, json, time

P = pathlib.Path(sys.argv[1]); KG = P/"kg"; W20 = P/"work"/"stage20"; W20.mkdir(parents=True, exist_ok=True)      # stage 20: the pickle goes to work/stage20 (stage 19's is kept)
rd = lambda p: pd.read_csv(p, dtype=str, keep_default_na=False, encoding="utf-8-sig")
AS = rd(P/"config"/"guidelines_analysis_sets.csv").set_index("key")
GL = pd.read_parquet(KG/"nodes"/"guideline.parquet").set_index("guideline_id")
CO = pd.read_parquet(KG/"nodes"/"company.parquet").set_index("company_id"); PRIM = CO.industry_primary
ORG = pd.read_parquet(KG/"nodes"/"org.parquet", columns=["org_id", "org_type", "parent_org_id"])
SOC = pd.read_parquet(KG/"nodes"/"society.parquet").set_index("society_id")
CM = pd.read_parquet(KG/"edges"/"committee_member.parquet")
PP = pd.read_parquet(KG/"edges"/"paid_person.parquet", columns=["src_id", "dst_id", "year", "category", "amount"])
PO = pd.read_parquet(KG/"edges"/"paid_org.parquet", columns=["src_id", "dst_id", "year", "category", "amount"])
IB = pd.read_parquet(KG/"edges"/"issued_by.parquet")
MEM = pd.read_pickle(P/"work"/"kg_build_v07"/"members.pkl")
RANK = rd(P/"work"/"expansion"/"society_rank.csv"); SNAME = dict(zip(RANK.society_id, RANK.name))
SNAME.update({k: v for k, v in SOC.name.items() if k not in SNAME})
N18 = pd.read_pickle(P/"work"/"stage18"/"report_numbers.pkl"); GSOC = {k: v["soc"] for k, v in N18["NUM"]["B7"].items()}
RN = pd.read_pickle(P/"work"/"census3"/"report_numbers.pkl")
LAST = 2023; CH2 = ["学会捐赠", "学会共同举办"]; IND = {"all": "全部企业", "pharma": "制药为主", "device": "器械为主"}
SETS = {"主分析集": [k for k in N18["MAIN"]], "期间推定层": [k for k in N18["INF"]]}
KEYS = SETS["主分析集"] + SETS["期间推定层"]; SETS["全部"] = KEYS
CHECK = []


def wilson(k, n, z=1.959963984540054):
    p = k / n; d = 1 + z * z / n; c = (p + z * z / (2 * n)) / d; h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return p, max(0.0, c - h), min(1.0, c + h)
fmt = lambda k, n: (lambda p, lo, hi: f"{p:.2f}，95% CI [{lo:.2f}, {hi:.2f}]（{k:,}/{n:,}）")(*wilson(k, n)) if n else "—（0）"
man = lambda x: f"{x / 1e4:,.0f}"
shr = lambda a, t: f"{a / t:.2f}" if t > 0 else "—"


def mq(v):
    v = [x for x in v if x is not None]
    if not v: return "—（0 部）"
    q1, q2, q3 = np.percentile(v, [25, 50, 75])
    return f"{q2:.2f}（四分位距 {q1:.2f}–{q3:.2f}，{len(v)} 部）"


# ---------------------------------------------------------------- checks on the inputs
assert len(KEYS) == 73 and len(SETS["主分析集"]) == 48 and len(SETS["期间推定层"]) == 25
assert all(AS.loc[k, "analysis_set"] == s for s in ("主分析集", "期间推定层") for k in SETS[s])
assert set(zip(CM.src_id, CM.dst_id)) == {(i, g) for g, v in zip(MEM.guideline_id, MEM.node_ids) for i in v}
CHECK.append("`work/kg_build_v07/members.pkl` 的委员与节点的对应和图谱的 COMMITTEE_MEMBER 边完全相同（用它把连到两个节点的委员算一人）。")
ISS = {k: sorted(IB.loc[IB.src_id == k, "dst_id"]) for k in KEYS}
assert all(ISS[k] == sorted(RN["ISS"][k]) for k in KEYS)
CHECK.append("每部指南的发行学会（ISSUED_BY）与审计结果定版所用的发行学会相同（73/73）。")
MEM["scope"] = (MEM.in_scope == "是") | ((MEM.in_scope == "不明") & MEM.listed)

# the in-scope members are the ones of the official numbers (census rosters; names compared as sets, nothing printed)
NEW13 = set(RN["new13"]); RR = rd(P/"work"/"stage14"/"rerun_keys.csv").set_index("key")
E1 = set(rd(P/"work"/"errata"/"keys.csv").key); E2 = {"liver_2021", "jds_dm_2024"}; E3 = set(rd(P/"census3_errata_root"/"config"/"guidelines_v3_1.csv").key)
def vdir(k):
    if k in RR.index: return P/"stage14_root"/"work"/"gl_v3_1"/k
    if k in NEW13: return P/("census3_errata_root" if k in E3 else "census3_root")/"work"/"gl_v3_1"/k
    if k in E2: return P/"errata2_root"/"work"/"gl_v3_1"/k
    if k in E1: return P/"errata_root"/"work"/"gl_v3_1"/k
    return P/"work"/"gl_v3_1"/k
same = 0; ev_off = []
for k in KEYS:
    RV = rd(vdir(k)/"roster_v3.csv"); ev = set(RV[(RV.in_scope == "是") | ((RV.in_scope == "不明") & (RV.listed == "True"))].nm)
    m = MEM[MEM.guideline_id == k]; same += set(m[m.scope].nm) == ev
    if set(m[m.evaluable].nm) != set(m[m.scope].nm): ev_off.append(k)
assert same == 73
n_scope = int(sum(MEM[MEM.guideline_id == k].scope.sum() for k in KEYS))
CHECK.append(f"开示范围内的委员：73 部合计 {n_scope:,} 人次，每部与审计结果定版（正式数）所用的范围内委员逐部相同（73/73）。"
             + (f"图谱的 evaluable_v3_1 列与此不同的有 {len(ev_off)} 部（" + "、".join(f"`{k}`" for k in ev_off) + "：图谱构建时这部记为非个人别开示，范围内的委员全部记为不可评价；"
                "审计结果定版按范围内算）。本轮按 in_scope 列取，与正式数一致；图谱不改。" if ev_off else ""))
for k in KEYS:
    g = GL.loc[k]; assert g.analysis_set == AS.loc[k, "analysis_set"]
WIN = {k: [y for y in range(int(GL.loc[k, "audit_year_first"]), int(GL.loc[k, "audit_year_last"]) + 1) if y <= LAST] for k in KEYS}
WIN2 = {k: [y for y in range(int(AS.loc[k, "title_year"]) - 3, int(AS.loc[k, "title_year"])) if y <= LAST] for k in KEYS}
THR = {k: max(500_000.0, float(AS.loc[k, "lecture_threshold_man"]) * 1e4) for k in KEYS}
assert all(PRIM.isin(["pharma", "device"]))

# targets of channel 2: the issuing societies, their branches / regional meetings (parent = the society); meetings are on the society node already
TGT = {k: set(ISS[k]) | set(ORG.loc[ORG.parent_org_id.isin(ISS[k]), "org_id"]) for k in KEYS}
for k in KEYS: assert all(ORG.set_index("org_id").loc[sorted(TGT[k] - set(ISS[k])), "org_type"] == "支部或地方会")
PPl = PP[PP.category == "讲演"]
POc = PO[PO.category.isin(CH2)]


def members(k):
    m = MEM[(MEM.guideline_id == k) & MEM.scope].reset_index(drop=True)
    return {pid: i for i, ids in enumerate(m.node_ids) for pid in ids}, len(m)


def one(k, mode="main"):
    """mode: main | any (sensitivity 1) | win2 (sensitivity 2) | allcat (sensitivity 3, stage 20: channel 2 = every category of institutional payment)"""
    yrs = WIN2[k] if mode == "win2" else WIN[k]; pid2m, nm_ = members(k)
    src = PP if mode == "any" else PPl
    x = src[src.dst_id.isin(pid2m) & src.year.isin(yrs)].copy(); x["m"] = x.dst_id.map(pid2m)
    if mode == "any":
        A = set(x.src_id)
    else:
        s = x.groupby(["src_id", "m", "year"]).amount.sum()
        A = set(s[s >= THR[k]].index.get_level_values(0))
    src2 = PO if mode == "allcat" else POc
    y = src2[src2.dst_id.isin(TGT[k]) & src2.year.isin(yrs)]
    s2 = y.groupby("src_id").amount.sum(); B = set(s2[s2 > 0].index)
    out = dict(years=yrs, members=nm_, n_targets=len(TGT[k]), n_socs=len(ISS[k]))
    for ind in IND:
        f = (lambda c: True) if ind == "all" else (lambda c, ind=ind: PRIM[c] == ind)
        a = {c for c in A if f(c)}; b = {c for c in B if f(c)}
        yy = y if ind == "all" else y[y.src_id.map(PRIM) == ind]
        tot = float(yy.amount.sum()); fa = float(yy[yy.src_id.isin(a)].amount.sum())
        out[ind] = dict(A=len(a), AB=len(a & b), B=len(b), total=tot, fromA=fa)
    return out


MODES = ("main", "any", "win2", "allcat")
RES = {mode: {k: one(k, mode) for k in KEYS} for mode in MODES}


def pool(keys, mode, ind):
    R = [RES[mode][k][ind] for k in keys]
    a, ab, b, t, fa = (sum(r[x] for r in R) for x in ("A", "AB", "B", "total", "fromA"))
    return dict(A=a, AB=ab, B=b, total=t, fromA=fa,
                med_ab_a=mq([r["AB"] / r["A"] if r["A"] else None for r in R]), med_ab_b=mq([r["AB"] / r["B"] if r["B"] else None for r in R]),
                med_share=mq([r["fromA"] / r["total"] if r["total"] > 0 else None for r in R]), n=len(keys))


POOL = {mode: {s: {ind: pool(ks, mode, ind) for ind in IND} for s, ks in SETS.items()} for mode in MODES}
SOCS = [s for s in list(RANK.society_id) if any(s in ISS[k] for k in KEYS)] + sorted({s for k in KEYS for s in ISS[k]} - set(RANK.society_id))
SOCK = {s: [k for k in KEYS if s in ISS[k]] for s in SOCS}
SOCP = {s: {ind: pool(SOCK[s], "main", ind) for ind in IND} for s in SOCS}
FRAME = set(RANK.society_id); NONF = [s for s in SOCS if s not in FRAME]                 # stage 20: co-issuing societies outside the 25 sampled
NFK = [k for k in KEYS if any(s not in FRAME for s in ISS[k])]                           # guidelines with at least one of them, each once
NFP = {ind: pool(NFK, "main", ind) for ind in IND}

# ---------------------------------------------------------------- code check: sensitivity 1 = the dual channel of stages 9 / 11 (ledger block 6)
LG = rd(P/"out"/"RESULTS_LEDGER.csv"); old = LG[LG["块"] == "6 双通道与归并率"]
cmp_ = []
for r in old.itertuples():
    k = r.说明.split("（`")[1].split("`）")[0] if "（`" in r.说明 else None
    if k not in RES["main"]: continue
    m = __import__("re").search(r"（(\d+)/(\d+)）", r.数值); both, paid = int(m.group(1)), int(m.group(2))
    rr = RES["any"][k]["all"]; cmp_.append((k, (both, paid) == (rr["AB"], rr["A"])))
n_cmp, n_same = len(cmp_), sum(v for _, v in cmp_)
CHECK.append(f"代码对照：敏感性一（任何个人付款，不设门槛）就是第 9、11 阶段双通道的定义。73 部里有旧数的 {n_cmp} 部（台账第 6 块），按本轮的代码重算「两条通道都有 / 付过委员的企业」"
             f"与旧数相同的 {n_same} 部" + ("（全部相同）。" if n_same == n_cmp else "；不同的：" + "、".join(f"`{k}`" for k, v in cmp_ if not v) + "。"))
oth = PO[~PO.category.isin(CH2)]
o_amt = sum(float(oth[oth.dst_id.isin(TGT[k]) & oth.year.isin(WIN[k])].amount.sum()) for k in KEYS)
o_n = sum(int((oth.dst_id.isin(TGT[k]) & oth.year.isin(WIN[k])).sum()) for k in KEYS)
T0, T3 = POOL["main"]["全部"]["all"]["total"], POOL["allcat"]["全部"]["all"]["total"]
assert abs((T3 - T0) - o_amt) < 1, "sensitivity 3 minus the official total must be the other categories"
allcat_diff = dict(amount=o_amt, share=o_amt / T0, edges=o_n, official=T0, allcat=T3)
lec_off = [k for k in KEYS if AS.loc[k, "lecture_item"] != "是"]
thr100 = [k for k in KEYS if THR[k] > 500_000]
part = [k for k in KEYS if int(GL.loc[k, "audit_year_last"]) > LAST]

# ---------------------------------------------------------------- markdown
TITLE = {k: AS.loc[k, "title"] for k in KEYS}
def order(keys):
    so = {s: j for j, s in enumerate(list(RANK.society_id) + sorted(set(GSOC.values()) - set(RANK.society_id)))}
    return sorted(keys, key=lambda k: (so.get(GSOC[k], 99), -int(AS.loc[k, "title_year"]), k))
L = ["# 两条通道：73 部指南（主分析集 48、期间推定层 25）", "",
     f"生成脚本：`scripts/120_two_channels.py`。生成日期：{time.strftime('%Y-%m-%d')}。只读图谱 v0.8（没有改）；委员名单和开示范围是冻结流程的模型抽取，**未经人工核对**。只含汇总数、企业数、金额、学会名、指南名；是描述，不做检验，不下结论。", "",
     "## 定义", "",
     "- 委员：该指南开示范围内的委员（in_scope 为「是」，或「不明」且列在开示文件里；与审计结果定版的正式数同一口径，日本循環器学会的外部評価委員按流程的判定）。一人连到两个 Person 节点时算一人，两个节点的付款相加。",
     f"- 窗口：该指南的审计年份（图谱 Guideline 的 audit_year_first 到 audit_year_last）；付款数据只到 {LAST} 年，窗口里 {LAST} 年以后的年份没有数据（{len(part)} 部的窗口有这样的年份）。个人付款制药 2016 年起、器械 2019 年起；机构付款制药 2017 年起、器械 2019 年起。",
     f"- 集合 A：窗口内给委员付过讲演费、且某一委员某一年从这家企业收到的讲演费合计不低于该指南的审计门槛的企业（门槛 = 50 万日元与规则第二条的讲演费门槛中较高的；高于 50 万的 {len(thr100)} 部：" + "、".join(f"`{k}` {THR[k]/1e4:g} 万" for k in thr100) + "）。"
     + (f"开示项目不含讲演费的 {len(lec_off)} 部也照算（集合 A 只看付款）：" + "、".join(f"`{k}`" for k in lec_off) + "。" if lec_off else ""),
     "- 集合 B：窗口内给发行学会付过学会捐赠或学会共同举办费的企业。发行学会 = ISSUED_BY 连到的全部学会（合办的各学会合起来）；口径同第 7 阶段：学会本身、它的支部和地方会（上级为该学会的 Org 节点）、它主办的学术集会（归并时已对到学会节点）。",
     f"- 学会付款合计：窗口内企业给这些收款方的学会捐赠和学会共同举办费；其中来自 A 的 = 付款企业在集合 A 里的部分。同一窗口内对这些收款方的其他类别的机构付款（奖学捐赠、一般捐赠、其他）不在口径内：73 部合计 {o_n:,} 条边、{man(o_amt)} 万日元。",
     "- 企业按图谱的合并节点（同名组算一家）；制药为主、器械为主按节点的主行业，各算一遍（A、B、金额都只取该行业的企业）。",
     "- 合并：指南 × 企业的对数和金额在各部指南之间相加（同一学会的几部指南窗口重叠时，学会的付款按指南各算一次）。比例（企业数之比）附 Wilson 95% CI；金额占比不是计数，不附 CI。中位数与四分位距按各部指南的比例（分母为 0 的指南不算），numpy 的线性插值。",
     "- 敏感性一：集合 A 改为窗口内给委员付过任何个人付款的企业（任何类别、不设门槛）。敏感性二：窗口统一改为标题年份减 3 到减 1（付款数据只到 2023 年）。"
     "敏感性三（第 20 阶段）：通道二改为窗口内给这些收款方的全部类别的机构付款（学会捐赠、学会共同举办、奖学捐赠、一般捐赠、其他）。",
     f"- 第 20 阶段已定：通道二的正式口径仍是学会捐赠加学会共同举办费（第 7 阶段以来一致），全部类别只作敏感性三；两者的差 = 学会付款合计多 {man(o_amt)} 万日元，为正式口径的 {o_amt / T0:.1%}。"
     "金额占比不附置信区间，论文表里只报各部指南的中位数和四分位距；企业数的比例照旧附 Wilson 区间。本文件的「来自 A 的占比」一列是各部金额相加的合并值，只作参考。", "",
     "## 输入的核对", ""] + [f"- {c}" for c in CHECK] + [""]

def head(extra=""):
    return ["| 集合 | 企业 | 部数 | |A| | |A∩B| | |A∩B| ÷ |A| | |B| | |A∩B| ÷ |B| | 学会付款合计（万日元） | 其中来自 A（万日元） | 来自 A 的占比 |",
            "|---|---|---|---|---|---|---|---|---|---|---|"]
def prow(lab, ind, d):
    return f"| {lab} | {IND[ind]} | {d['n']} | {d['A']:,} | {d['AB']:,} | {fmt(d['AB'], d['A'])} | {d['B']:,} | {fmt(d['AB'], d['B'])} | {man(d['total'])} | {man(d['fromA'])} | {shr(d['fromA'], d['total'])} |"
L += ["## 合计", "", "合并后的比例（指南 × 企业的对数相加）。", ""] + head()
for s in SETS:
    for ind in IND: L += [prow(s, ind, POOL["main"][s][ind])]
L += ["", "## 各部指南比例的中位数与四分位距", "", "| 集合 | 企业 | |A∩B| ÷ |A| | |A∩B| ÷ |B| | 来自 A 的占比 |", "|---|---|---|---|---|"]
for s in SETS:
    for ind in IND:
        d = POOL["main"][s][ind]; L += [f"| {s} | {IND[ind]} | {d['med_ab_a']} | {d['med_ab_b']} | {d['med_share']} |"]
L += ["", "## 敏感性", "", "敏感性一 = 集合 A 改为任何个人付款（不设门槛）；敏感性二 = 窗口统一改为标题年份减 3 到减 1；敏感性三 = 通道二改为全部类别的机构付款（第 20 阶段）。合并的做法同上。", "",
      "| 敏感性 | 集合 | 企业 | 部数 | |A| | |A∩B| | |A∩B| ÷ |A| | |B| | |A∩B| ÷ |B| | 学会付款合计（万日元） | 其中来自 A（万日元） | 来自 A 的占比 | 来自 A 的占比：中位数（四分位距） |",
      "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
for mode, lab in (("any", "敏感性一"), ("win2", "敏感性二"), ("allcat", "敏感性三")):
    for s in SETS:
        for ind in IND:
            d = POOL[mode][s][ind]
            L += [f"| {lab} | {s} | {IND[ind]} | {d['n']} | {d['A']:,} | {d['AB']:,} | {fmt(d['AB'], d['A'])} | {d['B']:,} | {fmt(d['AB'], d['B'])} | {man(d['total'])} | {man(d['fromA'])} | {shr(d['fromA'], d['total'])} | {d['med_share']} |"]
chg = [k for k in KEYS if WIN2[k] != WIN[k]]
L += ["", f"敏感性二改变窗口的指南 {len(chg)} 部（主分析集 {sum(k in SETS['主分析集'] for k in chg)}、期间推定层 {sum(k in SETS['期间推定层'] for k in chg)}）；其余的审计年份本来就是标题年份减 3 到减 1。",
      f"敏感性三与正式口径的差（全部 73 部，全部企业）：学会付款合计 {man(T3)} 万日元对 {man(T0)} 万日元，多 {man(o_amt)} 万日元（正式口径的 {o_amt / T0:.1%}；{o_n:,} 条边）。", ""]
L += ["## 每个学会", "", "按发行学会合并：一部合办的指南在每个发行学会下各算一次（所以各学会的行加起来多于合计）；每部指南的集合 B 和学会付款仍是合办的各学会合起来。73 部全部（主分析集和期间推定层）。", "",
      "| 学会 | 企业 | 指南数（主分析集 / 期间推定层） | |A| | |A∩B| | |A∩B| ÷ |A| | |B| | |A∩B| ÷ |B| | 学会付款合计（万日元） | 其中来自 A（万日元） | 来自 A 的占比 | 来自 A 的占比：中位数（四分位距） |",
      "|---|---|---|---|---|---|---|---|---|---|---|---|"]
for s in SOCS:
    ks = SOCK[s]; nm_ = sum(k in SETS["主分析集"] for k in ks)
    for ind in IND:
        d = SOCP[s][ind]
        L += [f"| {SNAME.get(s, s)} | {IND[ind]} | {len(ks)}（{nm_} / {len(ks) - nm_}） | {d['A']:,} | {d['AB']:,} | {fmt(d['AB'], d['A'])} | {d['B']:,} | {fmt(d['AB'], d['B'])} | {man(d['total'])} | {man(d['fromA'])} | {shr(d['fromA'], d['total'])} | {d['med_share']} |"]
L += [""]
L += ["## 合办学会合计", "", f"选样的 25 个学会以外的合办学会 {len(NONF)} 个；有其中至少一个学会合办的指南 {len(NFK)} 部（主分析集 {sum(k in SETS['主分析集'] for k in NFK)}、期间推定层 {sum(k in SETS['期间推定层'] for k in NFK)}），每部只算一次，合并的做法同上（第 20 阶段）。", "",
      "| 集合 | 企业 | 部数 | |A| | |A∩B| | |A∩B| ÷ |A| | |B| | |A∩B| ÷ |B| | 学会付款合计（万日元） | 其中来自 A（万日元） | 来自 A 的占比 | 来自 A 的占比：中位数（四分位距） |",
      "|---|---|---|---|---|---|---|---|---|---|---|---|"]
for ind in IND:
    d = NFP[ind]; L += [f"| 合办学会（{len(NONF)} 个）合计 | {IND[ind]} | {d['n']} | {d['A']:,} | {d['AB']:,} | {fmt(d['AB'], d['A'])} | {d['B']:,} | {fmt(d['AB'], d['B'])} | {man(d['total'])} | {man(d['fromA'])} | {shr(d['fromA'], d['total'])} | {d['med_share']} |"]
L += [""]
for ind in IND:
    L += [f"## 每部指南：{IND[ind]}", "", "| 指南 | 分析集 | 主学会 | 窗口 | 发行学会数 / 收款方节点数 | 范围内委员 | |A| | |A∩B| | |A∩B| ÷ |A| | |B| | |A∩B| ÷ |B| | 学会付款合计（万日元） | 其中来自 A（万日元） | 来自 A 的占比 |",
          "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for s in SETS:
        if s == "全部": continue
        for k in order(SETS[s]):
            r = RES["main"][k]; d = r[ind]; w = f"{r['years'][0]}–{r['years'][-1]}" if r["years"] else "—"
            L += [f"| {TITLE[k]}（`{k}`） | {s} | {SNAME.get(GSOC[k], GSOC[k])} | {w} | {r['n_socs']} / {r['n_targets']} | {r['members']} | {d['A']:,} | {d['AB']:,} | {fmt(d['AB'], d['A'])} | {d['B']:,} | {fmt(d['AB'], d['B'])} | {man(d['total'])} | {man(d['fromA'])} | {shr(d['fromA'], d['total'])} |"]
    L += [""]
L += ["主学会只用于排序（日本循環器学会合办的算日本循環器学会）。窗口一列是落在付款数据里的年份。", ""]
(P/"out"/"two_channels.md").write_text("\n".join(L), encoding="utf-8")
pd.to_pickle(dict(RES=RES, POOL=POOL, SOCP=SOCP, SOCS=SOCS, SOCK=SOCK, NONF=NONF, NFK=NFK, NFP=NFP, allcat_diff=allcat_diff, SETS=SETS, KEYS=KEYS, GSOC=GSOC, WIN=WIN, WIN2=WIN2, THR=THR, checks=CHECK,
                  n_cmp=n_cmp, n_same=n_same, other_amt=o_amt, other_n=o_n, ev_off=ev_off, changed_win2=chg), W20/"two_channels.pkl")
for s in SETS:
    for ind in IND:
        d = POOL["main"][s][ind]
        print(s, ind, "A", d["A"], "AB", d["AB"], "B", d["B"], "AB/A", round(d["AB"] / d["A"], 3) if d["A"] else None, "AB/B", round(d["AB"] / d["B"], 3) if d["B"] else None,
              "share", round(d["fromA"] / d["total"], 3) if d["total"] else None, "| median share", d["med_share"])
print("code check (sens 1 vs block 6):", n_same, "/", n_cmp, "| other categories to targets:", o_n, "edges", round(o_amt / 1e4), "万 | ev_off", ev_off, "| win2 changed", len(chg))
