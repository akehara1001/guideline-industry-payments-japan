# -*- coding: utf-8 -*-
"""Step 2: cross-year person key.
Usage: python 03_person_key.py "<project>"
Reads  work/C.pkl, config/company_id_map.csv, scripts/ref_aim3_1_units_and_stoppers.py (82 universities + specialty keywords)
Writes work/person_key.pkl (one row per within-year entity: person_id, tier), work/C_keyed.pkl (C + eid, person_id, tier, company_id),
       work/clerical_review_sample.xlsx (names; local only), out/linkage_report.md (aggregate numbers only)

Rules (from CC_PROMPT_stage1.md, step 2)
- Within-year entity: rows with a numeric pidn -> year x ind x pidn. Rows without -> year x ind x nm x institution root.
  Rows whose nm is unusable (empty, or fewer than 2 characters once symbols are removed) cannot be grouped or linked:
  one entity per row, tier "nm欠損".
- Institution root: inst + dept normalised; if the text names one of the 82 medical universities (or an alias) the root is
  that university (this covers its affiliated hospitals); otherwise the institution name (inst, or dept if inst is empty)
  with legal-entity prefixes removed.
- Linking across years and industries only between entities with the same nm. A "slot" is year x industry.
    甲: same nm, same (non-empty) root, and that root is unique for the nm in both slots.
    乙: same nm, different roots, and the nm has exactly one entity in each of the two slots.
    丙: everything else with the same nm. Pick the candidate whose specialty keywords overlap; if several overlap, the one
        whose title category also overlaps. A link needs the choice to be unique from both sides. Otherwise no link,
        and the entity is flagged (丙未判别).
- Hard constraint: a person never holds two entities of the same slot (so two different numbers of the same nm in one
  year and industry are never merged). Links are applied 甲 -> 乙 -> 丙, nearer years first; a link that would break
  the constraint is skipped.
Stage 2 changes (CC_PROMPT_stage2.md, A2-A3)
- A2 pharma 2023: 氏名No was numbered per original spelling, not per person. The within-year entity there is
  year x industry x normalised dup (「氏名（同姓同名）設定」, same name / different person carry a, b, c ... suffixes).
  The hard constraint in that slot therefore runs on dup: two different dup values of one nm are two entities of one slot.
- A3 no-number slots (pharma 2022, device 2023): if an nm has exactly one entity in every adjacent numbered year
  (pharma 2021 and 2023, device 2022), all its rows in the no-number year form one entity; otherwise nm x root as before.
  The rule is first validated on a numbered year (pharma 2021 with 2020/2023, device 2022 with 2021) against the
  numbers, side by side with the nm x root rule; it is not adopted for an industry whose precision drops by more than 0.03.
Stage 4 change (CC_PROMPT_stage4.md, A2)
- The kanji-variant folding table is extended with config/kanji_variant_pairs.csv (one-to-one pairs learned from the payment
  data's original vs new-form spellings, >= 5 spelling pairs) and nm is recomputed from the name columns with it.
The script prints aggregate numbers only.
"""
import pandas as pd, numpy as np, re, sys, unicodedata, ast, pathlib, time

_REF = pathlib.Path(__file__).with_name("ref_aim3_1_units_and_stoppers.py").read_text(encoding="utf-8")
UNIV = ast.literal_eval(re.search(r"^UNIV=(\{.*?\})$", _REF, re.M).group(1))
SPEC = ast.literal_eval(re.search(r"^SPEC=(\[.*?\])\nSPEC=", _REF, re.M | re.S).group(1))
SPEC_LABELS = [k for k, _ in SPEC]
SPEC_RX = [re.compile(p) for _, p in SPEC]
_PAT = sorted([(u, a) for u, al in UNIV.items() for a in [u] + al], key=lambda x: -len(x[1]))
_URX = re.compile("|".join(re.escape(a) for _, a in _PAT)); _AMAP = {a: u for u, a in _PAT}
LEGAL = re.compile(r"^(?:国立大学法人|公立大学法人|学校法人|独立行政法人|地方独立行政法人|国立研究開発法人|一般財団法人|公益財団法人"
                   r"|一般社団法人|公益社団法人|社会医療法人財団|社会医療法人社団|社会医療法人|特定医療法人社団|特定医療法人財団|特定医療法人"
                   r"|医療法人社団|医療法人財団|医療法人|社会福祉法人|宗教法人|特定非営利活動法人|NPO法人|株式会社|有限会社|合同会社|一般財団|公益財団"
                   r"|\((?:医|医社|医財|社|財|独|学|福|公財|一財|公社|一社|株|有|特医|社医)\))+")
