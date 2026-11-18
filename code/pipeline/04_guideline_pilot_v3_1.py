# -*- coding: utf-8 -*-
"""Guideline COI audit pipeline v3.1 (stage 4). v2 and v3 (04_guideline_pilot.py, 04_guideline_pilot_v3.py and their frozen
prompts) are left unchanged. The prompts are the v3 templates (config/prompt_extraction_v3.md, prompt_company_resolve_v2.md).

Usage
  python 04_guideline_pilot_v3_1.py prompts "<project>" <key>    fill config/prompt_extraction_v3.md -> work/gl_v3_1/<key>/prompt_extraction_filled.md
  python 04_guideline_pilot_v3_1.py prep "<project>" <key>       company strings + de-duplicated closed set, fill config/prompt_company_resolve_v2.md
  python 04_guideline_pilot_v3_1.py audit "<project>" "<gold folder>" <key>
                                                                 three-class judgement of every payment unit; outputs in work/gl_v3_1/<key>

Guideline parameters: config/guidelines_v3_1.csv (coi_files, committee_files, note_files). Text copies: work/pilot_src/v3_1/<key>
(06_doc_to_text_v3_1.py). Extraction output: extracted_meta.csv, extracted_roster.csv, extracted_declarations.csv.
Company resolution output: company_resolved.csv. Manual aliases: config/company_alias_manual.csv (only for 未解析 strings).

Changes from v3 (CC_PROMPT_stage4.md, A1-A3)
- A1 a year marked "not submitted" no longer makes a unit unassessable (published-paper convention): the unit is judged
  declared / undeclared as usual and carries the flag not_submitted_year = 是.
- A2 the one-character name rule is removed everywhere (roster vs committee list, member vs payment table, roster vs the
  adjudication table). Names are compared after the extended kanji-variant folding of 03_person_key.py
  (config/kanji_variant_pairs.csv).
- A3 unchanged scope rule; the esophagus committee list now comes from the society's public-comment draft (config).

Rules kept from v3 (CC_PROMPT_stage3.md, B2-B4)
- B2 roster = union of the disclosure file(s) and the committee list(s); each member carries roles, in_scope (from the
  extraction: 是 / 否 / 不明), scope years and years not submitted. Three-class judgement of each unit (member x company x year x
  item, payment >= 500,000 yen):
    无法评价: no individual disclosure in the file; role not in scope; year outside the member's disclosure years; or scope
             unclear (in_scope 不明) for a member the disclosure file does not list ("范围不明").
    已申报:   the member's declarations contain the same company (or its cross-industry counterpart) and item for that year.
    未申报:   otherwise (in scope, listed without this company; or in scope but not listed).
- B3 company resolution: only 高 / 中 accepted (低 counts as unresolved); the closed set drops aliases that list another
  company's canonical name (logged in config/company_alias_removed_v3.csv). Declaration comparison with the hand-entered
  declarations of the gold workbook is cut to the years the gold workbook has.
- B4 year attribution: a declaration written for one year counts for that year; one written for the whole period counts for
  every year of the period. Each unit records which (basis).
The script prints aggregate numbers and company names only.
"""
import pandas as pd, numpy as np, re, sys, json, pathlib, importlib.util, time, hashlib, unicodedata

HERE = pathlib.Path(__file__).parent
_s = importlib.util.spec_from_file_location("pk", HERE/"03_person_key.py"); pk = importlib.util.module_from_spec(_s); _s.loader.exec_module(pk)
THR = 500_000
ITEMS = {"講演料": "lecture", "原稿料": "writing"}
GFILES = {"講演料": "講師謝金_利益相反_関数無_20250826【最終版】.xlsx", "原稿料": "原稿執筆料_利益相反_関数無_20250826【最終版】.xlsx"}
COI = [f"利益相反{i}" for i in range(1, 19)]
UNRES = "未解析"; ACCEPT_CONF = {"高", "中"}
DECL, UNDECL, UNASS = "已申报", "未申报", "无法评价"
TPL_EXTRACT = "prompt_extraction_v3.md"; TPL_RESOLVE = "prompt_company_resolve_v2.md"
LEG = re.compile(r"株式会社|\(株\)|㈱|有限会社|\(有\)|合同会社|一般社団法人|公益財団法人|一般財団法人|公益社団法人|特定非営利活動法人")
GPAT = re.compile(r"^(講演料|原稿料|研究費|寄附金|寄付金|役員・顧問職|顧問料|寄附講座|株保有|特許使用料)\((.*)\)」?$")


