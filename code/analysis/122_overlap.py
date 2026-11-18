# -*- coding: utf-8 -*-
"""Stage 19, step C: pharma / device overlap among the committee members of the 73 guidelines (main 48, period-inferred 25), 2019-2023, graph v0.8 only.
Usage: python 122_overlap.py "<project>"
Reads  kg/edges/{paid_person, committee_member, board_member}.parquet, kg/nodes/guideline.parquet (v0.8, not changed), work/kg_build_v07/members.pkl,
       work/kg_build_v02/board.pkl (the 2021 board list of stage 7), work/stage18/report_numbers.pkl (the two sets), work/errata/overlap27.pkl and
       out/RESULTS_LEDGER.csv block 7 (code check only)
Writes out/overlap.md, work/stage19/overlap.pkl (aggregate numbers only)
Definitions (CC_PROMPT_stage19.md, 步骤 C; overlap as stages 7, 8, 11): members = the members of step A (in disclosure scope), one person per person key:
the Person nodes of the members are joined into one person when one member row links them (a member linked to two nodes) — connected components
over all member rows of the set, so a person on several guidelines counts once. A person overlaps in a year when he or she received an individual
payment that year from a pharma-primary company and from a device-primary company (same-name groups as one company, primary industry);
denominator = persons paid by either that year. Years without personal numbers (pharma 2022, device 2023) are marked; their persons are entities
inferred by rule. Controls: everyone paid that year (one Person node each); the 2021 board list of stage 7 (BOARD_MEMBER, the same list).
Proportions with Wilson 95% CI; descriptive, no test. Prints counts only.
"""
import pandas as pd, sys, pathlib, math, time, re

P = pathlib.Path(sys.argv[1]); KG = P/"kg"; W19 = P/"work"/"stage19"; W19.mkdir(parents=True, exist_ok=True)
rd = lambda p: pd.read_csv(p, dtype=str, keep_default_na=False, encoding="utf-8-sig")
PP = pd.read_parquet(KG/"edges"/"paid_person.parquet", columns=["dst_id", "year", "industry_primary"])
CM = pd.read_parquet(KG/"edges"/"committee_member.parquet"); BM = pd.read_parquet(KG/"edges"/"board_member.parquet")
MEM = pd.read_pickle(P/"work"/"kg_build_v07"/"members.pkl"); BD = pd.read_pickle(P/"work"/"kg_build_v02"/"board.pkl")
N18 = pd.read_pickle(P/"work"/"stage18"/"report_numbers.pkl")
SETS = {"主分析集": list(N18["MAIN"]), "期间推定层": list(N18["INF"])}; SETS["全部"] = SETS["主分析集"] + SETS["期间推定层"]
YRS = [2019, 2020, 2021, 2022, 2023]; DAG = {2022: "†", 2023: "‡"}
CHECK = []


def wilson(k, n, z=1.959963984540054):
    p = k / n; d = 1 + z * z / n; c = (p + z * z / (2 * n)) / d; h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return p, max(0.0, c - h), min(1.0, c + h)
fmt = lambda k, n: (lambda p, lo, hi: f"{p:.2f}，95% CI [{lo:.2f}, {hi:.2f}]（{k:,}/{n:,}）")(*wilson(k, n)) if n else "—（0）"

assert len(SETS["全部"]) == 73
assert set(zip(CM.src_id, CM.dst_id)) == {(i, g) for g, v in zip(MEM.guideline_id, MEM.node_ids) for i in v}
assert set(zip(BM.src_id, BM.dst_id)) == {(i, s) for ss, v in zip(BD.societies, BD.node_ids) for s in ss for i in v}
CHECK.append("委员与节点的对应（`work/kg_build_v07/members.pkl`）和图谱的 COMMITTEE_MEMBER 边完全相同；理事名单（`work/kg_build_v02/board.pkl`，第 7 阶段）和图谱的 BOARD_MEMBER 边完全相同。")
MEM["scope"] = (MEM.in_scope == "是") | ((MEM.in_scope == "不明") & MEM.listed)
pind = PP.groupby(["year", "industry_primary"]).dst_id.agg(set)


def components(node_sets):
    par = {}
    def f(x):
        while par.setdefault(x, x) != x: par[x] = par[par[x]]; x = par[x]
        return x
    for s in node_sets:
        s = list(s)
        for x in s[1:]: par[f(x)] = f(s[0])
        if s: f(s[0])
    g = {}
    for x in par: g.setdefault(f(x), set()).add(x)
    return list(g.values())


def ratio(groups, y):
    ph, dv = pind.get((y, "pharma"), set()), pind.get((y, "device"), set())
    return sum(1 for s in groups if s & ph and s & dv), sum(1 for s in groups if s & ph or s & dv)


GR = {s: components(MEM[MEM.guideline_id.isin(ks) & MEM.scope].node_ids) for s, ks in SETS.items()}
times = {s: int((MEM.guideline_id.isin(ks) & MEM.scope).sum()) for s, ks in SETS.items()}
GR["全体（该年收过个人付款的全部人）"] = [{p} for p in set(PP.dst_id)]
GR["2021 年的理事（第 7 阶段的名单）"] = components(BD.node_ids)
R = {lab: {y: ratio(g, y) for y in YRS} for lab, g in GR.items()}