TITLE = [("名誉教授", r"名誉教授"), ("特任教授等", r"(?:特任|客員|臨床|招へい|招聘|特命|兼任|連携|寄附講座)教授"), ("准教授", r"准教授|助教授"),
         ("教授", r"教授"), ("講師", r"講師"), ("助教", r"助教|助手"), ("理事長", r"理事長"), ("副院長", r"副院長"), ("院長", r"院長"),
         ("センター長", r"センター長"), ("部長", r"部長"), ("科長", r"科長"), ("医長", r"医長"), ("医員", r"医員|レジデント|専攻医"),
         ("室長", r"室長"), ("所長", r"所長"), ("主任", r"主任"), ("医師", r"医師")]
TITLE_RX = [re.compile(p) for _, p in TITLE]
TIER_RANK = {"甲": 0, "乙": 1, "丙": 2}
DUP_SLOTS = {("pharma", 2023)}                                     # A2: entity = normalised dup
NOPID_ADJ = {("pharma", 2022): (2021, 2023), ("device", 2023): (2022,)}   # A3: no-number slot -> adjacent numbered years
VALID_ADJ = {("pharma", 2021): (2020, 2023), ("device", 2022): (2021,)}   # A3: validation slot -> adjacent years
MAX_PREC_DROP = 0.03
SAMPLE_SEED = 20261011


def nk(s):
    return "" if s is None or (isinstance(s, float) and np.isnan(s)) else re.sub(r"[\s　]+", "", unicodedata.normalize("NFKC", str(s)))


