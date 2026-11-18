# -*- coding: utf-8 -*-
"""Step 1: company master.
Usage: python 02_company_master.py "<project>"
Reads  work/C.pkl, work/B.pkl, work/inventory.csv, and (optional) config/company_merge_confirmed.csv
Writes config/company_master.csv, config/company_id_map.csv (ind,k,co -> company_id), out/company_review.xlsx,
       work/B_keyed.pkl (B + company_id)
Pharma: company_id from 社番 k. Display name = most frequent co spelling in the latest year the k appears.
        Rows with empty k but a known co get the k that carries that co (same year first); rows with neither -> P_UNK.
Device: codes are not stable across years, so company_id from co. Exact co = one company. Names that only look alike
        (normalisation or string similarity) are listed in out/company_review.xlsx and are NOT merged until a row in
        config/company_merge_confirmed.csv (columns co, merge_into, decision) says decision == 合并.
The script prints aggregate numbers and company names only. No personal names.
"""
import pandas as pd, numpy as np, re, sys, unicodedata, difflib, pathlib, itertools
P = pathlib.Path(sys.argv[1]); WORK, CONF, OUT = P/"work", P/"config", P/"out"; OUT.mkdir(exist_ok=True)
C = pd.read_pickle(WORK/"C.pkl"); B = pd.read_pickle(WORK/"B.pkl")
cols = ["kind", "ind", "year", "k", "co", "amt"]
A = pd.concat([C[cols], B[cols]], ignore_index=True)

# ---------- pharma ----------
p = A[A.ind == "pharma"]
known = p[p.k != ""]
kco_year = known.groupby(["co", "year"]).k.unique()
kco_all = known.groupby("co").k.unique()
def fill_k(co, year):
    if co == "": return None
    v = kco_year.get((co, year))
    if v is not None and len(v) == 1: return v[0]
    v = kco_all.get(co)
    if v is not None and len(v) == 1: return v[0]
    return None
pmap = {}  # (k, co) -> company_id
for (k, co, year), _ in p.groupby(["k", "co", "year"]):
    if k != "": pmap[(k, co)] = "P" + k.zfill(3)
    else:
        kk = fill_k(co, year)
        pmap[(k, co)] = ("P" + kk.zfill(3)) if kk else "P_UNK"
pm_rows = []
for k, g in known.groupby("k"):
    last = g.year.max()
    cnt = g[g.year == last].groupby("co").agg(n=("amt", "size"), s=("amt", "sum")).reset_index()
    cnt = cnt.sort_values(["n", "s", "co"], ascending=[False, False, True])
    canon = cnt.co.iloc[0]
    allc = g.groupby("co").size().sort_values(ascending=False)
    pm_rows.append(dict(ind="pharma", company_id="P" + k.zfill(3), canonical_name=canon,
                        aliases="|".join([c for c in allc.index if c != canon]), key=k))
if (p.k.eq("") & p.co.eq("")).any():
    pm_rows.append(dict(ind="pharma", company_id="P_UNK", canonical_name="(社番・企業名とも空欄)", aliases="", key=""))

# ---------- device ----------
d = A[A.ind == "device"]
dco = sorted(d.co.unique())
base_id = {c: "D%03d" % (i + 1) for i, c in enumerate(dco)}
merge = {}
mf = CONF/"company_merge_confirmed.csv"
if mf.exists():
    m = pd.read_csv(mf, dtype=str).fillna("")
    for _, r in m[m.decision.str.strip() == "合并"].iterrows():
        if r.co in base_id and r.merge_into in base_id: merge[r.co] = r.merge_into
def root(c):
    seen = set()
    while c in merge and c not in seen: seen.add(c); c = merge[c]
    return c
dmap = {c: base_id[root(c)] for c in dco}
dm_rows = []
for cid, members in pd.Series(dco).groupby(pd.Series(dco).map(dmap)):
    tgt = [c for c in members if root(c) == c][0]
    dm_rows.append(dict(ind="device", company_id=cid, canonical_name=tgt,
                        aliases="|".join(sorted(c for c in members if c != tgt)), key=""))

# ---------- assign ids to every row ----------
def cid_of(r_ind, k, co):
    return pmap[(k, co)] if r_ind == "pharma" else dmap[co]
idmap = A[["ind", "k", "co"]].drop_duplicates().copy()
idmap["company_id"] = [cid_of(i, k, c) for i, k, c in idmap[["ind", "k", "co"]].itertuples(index=False)]
A = A.merge(idmap, on=["ind", "k", "co"], how="left")
master = pd.DataFrame(pm_rows + dm_rows)
yrs = A.groupby("company_id").year.agg(lambda s: ",".join(str(y) for y in sorted(s.unique())))
ctot = A[A.kind == "C"].groupby("company_id").amt.sum(); btot = A[A.kind == "B"].groupby("company_id").amt.sum()
master["出现年份"] = master.company_id.map(yrs)
master["C总额"] = master.company_id.map(ctot).fillna(0).round(0).astype("int64")
master["B总额"] = master.company_id.map(btot).fillna(0).round(0).astype("int64")