# ---------------------------------------------------------------- code checks: the stage-8 rows (ledger block 7) and stage 11's 27 guidelines
LG = rd(P/"out"/"RESULTS_LEDGER.csv"); b7 = LG[LG["块"] == "7 制药与器械的重叠"]
def old(prefix):
    out = {}
    for r in b7.itertuples():
        m = re.match(r"^(\d{4}) 年，" + re.escape(prefix), r.说明)
        if m: k, n = re.search(r"（([\d,]+)/([\d,]+)）", r.数值).groups(); out[int(m.group(1))] = (int(k.replace(",", "")), int(n.replace(",", "")))
    return out
o_all = old("付款表里该年收过个人付款的全部人：同一年"); o_bd = old("基本领域学会理事（2021 年名单")
ok_all = all(R["全体（该年收过个人付款的全部人）"][y] == o_all[y] for y in YRS); ok_bd = all(R["2021 年的理事（第 7 阶段的名单）"][y] == o_bd[y] for y in YRS)
OV27 = pd.read_pickle(P/"work"/"errata"/"overlap27.pkl")
g27 = list({frozenset(v): set(v) for v in MEM[MEM.guideline_id.isin(OV27["order"])].node_ids}.values())          # stage 11's definition: whole roster, frozenset groups
ok27 = all(ratio(g27, y) == OV27["R"]["27 部合计（去重）"][y] for y in YRS)
CHECK.append(f"代码对照：同一段代码重算第 8 阶段的「全体」和「理事」两行（台账第 7 块）5 年 × 2 行{'全部相同' if ok_all and ok_bd else '有不同'}；"
             f"按第 11 阶段的定义（名单上的全部委员、按节点集合去重）重算 27 部合计 5 年{'全部相同' if ok27 else '有不同'}。")
assert ok_all and ok_bd and ok27
multi = {s: sum(1 for g in GR[s] if len(g) > 1) for s in SETS}

L = ["# 制药与器械的重叠：73 部指南的委员（2019–2023 年）", "",
     f"生成脚本：`scripts/122_overlap.py`。生成日期：{time.strftime('%Y-%m-%d')}。只读图谱 v0.8（没有改）；委员名单和开示范围是冻结流程的模型抽取，**未经人工核对**。只含汇总数；是描述，不做检验，不下结论。", "",
     "## 定义", "",
     "- 委员：步骤 A 的委员，即 73 部指南（主分析集 48、期间推定层 25）开示范围内的委员（与审计结果定版的正式数同一口径）。按个人键去重：一个委员连到两个 Person 节点时两个节点算一人；"
     "同一人在几部指南里只算一次（对全部委员行求节点的连通分量）。",
     "- 重叠：一个人在同一年既从制药为主的企业、又从器械为主的企业收到个人付款（任何类别）；同名组按一家企业、按主行业归类，付款只算一次（同第 7、8、11 阶段）。分母 = 该年从任一边收到过个人付款的人。",
     "- 年份是付款年 2019–2023（器械数据从 2019 年起），不按各指南的审计年份截。",
     "- **无编号年份**：† 2022 年的制药、‡ 2023 年的器械没有个人编号，这两年的人为「年内实体按规则推定」。",
     "- 对照：该年收过个人付款的全部人（每个 Person 节点一人）；2021 年的基本领域学会理事（第 7 阶段的名单，按 v3.1 规则连在 2019–2021 年的实体上）。",
     "- 比例附 Wilson 95% CI。", "",
     "## 输入的核对", ""] + [f"- {c}" for c in CHECK] + [
     f"- 委员人次与人数：主分析集 {times['主分析集']:,} 人次 → {len(GR['主分析集']):,} 人；期间推定层 {times['期间推定层']:,} 人次 → {len(GR['期间推定层']):,} 人；全部 {times['全部']:,} 人次 → {len(GR['全部']):,} 人"
     f"（人数含连不上付款表的；连到两个以上节点的人：{multi['主分析集']} / {multi['期间推定层']} / {multi['全部']}）。", "",
     "## 逐年", "",
     "| 群体 | " + " | ".join(f"{y}{DAG.get(y, '')}" for y in YRS) + " |", "|---|" + "---|" * len(YRS)]
LAB = {"主分析集": "主分析集的委员", "期间推定层": "期间推定层的委员", "全部": "全部 73 部的委员"}
for lab in GR:
    L += [f"| {LAB.get(lab, lab)} | " + " | ".join(fmt(*R[lab][y]) for y in YRS) + " |"]
L += ["", "† 2022：制药为年内实体按规则推定；‡ 2023：器械为年内实体按规则推定。", "",
      "## 2021 年（有编号的年份）", "", "| 群体 | 当年收过个人付款的人 | 其中两边都收过 | 比例 |", "|---|---|---|---|"]
for lab in GR:
    k, n = R[lab][2021]; L += [f"| {LAB.get(lab, lab)} | {n:,} | {k:,} | {fmt(k, n)} |"]
L += [""]
(P/"out"/"overlap.md").write_text("\n".join(L), encoding="utf-8")
pd.to_pickle(dict(R=R, persons={s: len(GR[s]) for s in GR}, times=times, checks=CHECK, multi=multi), W19/"overlap.pkl")
for lab in GR: print(lab, {y: f"{R[lab][y][0]}/{R[lab][y][1]}" for y in YRS})
print("checks: stage-8 rows", ok_all, ok_bd, "| 27 pooled", ok27, "| persons", {s: len(GR[s]) for s in SETS})
