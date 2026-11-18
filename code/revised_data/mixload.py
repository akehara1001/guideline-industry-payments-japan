# -*- coding: utf-8 -*-
"""Run scripts/01_build_tables.py unchanged, with the four fixed pharma C files swapped in.
The script text of 01 is executed as is; only three things are set from outside, between its definitions and its build loop:
  1. CFG[key] = (sheet, header) for the keys in <mixdir>/sources.csv;
  2. FILES: the current file of each such key is replaced by the fixed file (registered under the name "<key>__<file>", so 01's find() works);
  3. pandas.read_excel renames the columns of a fixed file by <mixdir>/column_map_fixed.csv (source_col -> header_for_01) before 01 picks them,
     so that 01's own column patterns choose them; a column not in the map stops the run.
     Before the renaming, two value rules are applied to a fixed file (both optional files; the run stops if a count differs):
     - <mixdir>/name_rules.csv: rows whose 氏名(新字) is the one placeholder value (contains every word of must_contain, has the given length)
       get the blank_cols emptied; the number of such rows must equal expected_rows;
     - <mixdir>/code_override.csv: rows with the listed 管理番号 get 社番 = k_use (each must currently carry k_fixed).
Usage as a module: G, tail = build_namespace(s01, raw_current, raw_fixed, work, conf, mixdir); exec(tail, G) runs 01's build loop.
Usage as a script (= 01 with the fixed files): python mixload.py <s01> <raw_current> <raw_fixed> <work> <conf> <mixdir>
"""
import sys, pathlib, re, unicodedata
import pandas as pd

def _nh(c): return re.sub(r"\s+", "", unicodedata.normalize("NFKC", str(c)))

def build_namespace(s01, raw_current, raw_fixed, work, conf, mixdir):
    s01, raw_fixed, mixdir = pathlib.Path(s01), pathlib.Path(raw_fixed), pathlib.Path(mixdir)
    src = s01.read_text(encoding="utf-8"); cut = "allC=[];allB=[]"
    assert src.count(cut) == 1
    head, tail = src.split(cut); tail = cut + tail
    saved = sys.argv; sys.argv = ["01_build_tables.py", str(raw_current), str(work), str(conf)]
    G = {"__name__": "s01_mixed", "__file__": str(s01)}
    exec(compile(head, str(s01), "exec"), G)
    sys.argv = saved
    S = pd.read_csv(mixdir / "sources.csv", dtype=str, keep_default_na=False, encoding="utf-8-sig")
    M = pd.read_csv(mixdir / "column_map_fixed.csv", dtype=str, keep_default_na=False, encoding="utf-8-sig")
    ren = {_nh(a): b for a, b in zip(M.source_col, M.header_for_01)}
    assert len(set(M.header_for_01)) == len(M), "two source columns mapped to one header"
    fixed_paths = set()
    for r in S.itertuples():
        assert r.key in G["CFG"], r.key
        pre = r.key.split("#")[0]; path = raw_fixed / r.file
        assert path.exists(), path
        G["CFG"][r.key] = (r.sheet, int(r.header))
        for b in [b for b in G["FILES"] if b.startswith(pre + "__")]: del G["FILES"][b]
        G["FILES"][f"{pre}__{r.file}"] = str(path); fixed_paths.add(str(path))
    path_key = {str(raw_fixed / r.file): r.key for r in S.itertuples()}
    # optional per-key override of the column map (variant runs only; absent in the main fixed run): key, source_col, header_for_01
    KO = pd.read_csv(mixdir / "column_map_key_override.csv", dtype=str, keep_default_na=False, encoding="utf-8-sig") if (mixdir / "column_map_key_override.csv").exists() else None
    ren_key = {}
    if KO is not None:
        for r in KO.itertuples():
            assert r.key in set(S.key) and _nh(r.source_col) in ren, (r.key, r.source_col)
            ren_key.setdefault(r.key, dict(ren))[_nh(r.source_col)] = r.header_for_01
        for k, m in ren_key.items(): assert len(set(m.values())) == len(m), f"{k}: two source columns mapped to one header"
    NR = pd.read_csv(mixdir / "name_rules.csv", dtype=str, keep_default_na=False, encoding="utf-8-sig") if (mixdir / "name_rules.csv").exists() else None
    CO = pd.read_csv(mixdir / "code_override.csv", dtype=str, keep_default_na=False, encoding="utf-8-sig") if (mixdir / "code_override.csv").exists() else None
    LOG = G.setdefault("_MIX_LOG", [])
    real = pd.read_excel
    def read_excel(path, *a, **k):
        d = real(path, *a, **k)
        if str(path) in fixed_paths:
            key = path_key[str(path)]
            cols = [_nh(c) for c in d.columns]; d.columns = cols
            miss = [c for c in cols if c not in ren]
            if miss: raise SystemExit(f"column(s) of {pathlib.Path(path).name} not in column_map_fixed.csv: {miss}")
            if NR is not None and key in set(NR.key):
                r = NR[NR.key == key].iloc[0]; words = r.must_contain.split(";"); L = int(r.length)
                v = d["氏名(新字)"].astype(object).where(d["氏名(新字)"].notna(), "").astype(str).str.strip()
                hit = v.map(lambda x: len(x) == L and all(w in x for w in words))
                vals = set(v[hit])
                if len(vals) > 1: raise SystemExit(f"{key}: more than one placeholder value ({len(vals)})")
                if int(hit.sum()) != int(r.expected_rows): raise SystemExit(f"{key}: placeholder rows {int(hit.sum())} != expected {r.expected_rows}")
                for c in r.blank_cols.split(";"): d.loc[hit.values, _nh(c)] = None
                LOG.append(dict(key=key, rule="placeholder name -> empty", rows=int(hit.sum())))
            if CO is not None and key in set(CO.key):
                o = CO[CO.key == key]; mg = pd.to_numeric(d["管理番号"], errors="coerce")
                for r in o.itertuples():
                    ix = d.index[mg == int(r.mgmt)]
                    if len(ix) != 1 or int(pd.to_numeric(d.loc[ix[0], "社番"])) != int(r.k_fixed):
                        raise SystemExit(f"{key}: 管理番号 {r.mgmt} not found once with 社番 {r.k_fixed}")
                    d.loc[ix[0], "社番"] = int(r.k_use)
                LOG.append(dict(key=key, rule="社番 override", rows=len(o)))
            rk = ren_key.get(key, ren)
            if key in ren_key: LOG.append(dict(key=key, rule="column map override: " + "; ".join(f"{a}->{b}" for a, b in zip(KO[KO.key == key].source_col, KO[KO.key == key].header_for_01)), rows=len(d)))
            d.columns = [rk[c] for c in cols]
        return d
    G["pd"].read_excel = read_excel
    G["_MIX_FIXED_PATHS"] = fixed_paths
    return G, tail

if __name__ == "__main__":
    s01, rc, rf, work, conf, mixdir = sys.argv[1:7]
    G, tail = build_namespace(s01, rc, rf, work, conf, mixdir)
    print("fixed files:", sorted(pathlib.Path(p).name for p in G["_MIX_FIXED_PATHS"]))
    exec(compile(tail, s01, "exec"), G)
    print("value rules applied:", G["_MIX_LOG"])
    pd.DataFrame(G["_MIX_LOG"]).to_csv(pathlib.Path(work) / "mixload_rules_applied.csv", index=False, encoding="utf-8-sig")