# cross-industry: any pharma spelling equal to any device spelling
pnames = A[A.ind == "pharma"].groupby("company_id").co.unique()
dnames = A[A.ind == "device"].groupby("company_id").co.unique()
d_by_name = {c: cid for cid, cs in dnames.items() for c in cs}
partner = {}
for pid_, cs in pnames.items():
    hits = sorted({d_by_name[c] for c in cs if c in d_by_name and c != ""})
    if hits:
        partner.setdefault(pid_, set()).update(hits)
        for h in hits: partner.setdefault(h, set()).add(pid_)
master["是否跨行业"] = master.company_id.map(lambda c: "是" if c in partner else "否")
master["跨行业对应"] = master.company_id.map(lambda c: "|".join(sorted(partner.get(c, []))))
master = master[["ind", "company_id", "canonical_name", "aliases", "出现年份", "C总额", "B总额", "是否跨行业", "跨行业对应"]]
master.to_csv(CONF/"company_master.csv", index=False, encoding="utf-8-sig")
idmap.sort_values(["ind", "company_id", "co"]).to_csv(CONF/"company_id_map.csv", index=False, encoding="utf-8-sig")

# ---------- review workbook ----------
LEGAL = r"株式会社|\(株\)|有限会社|\(有\)|合同会社|\(同\)|合資会社|合名会社|incorporated|inc|corporation|corp|co\.?,?ltd|ltd|limited|k\.?k\.?|llc|gk"
def n2(s):
    s = unicodedata.normalize("NFKC", s).lower()
    s = re.sub(LEGAL, "", s)
    return re.sub(r"[\s・･·\.,，、\-‐－―_&＆'’\(\)（）/]", "", s)
dinfo = d.groupby("co").agg(years=("year", lambda s: ",".join(str(y) for y in sorted(s.unique()))),
                            rows_C=("kind", lambda s: int((s == "C").sum())), rows_B=("kind", lambda s: int((s == "B").sum())))
dinfo["amt_C"] = d[d.kind == "C"].groupby("co").amt.sum().reindex(dinfo.index).fillna(0).round(0).astype("int64")
dinfo["amt_B"] = d[d.kind == "B"].groupby("co").amt.sum().reindex(dinfo.index).fillna(0).round(0).astype("int64")
dcodes = pd.concat([C[C.ind == "device"][["co", "year", "k"]], B[B.ind == "device"][["co", "year", "k"]]])
dinfo["codes_by_year"] = dcodes.groupby("co").apply(
    lambda g: "; ".join(f"{y}:{','.join(sorted(set(g[g.year == y].k)))}" for y in sorted(g.year.unique())))
# generic words are removed before the similarity ratio, so that e.g. two different "...メディカルジャパン" do not pair up
GENERIC = r"ジャパン|japan|メディカル|medical|ヘルスケア|healthcare|グループ|group|日本"
def n3(s): return re.sub(GENERIC, "", n2(s))
pairs = []
for a, b in itertools.combinations(dco, 2):
    na, nb = n2(a), n2(b); ga, gb = n3(a), n3(b)
    ratio = difflib.SequenceMatcher(None, ga, gb).ratio() if min(len(ga), len(gb)) >= 2 else 0.0
    why = []
    if na == nb: why.append("规范化后相同")
    elif min(len(na), len(nb)) >= 3 and (na in nb or nb in na): why.append("一方包含另一方")
    if ratio >= 0.75 and na != nb: why.append("去通用词后相似度>=0.75")
    if why: pairs.append((a, b, round(ratio, 3), "+".join(why)))
size = (dinfo.rows_C + dinfo.rows_B).to_dict()
rev = []
for i, (a, b, ratio, why) in enumerate(sorted(pairs, key=lambda x: (x[0], x[1])), start=1):
    big, small = (a, b) if size[a] >= size[b] else (b, a)   # proposed direction: smaller spelling -> larger
    ya, yb = set(dinfo.loc[small, "years"].split(",")), set(dinfo.loc[big, "years"].split(","))
    rev.append(dict(pair=i, co=small, merge_into=big, decision=("合并" if merge.get(small) == big else ""),
                    reasons=why, sim_generic_removed=ratio, years_co=dinfo.loc[small, "years"], years_merge_into=dinfo.loc[big, "years"],
                    same_year=",".join(sorted(ya & yb)),
                    codes_co=dinfo.loc[small, "codes_by_year"], codes_merge_into=dinfo.loc[big, "codes_by_year"],
                    rows_C_co=dinfo.loc[small, "rows_C"], rows_C_merge_into=dinfo.loc[big, "rows_C"],
                    amt_C_co=dinfo.loc[small, "amt_C"], amt_B_co=dinfo.loc[small, "amt_B"],
                    company_id_co=dmap[small], company_id_merge_into=dmap[big]))