def cnorm(s): return LEG.sub("", pk.nk(s))
def sha256(p): return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()


def load_cfg(P, key):
    g = pd.read_csv(P/"config"/"guidelines_v3_1.csv", dtype=str, keep_default_na=False, encoding="utf-8-sig")
    r = g[g.key == key]
    if len(r) != 1: raise SystemExit(f"config/guidelines_v3_1.csv: expected one row for {key}, found {len(r)}")
    r = r.iloc[0].to_dict()
    for c, k in (("coi_files", "coi"), ("committee_files", "committee"), ("note_files", "notes")): r[k] = [x for x in r[c].split(";") if x]
    return r


def paths(P, key):
    W = P/"work"/"gl_v3_1"/key; S = P/"work"/"pilot_src"/"v3_1"/key
    return dict(W=W, S=S, scratch=S/"scratch", raw=P/"data_raw"/"guidelines"/key,
                meta=W/"extracted_meta.csv", roster=W/"extracted_roster.csv", decl=W/"extracted_declarations.csv",
                strings=S/"company_strings.csv", closed=P/"work"/"pilot_src"/"v3_1"/"company_closed_set_v3.csv", resolved=W/"company_resolved.csv")


def fill(tpl, mapping):
    s = tpl
    for k, v in mapping.items(): s = s.replace("{{" + k + "}}", v)
    left = sorted(set(re.findall(r"\{\{[A-Z_]+\}\}", s)))
    if left: raise SystemExit(f"unfilled placeholders: {left}")
    return s




# ---------------------------------------------------------------- prompts / prep
def cmd_prompts(P, key):
    cfg = load_cfg(P, key); pa = paths(P, key)
    for d in (pa["W"], pa["S"], pa["scratch"]): d.mkdir(parents=True, exist_ok=True)
    lines = ([f"  - {f}（开示文件）" for f in cfg["coi"]] + [f"  - {f}（委员会名单类文件）" for f in cfg["committee"]] + [f"  - {f}（说明类文件）" for f in cfg["notes"]])
    m = dict(GUIDELINE_TITLE=cfg["title"], SOCIETY=cfg["society"], RAW_DIR=str(pa["raw"]), FILE_LIST="\n".join(lines), TXT_DIR=str(pa["S"]),
             COI_FILES="、".join(cfg["coi"]), COMMITTEE_FILES=("、".join(cfg["committee"]) if cfg["committee"] else "无"),
             NOTE_FILES=("、".join(cfg["notes"]) if cfg["notes"] else "无"), SCRATCH_DIR=str(pa["scratch"]),
             OUT_META=str(pa["meta"]), OUT_ROSTER=str(pa["roster"]), OUT_DECL=str(pa["decl"]))
    tpl = P/"config"/TPL_EXTRACT
    out = pa["W"]/"prompt_extraction_filled.md"; out.write_text(fill(tpl.read_text(encoding="utf-8"), m), encoding="utf-8")
    print(f"template {TPL_EXTRACT} sha256 {sha256(tpl)}; filled prompt -> {out}")