VAR = str.maketrans("髙﨑嶋嶌邉邊濵濱栁國德瀨黑齋齊龍澤眞廣", "高崎島島辺辺浜浜柳国徳瀬黒斎斉竜沢真広")
# Stage 4 (A2): the base table is extended with the one-to-one pairs learned from the payment data's own original vs
# new-form spellings (config/kanji_variant_pairs.csv, built by 12_kanji_variant_pairs.py). nm is recomputed in main().
_KV = pathlib.Path(__file__).resolve().parent.parent/"config"/"kanji_variant_pairs.csv"
if _KV.exists():
    _kv = pd.read_csv(_KV, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    VAR.update({ord(a): b for a, b in zip(_kv.raw, _kv.new) if len(a) == 1 and len(b) == 1})


def norm_name(s):
    """Same normalisation as nm in 01_build_tables.py."""
    return nk(s).translate(VAR)


def nm_usable(nm):
    return len(re.sub(r"[-ー―‐*＊・.\s]", "", nm or "")) >= 2


def univ(text):
    m = _URX.search(text)
    return _AMAP[m.group(0)] if m else None


def inst_root(inst, dept):
    a, b = nk(inst), nk(dept)
    u = univ(a + b)
    if u: return "U:" + u
    base = LEGAL.sub("", a if a else b)
    return ("I:" + base) if base else ""


def spec_bit(text):
    for i, rx in enumerate(SPEC_RX):
        if rx.search(text): return 1 << i
    return 0


def title_bit(t):
    t = nk(t)
    for i, rx in enumerate(TITLE_RX):
        if rx.search(t): return 1 << i
    return 0


def bits_to_labels(b, labels):
    return "|".join(l for i, l in enumerate(labels) if b >> i & 1)


def pair_counts(df, true_col, pred_cols):
    """Pairwise precision/recall of grouping pred_cols against true_col (row pairs)."""
    c2 = lambda n: (n * (n - 1) / 2).sum()
    tp = c2(df.groupby([true_col] + pred_cols).size().astype(float))
    pred = c2(df.groupby(pred_cols).size().astype(float)); true = c2(df.groupby(true_col).size().astype(float))
    return tp, pred, true


def main():
    P = pathlib.Path(sys.argv[1]); WORK, CONF, OUT = P/"work", P/"config", P/"out"
    t0 = time.time()
    C = pd.read_pickle(WORK/"C.pkl")
    idm = pd.read_csv(CONF/"company_id_map.csv", dtype=str, keep_default_na=False)
    cmap = {(a, b, c): d for a, b, c, d in idm[["ind", "k", "co"]].assign(cid=idm.company_id).itertuples(index=False)}
    C["company_id"] = [cmap[t] for t in zip(C.ind, C.k, C.co)]
    C["nm"] = C["name"].where(C["name"].notna(), C["name_raw"]).map(norm_name)   # A2: refold with the extended table
    C["nm_ok"] = C.nm.map(nm_usable)
    # institution root, specialty bit, title bit on unique strings
    key = C.inst.fillna("") + "\x1f" + C.dept.fillna("")
    u = pd.Series(key.unique())
    parts = u.str.split("\x1f", n=1, expand=True)
    root_u = [inst_root(a, b) for a, b in zip(parts[0], parts[1])]
    spec_u = [spec_bit(nk(a) + nk(b)) for a, b in zip(parts[0], parts[1])]
    m = pd.DataFrame({"key": u, "root": root_u, "sbit": spec_u}).set_index("key")
    C["root"] = key.map(m.root).values; C["sbit"] = key.map(m.sbit).values.astype("int64")
    tu = pd.Series(C.title.fillna("").unique()); tm = dict(zip(tu, [title_bit(x) for x in tu]))
    C["tbit"] = C.title.fillna("").map(tm).astype("int64")
    print(f"[{time.time()-t0:.0f}s] roots: distinct {m.root.nunique()}, rows with university root {100*C.root.str.startswith('U:').mean():.1f}%,"
          f" empty root {100*(C.root=='').mean():.2f}%, rows with specialty {100*(C.sbit>0).mean():.1f}%, with title category {100*(C.tbit>0).mean():.1f}%")

    # ---- within-year entities ----
    slots = sorted(set(zip(C.ind, C.year)))
    sidx = {s: i for i, s in enumerate(slots)}
    C["slot"] = [sidx[s] for s in zip(C.ind, C.year)]
    # A2: in the dup slots the numbered key is the normalised dup, elsewhere the number
    in_dup = pd.Series([s in DUP_SLOTS for s in zip(C.ind, C.year)], index=C.index)
    C["dn"] = ""
    C.loc[in_dup, "dn"] = C.loc[in_dup, "dup"].map(norm_name)
    use_dup = in_dup & (C.dn != "")
    has_pid = C.pidn.notna() & ~use_dup
    C["nkey"] = np.where(use_dup, "D|" + C.dn, np.where(has_pid, "P|" + C.pidn.astype(str), ""))
    d23 = C[in_dup]
    g_dp = d23[d23.dn != ""].groupby("dn").pidn.nunique()
    dup_stats = dict(rows=len(d23), rows_no_dup=int((d23.dn == "").sum()), n_dup=len(g_dp), dup_multi_pid=int((g_dp > 1).sum()),
                     n_pid=int(d23.pidn.nunique()), pid_multi_dup=int((d23[d23.dn != ""].groupby("pidn").dn.nunique() > 1).sum()),
                     nm_multi_dup=int((d23[d23.nm_ok].groupby("nm").dn.nunique() > 1).sum()),
                     nm_multi_pid=int((d23[d23.nm_ok].groupby("nm").pidn.nunique() > 1).sum()))
    print(f"[{time.time()-t0:.0f}s] A2 dup slots {sorted(DUP_SLOTS)}: {dup_stats}")

    # A3: nm with exactly one numbered entity in every adjacent numbered year
    def uniq_nm(ind, years):
        sets = []
        for y in years:
            d = C[(C.ind == ind) & (C.year == y) & C.nm_ok & (C.nkey != "")]
            g = d.groupby("nm").nkey.nunique()
            sets.append(set(g.index[g == 1]))
        return set.intersection(*sets)
    a3rows = []; adopt = {}
    for (ind, yr), adj in VALID_ADJ.items():
        d = C[(C.ind == ind) & (C.year == yr) & C.nm_ok & C.pidn.notna()]
        q = uniq_nm(ind, adj)
        qm = d.nm.isin(q)
        d = d.assign(k_old=d.nm + "|" + d.root, k_new=np.where(qm, d.nm + "|*", d.nm + "|" + d.root))
        res = {}
        for rule, col in (("old", "k_old"), ("new", "k_new")):
            tp, pred, true = pair_counts(d, "pidn", [col])
            res[rule] = dict(ind=ind, year=yr, adj="、".join(str(a) for a in adj), rule=rule, rows=len(d), n_number=d.pidn.nunique(),
                             nm_qualified=int(d.nm[qm].nunique()), rows_qualified=int(qm.sum()), n_pred=d[col].nunique(),
                             pairs_true=true, pairs_pred=pred, pairs_tp=tp, precision=tp / pred, recall=tp / true)
            a3rows.append(res[rule])
        adopt[ind] = res["new"]["precision"] >= res["old"]["precision"] - MAX_PREC_DROP
        print(f"[{time.time()-t0:.0f}s] A3 validation {ind} {yr} (adjacent {adj}): old P {res['old']['precision']:.4f} R {res['old']['recall']:.4f};"
              f" new P {res['new']['precision']:.4f} R {res['new']['recall']:.4f}; adopt {adopt[ind]}")
    A3V = pd.DataFrame(a3rows)
    in_q = pd.Series(False, index=C.index); a3_apply = {}
    for (ind, yr), adj in NOPID_ADJ.items():
        q = uniq_nm(ind, adj) if adopt[ind] else set()
        mq = (C.ind == ind) & (C.year == yr) & (C.nkey == "") & C.nm_ok & C.nm.isin(q)
        in_q |= mq
        a3_apply[(ind, yr)] = dict(adopted=adopt[ind], nm_qualified=len(q & set(C.nm[mq])), rows=int(mq.sum()),
                                   rows_nopid=int(((C.ind == ind) & (C.year == yr) & (C.nkey == "")).sum()))
    sl = C.slot.astype(str)
    ek = np.where(C.nkey != "", sl + "|" + C.nkey,
                  np.where(in_q, sl + "|M|" + C.nm,
                           np.where(C.nm_ok, sl + "|N|" + C.nm + "|" + C.root, sl + "|R|" + C.index.astype(str))))
    C["ktype"] = np.where(C.nkey != "", np.where(use_dup, "dup", "编号"),
                          np.where(in_q, "nm（相邻年唯一）", np.where(C.nm_ok, "nm×机构根", "nm不可用")))
    C["eid"] = pd.factorize(pd.Series(ek))[0]
    Cok = C[C.nm_ok]
    nmm = Cok.groupby(["eid", "nm"]).size().reset_index(name="c").sort_values(["eid", "c", "nm"], ascending=[True, False, True])
    n_nm = nmm.groupby("eid").size()
    nmm = nmm.drop_duplicates("eid").set_index("eid").nm
    rr = C.groupby(["eid", "root"]).agg(c=("amt", "size"), s=("amt", "sum")).reset_index().sort_values(["eid", "c", "s"], ascending=[True, False, False])
    rr = rr.drop_duplicates("eid").set_index("eid").root
    E = C.groupby("eid").agg(slot=("slot", "first"), ind=("ind", "first"), year=("year", "first"), pidn=("pidn", "first"),
                             ktype=("ktype", "first"), rows=("amt", "size"), amt=("amt", "sum"))
    E["nm"] = nmm.reindex(E.index).fillna("")
    E["nm_ok"] = E.nm != ""
    E["n_nm_spellings"] = n_nm.reindex(E.index).fillna(0).astype(int)
    E["root"] = rr.reindex(E.index)
    E["sbits"] = C[["eid", "sbit"]].drop_duplicates().groupby("eid").sbit.sum().reindex(E.index).astype("int64")
    E["tbits"] = C[["eid", "tbit"]].drop_duplicates().groupby("eid").tbit.sum().reindex(E.index).astype("int64")
    E["has_pid"] = E.ktype.isin(["编号", "dup"])
    print(f"[{time.time()-t0:.0f}s] entities: {len(E)} by key type {E.ktype.value_counts().to_dict()};"
          f" numbered entities with >1 nm spelling: {int((E.has_pid & (E.n_nm_spellings > 1)).sum())}")

    # ---- candidate pairs ----
    Ek = E[E.nm_ok].reset_index()[["eid", "slot", "year", "ind", "nm", "root", "sbits", "tbits"]]
    ns = Ek.groupby("nm").slot.nunique(); Ek = Ek[Ek.nm.map(ns) >= 2]
    n_slot = Ek.groupby(["nm", "slot"]).size()
    n_root = Ek.groupby(["nm", "slot", "root"]).size()
    Pp = Ek.merge(Ek, on="nm", suffixes=("_x", "_y"))
    Pp = Pp[Pp.slot_x < Pp.slot_y].reset_index(drop=True)
    print(f"[{time.time()-t0:.0f}s] candidate pairs (same nm, different slot): {len(Pp)}")
    Pp["n1"] = n_slot.reindex(pd.MultiIndex.from_arrays([Pp.nm, Pp.slot_x])).values
    Pp["n2"] = n_slot.reindex(pd.MultiIndex.from_arrays([Pp.nm, Pp.slot_y])).values
    Pp["m12"] = n_root.reindex(pd.MultiIndex.from_arrays([Pp.nm, Pp.slot_y, Pp.root_x])).fillna(0).values
    Pp["m21"] = n_root.reindex(pd.MultiIndex.from_arrays([Pp.nm, Pp.slot_x, Pp.root_y])).fillna(0).values
    same = (Pp.root_x == Pp.root_y) & (Pp.root_x != "")
    jia = same & (Pp.m12 == 1) & (Pp.m21 == 1)
    yi = ~same & (Pp.n1 == 1) & (Pp.n2 == 1)
    # entities already matched by 甲 into the other slot leave the 丙 pool for that slot
    kx = Pp.eid_x.values.astype(np.int64) * 64 + Pp.slot_y.values; ky = Pp.eid_y.values.astype(np.int64) * 64 + Pp.slot_x.values
    inx = np.isin(kx, kx[jia.values]); iny = np.isin(ky, ky[jia.values])
    cand = ~jia & ~yi & ~inx & ~iny
    Q = Pp[cand].copy()
    Q["so"] = (Q.sbits_x & Q.sbits_y) != 0
    Q["to"] = (Q.tbits_x & Q.tbits_y) != 0
    Q["st"] = Q.so & Q.to
    gL = Q.groupby(["eid_x", "slot_y"]); gR = Q.groupby(["eid_y", "slot_x"])
    cSL, cTL = gL.so.transform("sum"), gL.st.transform("sum")
    cSR, cTR = gR.so.transform("sum"), gR.st.transform("sum")
    chL = Q.so & ((cSL == 1) | ((cSL > 1) & Q.st & (cTL == 1)))
    chR = Q.so & ((cSR == 1) | ((cSR > 1) & Q.st & (cTR == 1)))
    Q["bing"] = chL & chR
    Q["basis"] = np.where((cSL == 1) & (cSR == 1), "专科", "专科+职称")
    # unresolved: had 丙 candidates towards a slot, got no 丙 link there
    linkedL = set(zip(Q.eid_x[Q.bing], Q.slot_y[Q.bing])); linkedR = set(zip(Q.eid_y[Q.bing], Q.slot_x[Q.bing]))
    unresolved = set(e for e, s in zip(Q.eid_x, Q.slot_y) if (e, s) not in linkedL) | set(e for e, s in zip(Q.eid_y, Q.slot_x) if (e, s) not in linkedR)
    L = pd.concat([Pp.loc[jia, ["eid_x", "eid_y", "year_x", "year_y", "slot_x", "slot_y"]].assign(tier="甲", basis="机构根"),
                   Pp.loc[yi, ["eid_x", "eid_y", "year_x", "year_y", "slot_x", "slot_y"]].assign(tier="乙", basis="同名唯一"),
                   Q.loc[Q.bing, ["eid_x", "eid_y", "year_x", "year_y", "slot_x", "slot_y", "basis"]].assign(tier="丙")], ignore_index=True)
    L["rank"] = L.tier.map(TIER_RANK); L["gap"] = (L.year_x - L.year_y).abs()
    L = L.sort_values(["rank", "gap", "year_x", "eid_x", "eid_y"]).reset_index(drop=True)
    print(f"[{time.time()-t0:.0f}s] accepted links: 甲 {int(jia.sum())}, 乙 {int(yi.sum())}, 丙 {int(Q.bing.sum())};"
          f" 丙 candidate pairs {len(Q)}; entities flagged 丙未判别 {len(unresolved)}")

    # ---- constrained union ----
    n = len(E); parent = np.arange(n); mask = np.left_shift(1, E.slot.values.astype(np.int64))
    eidx = {e: i for i, e in enumerate(E.index)}
    par = parent.tolist(); msk = mask.tolist()
    def find(x):
        r = x
        while par[r] != r: r = par[r]
        while par[x] != r: par[x], x = r, par[x]
        return r
    applied = 0; skipped = 0
    for a, b in zip(L.eid_x.map(eidx).values, L.eid_y.map(eidx).values):
        ra, rb = find(a), find(b)
        if ra == rb: continue
        if msk[ra] & msk[rb]: skipped += 1; continue
        if ra < rb: ra, rb = rb, ra
        par[ra] = rb; msk[rb] |= msk[ra]; applied += 1
    roots = np.array([find(i) for i in range(n)])
    E["person_id"] = pd.factorize(roots)[0]
    L["realized"] = roots[L.eid_x.map(eidx).values] == roots[L.eid_y.map(eidx).values]
    print(f"[{time.time()-t0:.0f}s] unions applied {applied}, links skipped by the one-entity-per-slot constraint {skipped},"
          f" links realized {int(L.realized.sum())} of {len(L)}")
    # hard-constraint check: one entity per person and slot; in dup slots one dup, in other numbered slots one number
    per_slot = E.groupby(["person_id", "slot"]).size()
    viol = int((per_slot > 1).sum())
    pid_of_row = E.person_id.reindex(C.eid).values
    viol_dup = int((C.loc[use_dup, ["slot", "dn"]].assign(p=pid_of_row[use_dup.values]).groupby(["p", "slot"]).dn.nunique() > 1).sum())
    viol_pid = int((C.loc[has_pid, ["slot", "pidn"]].assign(p=pid_of_row[has_pid.values]).groupby(["p", "slot"]).pidn.nunique() > 1).sum())
    print(f"[{time.time()-t0:.0f}s] hard constraint: person x slot with >1 entity {viol}; with >1 dup (dup slots) {viol_dup}; with >1 number (other numbered slots) {viol_pid}")

    # ---- entity tier ----
    R = L[L.realized]
    best = pd.concat([R[["eid_x", "rank"]].rename(columns={"eid_x": "eid"}), R[["eid_y", "rank"]].rename(columns={"eid_y": "eid"})]).groupby("eid")["rank"].min()
    anyL = set(L.eid_x) | set(L.eid_y)
    inv = {v: k for k, v in TIER_RANK.items()}
    def tier_of(e, ok):
        if not ok: return "nm欠損"
        b = best.get(e)
        if b is not None and not np.isnan(b): return inv[int(b)]
        if e in unresolved: return "丙未判别"
        if e in anyL: return "冲突未连接"
        return "单独"
    E["tier"] = [tier_of(e, ok) for e, ok in zip(E.index, E.nm_ok)]
    E["flag_unresolved"] = E.index.isin(list(unresolved))
    pr = pd.concat([R[["eid_x", "rank"]].rename(columns={"eid_x": "eid"}), R[["eid_y", "rank"]].rename(columns={"eid_y": "eid"})])
    pr["person_id"] = E.person_id.reindex(pr.eid).values
    worst = pr.groupby("person_id")["rank"].max().map(inv)
    E["person_weakest_link"] = E.person_id.map(worst).fillna("")
    E["spec"] = E.sbits.map(lambda b: bits_to_labels(b, SPEC_LABELS)); E["title_cat"] = E.tbits.map(lambda b: bits_to_labels(b, [t for t, _ in TITLE]))
    E.reset_index().to_pickle(WORK/"person_key.pkl")
    L.to_pickle(WORK/"person_links.pkl")
    C["person_id"] = E.person_id.reindex(C.eid).values
    C["tier"] = E.tier.reindex(C.eid).values
    C.drop(columns=["slot", "nkey"]).to_pickle(WORK/"C_keyed.pkl")
    print(f"[{time.time()-t0:.0f}s] saved person_key.pkl, person_links.pkl, C_keyed.pkl")

    # ---- validation of the no-number rule on numbered years ----
    VAL = [("pharma", 2021), ("pharma", 2023), ("device", 2021), ("device", 2022)]
    vrows = []
    for ind, yr in VAL:
        d = C[(C.ind == ind) & (C.year == yr)]
        excl = int((~(d.pidn.notna() & d.nm_ok)).sum())
        d = d[d.pidn.notna() & d.nm_ok]
        tp, pred, true = pair_counts(d, "pidn", ["nm", "root"])
        vrows.append(dict(ind=ind, year=yr, rows=len(d), rows_excluded=excl, n_number=d.pidn.nunique(),
                          n_nm_root=d.groupby(["nm", "root"]).ngroups, pairs_true=true, pairs_pred=pred, pairs_tp=tp,
                          precision=tp / pred, recall=tp / true))
    V = pd.DataFrame(vrows)
    tot = V[["pairs_true", "pairs_pred", "pairs_tp"]].sum()
    for ind in ("pharma", "device"):
        s = V[V.ind == ind][["pairs_true", "pairs_pred", "pairs_tp"]].sum()
        print(f"no-number rule, {ind}: pairwise precision {s.pairs_tp/s.pairs_pred:.4f}, recall {s.pairs_tp/s.pairs_true:.4f}")

    # ---- clerical review sample (names, local only; the stage-1 sample is kept as clerical_review_sample_stage1_20261004.xlsx) ----
    rng = np.random.default_rng(SAMPLE_SEED)
    X = R[R.year_x != R.year_y]
    samp = []
    for t in ("甲", "乙", "丙"):
        x = X[X.tier == t]
        take = x.iloc[rng.choice(len(x), size=min(100, len(x)), replace=False)] if len(x) else x
        samp.append(take)
    S = pd.concat(samp, ignore_index=True)
    need = set(S.eid_x) | set(S.eid_y)
    Cs = C[C.eid.isin(need)].copy(); Cs["name0"] = Cs.name.where(Cs.name.notna(), Cs.name_raw)
    def modal(col):
        g = Cs[Cs[col].notna()].groupby(["eid", col]).size().reset_index(name="c").sort_values(["eid", "c"], ascending=[True, False])
        return g.drop_duplicates("eid").set_index("eid")[col]
    rep = pd.DataFrame({"name": modal("name0"), "inst": modal("inst"), "dept": modal("dept"), "title": modal("title")})
    rep = rep.join(E[["ind", "year", "root", "spec", "title_cat", "rows", "amt"]], how="right").reindex(list(need))
    out = []
    for i, r in enumerate(S.itertuples(), start=1):
        a, b = rep.loc[r.eid_x], rep.loc[r.eid_y]
        out.append({"sample_id": i, "档位": r.tier, "依据": r.basis,
                    "年1": a.year, "行业1": a.ind, "姓名1": a["name"], "所属1": a.inst, "部署1": a.dept, "职称1": a.title, "机构根1": a.root, "专科1": a.spec,
                    "年2": b.year, "行业2": b.ind, "姓名2": b["name"], "所属2": b.inst, "部署2": b.dept, "职称2": b.title, "机构根2": b.root, "专科2": b.spec,
                    "判定（同一人 / 不同人 / 无法判断）": "", "备注": ""})
    pd.DataFrame(out).to_excel(WORK/"clerical_review_sample.xlsx", index=False)
    print(f"clerical sample written: {S.tier.value_counts().to_dict()}")

    # ---- report ----
    lab = lambda r: f"{'制药' if r[0] == 'pharma' else '器械'} {r[1]}"
    tiers = ["甲", "乙", "丙", "丙未判别", "冲突未连接", "单独", "nm欠損"]
    rows_t = C.groupby(["ind", "year", "tier"]).size().unstack(fill_value=0).reindex(columns=tiers, fill_value=0)
    amt_t = C.groupby(["ind", "year", "tier"]).amt.sum().unstack(fill_value=0).reindex(columns=tiers, fill_value=0)
    rs = rows_t.div(rows_t.sum(axis=1), axis=0) * 100; am = amt_t.div(amt_t.sum(axis=1), axis=0) * 100
    def mdtab(df, fmt):
        h = "| 年 | " + " | ".join(df.columns) + " |\n|---|" + "---|" * len(df.columns) + "\n"
        return h + "\n".join("| " + lab(i) + " | " + " | ".join(fmt(v) for v in r) + " |" for i, r in df.iterrows())
    allr = rows_t.sum(); alla = amt_t.sum()
    per = E.groupby("person_id").agg(ninds=("ind", "nunique"), nyears=("year", "nunique"), nm_ok=("nm_ok", "max"))
    ph = E[E.ind == "pharma"].person_id.nunique(); dv = E[E.ind == "device"].person_id.nunique()
    vt = "| 行业 | 年 | 行数 | 排除行 | 编号数 | nm×机构根实体数 | 精确率 | 召回率 |\n|---|---|---|---|---|---|---|---|\n" + "\n".join(
        f"| {'制药' if r.ind == 'pharma' else '器械'} | {r.year} | {r.rows:,} | {r.rows_excluded:,} | {r.n_number:,} | {r.n_nm_root:,} | {r.precision:.4f} | {r.recall:.4f} |" for r in V.itertuples())
    pool = {ind: V[V.ind == ind][["pairs_true", "pairs_pred", "pairs_tp"]].sum() for ind in ("pharma", "device")}
    rl = {"old": "nm × 机构根（原规则）", "new": "相邻年唯一则按 nm 合并（新规则）"}
    a3t = "| 行业 | 验证年 | 相邻年 | 规则 | 行数 | 编号数 | 规则下实体数 | 满足条件的 nm（行数） | 精确率 | 召回率 |\n|---|---|---|---|---|---|---|---|---|---|\n" + "\n".join(
        f"| {'制药' if r.ind == 'pharma' else '器械'} | {r.year} | {r.adj} | {rl[r.rule]} | {r.rows:,} | {r.n_number:,} | {r.n_pred:,} | "
        f"{(f'{r.nm_qualified:,}（{r.rows_qualified:,}）') if r.rule == 'new' else '—'} | {r.precision:.4f} | {r.recall:.4f} |" for r in A3V.itertuples())
    a3d = "\n".join(f"- {'制药' if ind == 'pharma' else '器械'} {yr}：新规则{'采用' if v['adopted'] else '不采用（精确率下降超过门槛）'}；"
                     f"该年无编号行 {v['rows_nopid']:,}，按新规则并为一个实体的 nm {v['nm_qualified']:,} 个、行 {v['rows']:,}。" for (ind, yr), v in a3_apply.items())
    md = f"""# 跨年个人键：连接报告（步骤 2，只含汇总数）

生成脚本：`scripts/03_person_key.py`。生成日期：{time.strftime('%Y-%m-%d')}。

## 1. 规模

- C 表 {len(C):,} 行，年内实体 {len(E):,} 个，按实体的键：{'，'.join(f'{k} {v:,}' for k, v in E.ktype.value_counts().items())}（nm不可用 = 空、「-」等，每行单独成实体）。
- 有编号（含 dup）的实体中，同一键下 nm 写法不止一种的 {int((E.has_pid & (E.n_nm_spellings > 1)).sum()):,} 个，取行数最多的写法作连接用。
- 机构根：不同机构根 {m.root.nunique():,} 个；行中机构根为 82 所医学院大学之一的 {100*C.root.str.startswith('U:').mean():.1f}%，机构根为空的 {100*(C.root=='').mean():.2f}%；能归出专科关键词的行 {100*(C.sbit>0).mean():.1f}%，能归出职称类别的行 {100*(C.tbit>0).mean():.1f}%。
- 人数（person_id 数）：{E.person_id.nunique():,}。其中出现在制药 {ph:,}，出现在器械 {dv:,}，两边都有 {int((per.ninds > 1).sum()):,}；跨 2 年以上的 {int((per.nyears > 1).sum()):,}。
- 同名候选对（同 nm、不同年或不同行业）{len(Pp):,} 对。接受的连接：甲 {int(jia.sum()):,}，乙 {int(yi.sum()):,}，丙 {int(Q.bing.sum()):,}（丙候选对 {len(Q):,}）。因「一人一年一行业只能有一个实体」而跳过的连接 {skipped:,} 条；最终落在同一人内的连接 {int(L.realized.sum()):,} 条。
- 硬约束检查：同一 person_id 在同一年同一行业下有两个实体的情况 {viol} 例；制药 2023 年同一 person_id 下有两个不同 dup 的 {viol_dup} 例；其他有编号年份同一 person_id 下有两个不同编号的 {viol_pid} 例。

## 1b. 制药 2023 年改按 dup 定年内实体（第 2 阶段 A2）

- 这一年的 `氏名No` 按原始写法编号，不是同名判别的结果；人工判别的结果在「氏名（同姓同名）設定」列（`dup`，同名不同人用 a、b、c 等后缀或括号内的区分语区分）。年内实体改为 年 × 行业 × 规范化后的 `dup`（规范化同 `nm`：NFKC、去空格、异体字折叠），硬约束在这一年按 `dup` 执行。其他年份不变。
- 制药 2023 年 {dup_stats['rows']:,} 行，`dup` 为空的 {dup_stats['rows_no_dup']:,} 行；规范化后的 `dup` {dup_stats['n_dup']:,} 个，其中对应多个 `氏名No` 的 {dup_stats['dup_multi_pid']:,} 个（{100*dup_stats['dup_multi_pid']/dup_stats['n_dup']:.1f}%）；`氏名No` {dup_stats['n_pid']:,} 个，其中对应多个 `dup` 的 {dup_stats['pid_multi_dup']:,} 个。
- 同一 `nm` 下有多个 `dup` 的 {dup_stats['nm_multi_dup']:,} 个 `nm`；按 `氏名No` 算则是 {dup_stats['nm_multi_pid']:,} 个。

## 2. 各档位占行数的比例（%，分年分行业）

档位按实体计：取该实体实际成立的连接里最强的一档。丙未判别 = 有同名多候选、专科和职称判别不了、没有连接；冲突未连接 = 有合格连接但都因硬约束被跳过；单独 = 别的年份/行业里没有可连的同名实体；nm欠損 = 姓名为空或只有符号。

{mdtab(rs, lambda v: f'{v:.1f}')}
| 合计 | {' | '.join(f'{100*v/allr.sum():.1f}' for v in allr)} |

## 3. 各档位占金额的比例（%，分年分行业）

{mdtab(am, lambda v: f'{v:.1f}')}
| 合计 | {' | '.join(f'{100*v/alla.sum():.1f}' for v in alla)} |

## 4. 无编号规则的误差（以编号为参照，成对精确率与召回率）

把「年 × 行业 × nm × 机构根」的规则套到有编号的年份，以行对为单位：精确率 = 两行被规则归为同一实体且编号相同 / 被规则归为同一实体；召回率 = 同上 / 编号相同。排除行 = 无编号或 nm 不可用的行。

{vt}

- 合并：制药 精确率 {pool['pharma'].pairs_tp/pool['pharma'].pairs_pred:.4f}、召回率 {pool['pharma'].pairs_tp/pool['pharma'].pairs_true:.4f}；器械 精确率 {pool['device'].pairs_tp/pool['device'].pairs_pred:.4f}、召回率 {pool['device'].pairs_tp/pool['device'].pairs_true:.4f}。
- 本表与第 1 阶段口径相同，保留作对照。制药 2023 年的参照 `氏名No` 已知不是同名判别的结果（见 1b），这一行的精确率偏低不全是规则的误差。

## 4b. 无编号年份的新规则（第 2 阶段 A3）

新规则：某个 `nm` 在相邻的有编号年份里**每一年**都只对应一个实体（制药看 2021 和 2023，器械看 2022；任一相邻年没有该 `nm` 即不满足），该 `nm` 在无编号年份的全部行并为一个实体；否则仍用 `nm` × 机构根。相邻年的「实体」按本脚本的年内实体计（制药 2023 年按 `dup`），按行上的 `nm` 数。

验证：把新规则套到有编号的年份，以编号为参照算成对精确率和召回率，与原规则并排。制药用 2021 年（相邻年取 2020 和 2023），器械用 2022 年（相邻年取 2021）。新规则精确率比原规则低 {MAX_PREC_DROP} 以上的行业不采用。

{a3t}

{a3d}

## 5. 人工核对样本

`work/clerical_review_sample.xlsx`：甲、乙、丙各随机抽跨年连接（种子 {SAMPLE_SEED}），实际抽到 {S.tier.value_counts().reindex(['甲','乙','丙']).fillna(0).astype(int).to_dict()}。判定列留空，未作判断。第 1 阶段的样本改名为 `work/clerical_review_sample_stage1_20261004.xlsx` 留档。
"""
    (OUT/"linkage_report.md").write_text(md, encoding="utf-8")
    V.to_csv(WORK/"nopid_rule_validation.csv", index=False, encoding="utf-8-sig")
    A3V.to_csv(WORK/"nopid_rule_validation_a3.csv", index=False, encoding="utf-8-sig")
    print(f"[{time.time()-t0:.0f}s] persons {E.person_id.nunique()}, hard-constraint violations {viol} / dup {viol_dup} / number {viol_pid}; report written")
    print("A3 applied:", a3_apply)
    print("pharma 2023 tier share of rows:", {k: round(v, 1) for k, v in rs.loc[('pharma', 2023)].items()})
    print("pharma 2023 tier share of amount:", {k: round(v, 1) for k, v in am.loc[('pharma', 2023)].items()})
    print("tier share of rows (all):", {k: round(100*v/allr.sum(), 1) for k, v in allr.items()})
    print("tier share of amount (all):", {k: round(100*v/alla.sum(), 1) for k, v in alla.items()})


if __name__ == "__main__":
    main()