rev = pd.DataFrame(rev)
pv = []
for k, g in known.groupby("k"):
    s = g.groupby("co").agg(rows=("amt", "size"), years=("year", lambda x: ",".join(str(y) for y in sorted(x.unique()))))
    if len(s) > 1:
        for co, r in s.iterrows(): pv.append(dict(company_id="P" + k.zfill(3), co=co, rows=int(r.rows), years=r.years))
pv = pd.DataFrame(pv)
cross = master[master["是否跨行业"] == "是"][["ind", "company_id", "canonical_name", "aliases", "出现年份", "C总额", "B总额", "跨行业对应"]]
readme = pd.DataFrame({"说明": [
    "device_merge_candidates：器械企业名的相似候选，一行一对。co 是行数较少的写法，merge_into 是行数较多的写法。未确认前一律不合并。",
    "确认方法：decision 填『合并』或『不合并』(合并方向可改 merge_into)；然后把 co、merge_into、decision 三列",
    "  另存为 config/company_merge_confirmed.csv(UTF-8)，重跑 02_company_master.py。",
    "same_year：两种写法同年都出现的年份。同年并存且代码不同，多半是两家公司。codes_* 仅供参考（器械代码跨年不稳定）。",
    "pharma_name_variants：同一社番下的多种写法（已按社番合并，仅供核对是否有代码复用）。",
    "cross_industry：制药与器械两边名称相同的企业。"]})
with pd.ExcelWriter(OUT/"company_review.xlsx") as w:
    readme.to_excel(w, sheet_name="README", index=False)
    rev.to_excel(w, sheet_name="device_merge_candidates", index=False)
    pv.to_excel(w, sheet_name="pharma_name_variants", index=False)
    cross.to_excel(w, sheet_name="cross_industry", index=False)

# ---------- B with company_id ----------
B = B.merge(idmap, on=["ind", "k", "co"], how="left"); B.to_pickle(WORK/"B_keyed.pkl")

# ---------- acceptance ----------
miss = A.company_id.isna().sum()
inv = pd.read_csv(WORK/"inventory.csv")
s0 = pd.concat([C.groupby(["kind", "ind", "year"]).agg(rows=("amt", "size"), amt=("amt", "sum")),
                pd.read_pickle(WORK/"B.pkl").groupby(["kind", "ind", "year"]).agg(rows=("amt", "size"), amt=("amt", "sum"))])
s1 = A.groupby(["kind", "ind", "year", "company_id"]).amt.agg(["size", "sum"]).groupby(level=[0, 1, 2]).sum()
chk = s0.join(s1)
chk["oku1"] = (chk["sum"] / 1e8).round(1)
chk = chk.reset_index().merge(inv[["kind", "ind", "year", "oku"]], on=["kind", "ind", "year"])
bad = chk[(chk.rows != chk["size"]) | ((chk.amt - chk["sum"]).abs() > 0.5) | (chk.oku != chk.oku1)]
print("rows without company_id:", int(miss))
print("year cells compared:", len(chk), " mismatches:", len(bad))
print("pharma companies:", (master.ind == "pharma").sum(), "(incl. P_UNK:", int((master.company_id == "P_UNK").sum()), ")",
      " device companies:", (master.ind == "device").sum(), " merges applied:", len(merge))
print("rows assigned P_UNK:", int((A.company_id == "P_UNK").sum()), " amount:", round(A[A.company_id == "P_UNK"].amt.sum()))
fill = A[(A.ind == "pharma") & (A.k == "") & (A.company_id != "P_UNK")]
print("pharma rows with empty k filled by name:", len(fill))
print("pharma ids with >1 spelling:", int((master[master.ind == "pharma"].aliases != "").sum()))
print("cross-industry companies: pharma", int(((master.ind == "pharma") & (master["是否跨行业"] == "是")).sum()),
      " device", int(((master.ind == "device") & (master["是否跨行业"] == "是")).sum()))
print("device candidate pairs for review:", len(rev), " distinct names involved:", len(set(rev.co) | set(rev.merge_into)) if len(rev) else 0)
print("ACCEPT" if miss == 0 and len(bad) == 0 else "FAIL")