def closed_set(P):
    """Company master without P_UNK; aliases that list another company's canonical name are dropped (logged)."""
    m = pd.read_csv(P/"config"/"company_master.csv", dtype=str, keep_default_na=False, encoding="utf-8-sig")
    m = m[m.company_id != "P_UNK"].copy()
    n = lambda s: cnorm(re.sub(r"[\s　]+", "", unicodedata.normalize("NFKC", s)))
    canon = {r.company_id: n(r.canonical_name) for r in m.itertuples()}
    removed = []; new_alias = []
    for r in m.itertuples():
        keep = []
        for a in [x for x in r.aliases.split("|") if x]:
            parts = [p for p in re.split(r"[()（）、,，/・]", n(a)) if p]
            other = sorted({oc for oc, cn in canon.items() if oc != r.company_id and len(cn) >= 3 and cn in parts})
            if other: removed.append(dict(company_id=r.company_id, alias=a, lists_canonical_of="|".join(other)))
            else: keep.append(a)
        new_alias.append("|".join(keep))
    m["aliases"] = new_alias
    return m[["ind", "company_id", "canonical_name", "aliases"]], pd.DataFrame(removed, columns=["company_id", "alias", "lists_canonical_of"])


def cmd_prep(P, key):
    pa = paths(P, key)
    D = pd.read_csv(pa["decl"], dtype=str, keep_default_na=False, encoding="utf-8-sig")
    s = D.company.str.strip().value_counts().rename_axis("company_as_written").reset_index(name="n_rows")
    s.to_csv(pa["strings"], index=False, encoding="utf-8-sig")
    cs, rem = closed_set(P)
    cs.to_csv(pa["closed"], index=False, encoding="utf-8-sig"); rem.to_csv(P/"config"/"company_alias_removed_v3.csv", index=False, encoding="utf-8-sig")
    mp = dict(IN_STRINGS=str(pa["strings"]), CLOSED_SET=str(pa["closed"]), OUT=str(pa["resolved"]), SCRATCH_DIR=str(pa["scratch"]))
    tpl = P/"config"/TPL_RESOLVE
    out = pa["W"]/"prompt_company_filled.md"; out.write_text(fill(tpl.read_text(encoding="utf-8"), mp), encoding="utf-8")
    print(f"company strings {len(s)} (rows {int(s.n_rows.sum())}); closed set {len(cs)} ids, aliases removed {len(rem)}; template {TPL_RESOLVE} sha256 {sha256(tpl)}")


# ---------------------------------------------------------------- audit helpers
def years_from(s):
    y = pk.nk(s).replace("～", "-").replace("〜", "-").replace("~", "-").replace("年", "")
    m = re.fullmatch(r"(\d{4})", y)
    if m: return {int(m.group(1))}
    m = re.search(r"(\d{4})\D+(\d{4})", y)
    if m: return set(range(int(m.group(1)), int(m.group(2)) + 1))
    return None


def years_of(meta):
    st = [v for v in meta[meta.field == "period_start"].value if re.match(r"\d{4}", pk.nk(v))]
    en = [v for v in meta[meta.field == "period_end"].value if re.match(r"\d{4}", pk.nk(v))]
    if not st or not en: raise SystemExit("extracted_meta.csv: period_start / period_end not readable")
    return list(range(min(int(pk.nk(v)[:4]) for v in st), max(int(pk.nk(v)[:4]) for v in en) + 1))


def read_gold_decl(GOLD, label, YEARS):
    rows = []; ys = set()
    for item, fn in GFILES.items():
        xl = pd.ExcelFile(GOLD/fn, engine="calamine")
        for sn in xl.sheet_names:
            m = re.match(r"(\d{4})利益相反", sn)
            if not m or int(m.group(1)) not in YEARS: continue
            b = pd.read_excel(xl, sheet_name=sn, header=0, dtype=object)
            b = b[b["ガイドライン"].astype(str).str.strip() == label].copy()
            if b.empty: continue
            ys.add(int(m.group(1)))
            for _, r in b.iterrows():
                for c in COI:
                    v = r[c]
                    if pd.isna(v) or not str(v).strip(): continue
                    mm = GPAT.match(pk.nk(v))
                    if not mm or mm.group(1) not in ITEMS: continue
                    comp = mm.group(2)
                    while comp.endswith(")") and comp.count("(") < comp.count(")"): comp = comp[:-1]
                    rows.append(dict(nm=pk.norm_name(r["名前"]), year=int(m.group(1)), item=mm.group(1), company_gold=comp))
    return pd.DataFrame(rows, columns=["nm", "year", "item", "company_gold"]).drop_duplicates(), sorted(ys)


def f3(a, b): return f"{a/b:.3f}" if b else "—"


# ---------------------------------------------------------------- audit
def cmd_audit(P, GOLD, key):
    cfg = load_cfg(P, key); pa = paths(P, key); W = pa["W"]; CONF = P/"config"
    meta = pd.read_csv(pa["meta"], dtype=str, keep_default_na=False, encoding="utf-8-sig")
    YEARS = years_of(meta)
    mv = lambda f: pk.nk(meta[meta.field == f].value.iloc[0]) if (meta.field == f).any() else ""
    indiv, covered, listing, by_year = mv("individual_disclosure"), mv("covered_roles"), mv("listing_rule"), mv("by_year")
    unclear = lambda v: v in ("", "不明")
    scope_unclear = unclear(covered) and unclear(listing)
    R = pd.read_csv(pa["roster"], dtype=str, keep_default_na=False, encoding="utf-8-sig")
    D = pd.read_csv(pa["decl"], dtype=str, keep_default_na=False, encoding="utf-8-sig")
    R["nm"] = R.name.map(pk.norm_name); D["nm"] = D.name.map(pk.norm_name)
    R["root"] = R.affiliation.map(lambda a: pk.inst_root(a, ""))
    R["src"] = np.where(R.source_type.str.contains("开示"), "coi", "committee")
    D["item"] = D["item"].str.strip(); D["company"] = D.company.str.strip()

    # ---- A2: no one-character merging; names are matched exactly after the extended variant folding ----
    nlog = []

    # ---- members ----
    def agg_scope(s):
        v = set(s)
        return "是" if "是" in v else ("否" if v <= {"否"} else "不明")
    mem = R[R.nm != ""].groupby("nm").agg(listed=("src", lambda s: "coi" in set(s)), in_committee=("src", lambda s: "committee" in set(s)),
                                          in_scope=("in_scope", lambda s: agg_scope(pk.nk(x) for x in s)),
                                          scope_basis=("scope_basis", lambda s: " / ".join(sorted({x for x in s if x}))[:300]),
                                          scope_years=("scope_years", lambda s: set().union(*[years_from(x) or set() for x in s])),
                                          not_sub=("not_submitted_years", lambda s: {int(y) for x in s for y in re.findall(r"\d{4}", pk.nk(x))}),
                                          roles=("committee_or_role", lambda s: " | ".join(sorted({x for x in s if x}))[:200]),
                                          affs=("affiliation", lambda s: sorted({x for x in s if x})),
                                          coi_loc=("source_location", lambda s: ""),
                                          ).reset_index()
    coi_loc = R[R.src == "coi"].groupby("nm").apply(lambda g: f"{g.source_file.iloc[0]} {g.source_location.iloc[0]}").to_dict()
    mem["coi_loc"] = mem.nm.map(coi_loc).fillna("")
    mem["roots"] = mem.affs.map(lambda a: {pk.inst_root(x, "") for x in a} - {""})
    mem["sbits"] = mem.affs.map(lambda a: int(np.bitwise_or.reduce([pk.spec_bit(pk.nk(x)) for x in a])) if a else 0)

    # ---- company keys (pipeline side) ----
    mas = pd.read_csv(CONF/"company_master.csv", dtype=str, keep_default_na=False, encoding="utf-8-sig")
    valid = set(mas.company_id) - {"P_UNK"}
    equiv = {r.company_id: {r.company_id} | {x for x in r["跨行业对应"].split("|") if x} for _, r in mas.iterrows()}
    res = pd.read_csv(pa["resolved"], dtype=str, keep_default_na=False, encoding="utf-8-sig")
    for c in res.columns: res[c] = res[c].str.strip()
    rmap = {r.company_as_written: (r.company_id, r.confidence) for r in res.itertuples()}
    man = pd.read_csv(CONF/"company_alias_manual.csv", dtype=str, keep_default_na=False, encoding="utf-8-sig")
    mmap = {r.company_as_written.strip(): r.company_id.strip() for r in man.itertuples()}
    plog = {}
    def pkey(raw):
        if raw in plog: return plog[raw][0]
        cid, conf = rmap.get(raw, (None, ""))
        if cid is None: how, k = "解析表缺行", None
        elif cid == UNRES: how, k = UNRES, None
        elif cid not in valid: how, k = "解析出闭集外编号", None
        elif conf not in ACCEPT_CONF: how, k = "低置信度不采用", None
        else: how, k = "模型:" + conf, cid
        if k is None and raw in mmap and mmap[raw] in valid: how, k = how + "→人工别名", mmap[raw]
        if k is None: k = "NAME:" + cnorm(raw)
        plog[raw] = (k, how); return k
    D["ck"] = D.company.map(pkey)
    strings = list(D.company.unique())
    s_how = pd.Series([plog[s][1] for s in strings]).value_counts().to_dict() if strings else {}
    conf_counts = res[res.company_as_written.isin(strings) & (res.company_id != UNRES)].confidence.value_counts().to_dict()

    # ---- declarations: year attribution (B4) ----
    Dd = D[D["item"].isin(ITEMS)].copy()
    Dd["cover"] = Dd.year.map(years_from)
    Dd["basis"] = np.where(Dd.cover.map(lambda c: c is not None and len(c) == 1), "按年", "期间合并")
    Dd["cover"] = Dd.cover.map(lambda c: c if c is not None else set(YEARS))
    decl = {}
    for r in Dd.itertuples():
        for cid in (equiv.get(r.ck, {r.ck})):
            for y in r.cover:
                decl.setdefault((r.nm, cid, r.item, y), (r.basis, r.source_text, f"{r.source_file} {r.source_location}"))

    # ---- linking to payments (A2: exact nm only, no one-character fallback) ----
    E = pd.read_pickle(P/"work"/"person_key.pkl")
    E = E[E.year.isin(YEARS) & E.nm_ok]
    plog_rows = []
    def link(ind):
        Ei = E[E.ind == ind]; byn = dict(tuple(Ei.groupby("nm"))); out = []
        for r in mem.itertuples():
            c = byn.get(r.nm)
            if c is None:
                out.append((r.nm, None, "未找到", "")); continue
            per = c.groupby("person_id").agg(roots=("root", set), sb=("sbits", lambda s: int(np.bitwise_or.reduce(s.values))),
                                             tiers=("tier", lambda s: "|".join(sorted(set(s)))))
            rm = per[per.roots.map(lambda x: bool(x & r.roots))]
            if len(rm) == 1: out.append((r.nm, rm.index[0], "甲", rm.tiers.iloc[0])); continue
            if len(per) == 1: out.append((r.nm, per.index[0], "乙", per.tiers.iloc[0])); continue
            pool = rm if len(rm) > 1 else per
            sm = pool[(pool.sb & r.sbits) != 0]
            if len(sm) == 1: out.append((r.nm, sm.index[0], "丙", sm.tiers.iloc[0])); continue
            out.append((r.nm, None, "多候选未判别", ""))
        return pd.DataFrame(out, columns=["nm", "person_id", "link_tier", "person_key_tiers"])
    Lp = link("pharma"); Ld = link("device")

    # ---- units and three-class judgement ----
    C = pd.read_pickle(P/"work"/"C_keyed.pkl")[["ind", "year", "person_id", "company_id", "c3", "amt"]]
    C = C[C.year.isin(YEARS) & C.c3.isin(ITEMS.values())]
    inv_items = {v: k for k, v in ITEMS.items()}
    cname = mas.set_index("company_id").canonical_name.to_dict()
    def units(Lk, ind):
        lk = Lk.dropna(subset=["person_id"])
        x = C[(C.ind == ind) & C.person_id.isin(lk.person_id)].merge(lk[["nm", "person_id", "link_tier"]], on="person_id")
        u = x.groupby(["nm", "link_tier", "company_id", "year", "c3"]).amt.sum().reset_index()
        u = u[u.amt >= THR].rename(columns={"company_id": "ck", "amt": "amt_pay"})
        u["item"] = u.c3.map(inv_items); u["ind"] = ind
        return u.drop(columns="c3")
    U = pd.concat([units(Lp, "pharma"), units(Ld, "device")], ignore_index=True)
    M = mem.set_index("nm")
    def judge(r):
        m = M.loc[r.nm]
        if indiv == "否": return UNASS, "文件无个人别开示", "", "", ""
        if m.in_scope == "否": return UNASS, "角色不在适用范围", "", m.scope_basis, ""
        if m.scope_years and r.year not in m.scope_years: return UNASS, "不在该委员的开示期间", "", m.scope_basis, ""
        if m.in_scope == "不明" and not m.listed: return UNASS, "范围不明", "", m.scope_basis, ""
        hit = decl.get((r.nm, r.ck, r.item, r.year))
        if hit: return DECL, "申报里有同一企业", hit[0], hit[1], hit[2]
        yb = "按年" if by_year == "是" else "期间合并"
        if m.listed: return UNDECL, "已列出、申报里没有该企业", yb, "", m.coi_loc
        return UNDECL, "在适用范围内而未列出" + ("（文件只列有申报内容的委员）" if listing == "是" else ""), yb, m.scope_basis, ""
    J = [judge(r) for r in U.itertuples()]
    U["judge"] = [j[0] for j in J]; U["judge_detail"] = [j[1] for j in J]; U["basis"] = [j[2] for j in J]
    U["evidence_text"] = [j[3] for j in J]; U["evidence_loc"] = [j[4] for j in J]
    U["company"] = U.ck.map(cname); U["listed_in_coi"] = U.nm.map(M.listed); U["in_scope"] = U.nm.map(M.in_scope)
    U["not_submitted_year"] = ["是" if r.year in M.loc[r.nm].not_sub else "否" for r in U.itertuples()]   # A1: flag only

    # ---- declaration comparison vs hand-entered gold, cut to the years the gold workbook has (B3-2) ----
    G, gyears = read_gold_decl(GOLD, cfg["gold_label"], YEARS)
    gres_f = P/"work"/"gl"/key/"gold_company_resolved.csv"    # stage-2 reference-side mapping, reused for this diagnostic only
    gres = pd.read_csv(gres_f, dtype=str, keep_default_na=False, encoding="utf-8-sig") if gres_f.exists() else pd.DataFrame(columns=["company_as_written", "company_id", "confidence"])
    gmap = {cnorm(r.company_as_written): r.company_id.strip() for r in gres.itertuples() if r.company_id.strip() in valid}
    idm = pd.read_csv(CONF/"company_id_map.csv", dtype=str, keep_default_na=False)
    nm2 = pd.concat([idm[["co", "company_id"]].rename(columns={"co": "n"}), mas[["canonical_name", "company_id"]].rename(columns={"canonical_name": "n"})])
    nm2 = nm2[(nm2.n != "") & (nm2.company_id != "P_UNK")]
    dmap = nm2.assign(c=nm2.n.map(cnorm)).groupby("c").company_id.unique()
    def gkey(s):
        c = cnorm(s); v = dmap.get(c)
        if v is not None and len(v) == 1: return v[0]
        return gmap.get(c, "NAME:" + c)
    G["ck"] = G.company_gold.map(gkey)
    De = {(n, c, it) for n, c, it, cov in zip(Dd.nm, Dd.ck, Dd["item"], Dd.cover) if cov & set(gyears)}
    Gd = {(n, c, it) for n, c, it in zip(G.nm, G.ck, G["item"])}
    d_tp, d_ex, d_miss = len(De & Gd), len(De - Gd), len(Gd - De)

    # ---- outputs ----
    W.mkdir(parents=True, exist_ok=True)
    U.to_csv(W/"units_v3.csv", index=False, encoding="utf-8-sig")
    out_m = mem.drop(columns=["affs"]).copy()
    for c in ("scope_years", "not_sub", "roots"): out_m[c] = out_m[c].map(lambda s: "|".join(str(x) for x in sorted(s)))
    out_m.to_csv(W/"roster_v3.csv", index=False, encoding="utf-8-sig")
    pd.concat([Lp.assign(ind="pharma"), Ld.assign(ind="device")]).to_csv(W/"member_links.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame([dict(company_as_written=k, key=v[0], how=v[1]) for k, v in plog.items()]).to_csv(W/"company_map.csv", index=False, encoding="utf-8-sig")
    lt = lambda L: L.link_tier.value_counts().reindex(["甲", "乙", "丙", "多候选未判别", "未找到"], fill_value=0).to_dict()
    Up = U[U.ind == "pharma"]; Udv = U[U.ind == "device"]
    Mt = dict(key=key, title=cfg["title"], years=YEARS, scope=dict(individual_disclosure=indiv, covered_roles=covered[:120], listing_rule=listing, by_year=by_year, scope_unclear=scope_unclear),
              roster=dict(rows=len(R), coi_rows=int((R.src == "coi").sum()), committee_rows=int((R.src == "committee").sum()), members=len(mem),
                          listed=int(mem.listed.sum()), committee_only=int((~mem.listed).sum()), in_scope=mem.in_scope.value_counts().to_dict(),
                          near_merges=len(nlog)),
              company=dict(strings=len(strings), how=s_how, confidence=conf_counts, aliases_removed=int(len(closed_set(P)[1]))),
              declarations=dict(rows=len(D), gold_years=gyears, tp=d_tp, extra=d_ex, missed=d_miss),
              links=dict(pharma=lt(Lp), device=lt(Ld), near_payment=len(plog_rows)),
              units=dict(pharma=len(Up), device=len(Udv), pharma_judge=Up.judge.value_counts().to_dict(), device_judge=Udv.judge.value_counts().to_dict(),
                         detail=Up.judge_detail.value_counts().to_dict(), basis=Up.basis.value_counts().to_dict(),
                         not_submitted=Up[Up.not_submitted_year == "是"].judge.value_counts().to_dict()),
              generated=time.strftime("%Y-%m-%d"))
    (W/"metrics_v3.json").write_text(json.dumps(Mt, ensure_ascii=False, indent=1, default=lambda o: int(o) if isinstance(o, np.integer) else bool(o) if isinstance(o, np.bool_) else str(o)), encoding="utf-8")
    print(f"[{key}] years {YEARS}; scope individual={indiv} listing={listing} unclear={scope_unclear}; roster rows {len(R)} members {len(mem)} (listed {int(mem.listed.sum())}, committee only {int((~mem.listed).sum())}), in_scope {mem.in_scope.value_counts().to_dict()}, near merges {len(nlog)}")
    print(f"[{key}] company {s_how}; decl vs gold (years {gyears}) tp {d_tp} extra {d_ex} missed {d_miss}")
    print(f"[{key}] links pharma {lt(Lp)} device {lt(Ld)}; near payment links {len(plog_rows)}")
    print(f"[{key}] not-submitted-year units (pharma) {Up[Up.not_submitted_year == '是'].judge.value_counts().to_dict()}")
    print(f"[{key}] units pharma {len(Up)} {Up.judge.value_counts().to_dict()} detail {Up.judge_detail.value_counts().to_dict()}; device {len(Udv)} {Udv.judge.value_counts().to_dict()}")


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "prompts": cmd_prompts(pathlib.Path(sys.argv[2]), sys.argv[3])
    elif cmd == "prep": cmd_prep(pathlib.Path(sys.argv[2]), sys.argv[3])
    elif cmd == "audit": cmd_audit(pathlib.Path(sys.argv[2]), pathlib.Path(sys.argv[3]), sys.argv[4])
    else: raise SystemExit("usage: prompts|prep|audit ...")
