# -*- coding: utf-8 -*-
"""Harmonise the 24 yearly payment workbooks into two long tables.
Usage: python 01_build_tables.py "<project>/data_raw" "<project>/work" "<project>/config"
Output: work/C.pkl (payments to individuals), work/B.pkl (payments to institutions), work/inventory.csv
Columns added: year, ind (pharma/device), kind (C/B), k (company code as string), co (normalised company name),
               catx (category label), c3 or b5 (harmonised category), nm (normalised name), pidn (within-year person number)
The script prints aggregate numbers only. Do not print rows with personal names.
"""
import pandas as pd, numpy as np, glob, os, re, sys, unicodedata, warnings, pathlib
warnings.filterwarnings("ignore")
RAW, WORK, CONF = [pathlib.Path(p) for p in sys.argv[1:4]]; WORK.mkdir(parents=True, exist_ok=True)
try:
    import python_calamine  # noqa
    ENGINE = "calamine"
except Exception:
    ENGINE = "openpyxl"
CFG={ # file prefix -> (sheet, header_row)
 "製薬_C_2016":("2016年C項目",1),"製薬_BC_2017#C":("2017_C",1),"製薬_BC_2017#B":("2017_B",1),
 "製薬_C_2018":("2018年度C項目統合",1),"製薬_C_2019":("C項目並び順",1),"製薬_C_2020":("2020年C項目",1),
 "製薬_C_2021":("C項目",1),"製薬_C_2022":("C項目",1),"製薬_C_2023":("2023年度製薬C目視名寄結果235302",0),
 "製薬_B_2018":("B統合",1),"製薬_B_2019":("2019_B",1),"製薬_B_2020":("B項目並び順",1),"製薬_B_2021":("B項目",1),
 "製薬_B_2022":("B項目",1),"製薬_B_2023":("2023年度製薬B統合",1),
 "機器_C_2019":("Sheet1",0),"機器_C_2020":("Sheet1",0),"機器_C_2021":("sheet1",0),"機器_C_2022":("2022年度機器C項目目視済統合",0),
 "機器_C_2023":("2023年度機器C統合",1),
 "機器_B_2019":("医療機器B",1),"機器_B_2020":("医療機器B",1),"機器_B_2021":("2021年度B統合",1),"機器_B_2022":("2022年度B項目統合",0),
 "機器_B_2023":("2023年度機器B統合wk",1)}
def nh(c): return re.sub(r"\s+","",unicodedata.normalize("NFKC",str(c)))
def nk(s): return "" if s is None or (isinstance(s,float) and np.isnan(s)) else re.sub(r"[\s　]+","",unicodedata.normalize("NFKC",str(s)))
# Kanji variants folded for the blocking key nm only (the original spelling stays in name / name_raw)
VAR=str.maketrans("髙﨑嶋嶌邉邊濵濱栁國德瀨黑齋齊龍澤眞廣","高崎島島辺辺浜浜柳国徳瀬黒斎斉竜沢真広")
def pick(cols,pats):
    for p in pats:
        for c in cols:
            if re.fullmatch(p,c): return c
    return None
P_C=dict(
 pid=[r"氏名No\.?",r"ID"],
 name=[r"氏名\(新字変換後\)",r"氏名\(全角\)目視後",r"氏名\(全角\)変換後",r"氏名\(変換後\)",r"氏名\(置換後\)",r"氏名\(新字\)",r"氏名\(全角\)",r"氏名"],
 name_raw=[r"氏名\(全角\)変換前",r"氏名\(全角\)",r"氏名",r"氏名\(変換後\)",r"氏名\(置換後\)"],
 dup=[r"氏名\(同姓同名\)設定",r"氏名\(同姓同名\)",r"氏名\(同姓同名分類\)置換後",r"名寄せ結果"],
 inst=[r"所属\(団体・施設名・全角\)変換後",r"所属\(団体・施設名・全角\)",r"所属\(団体・施設名\)",r"所属1\(団体・施設名・全角\)",r"所属\(施設・団体名\)",r"病院名\(変換後\)"],
 dept=[r"所属\(変換後\)",r"所属",r"所属2\(全角\)",r"所属2",r"部署"],
 title=[r"役職\(変換後\)",r"役職"], code=[r"社番"], company=[r"医療機器メーカー",r"製薬会社",r"製薬会社名"],
 cat_raw=[r"名目"], cat=[r"名目統合"], n=[r"件数"], amt=[r"金額"])
P_B=dict(
 recip=[r"団体・施設名・イベント名\(.*変換後.*",r"団体・施設名・イベント名",r"支払先"], recip_raw=[r"団体・施設名・イベント名\(変換前\)?",r"団体・施設名・イベント名",r"支払先"],
 dept=[r"所属\(.*変換後.*",r"所属",r"Division"], title=[r"役職"], code=[r"社番"], company=[r"医療機器メーカー",r"製薬会社",r"製薬企業"],
 cat_raw=[r"名目"], cat=[r"名目統合"], n=[r"件数"], amt=[r"金額"])
FILES={unicodedata.normalize("NFC",os.path.basename(f)):f for f in glob.glob(str(RAW/"**"/"*.xlsx"),recursive=True)}
def find(pre):
    hit=[f for b,f in FILES.items() if b.startswith(pre+"__")]
    if len(hit)!=1: raise SystemExit(f"expected exactly one file for prefix {pre}, found {len(hit)}")
    return hit[0]
def load(path,key):
    sheet,h=CFG[key]
    d=pd.read_excel(path,sheet_name=sheet,header=h,engine=ENGINE,dtype=object)
    d.columns=[nh(c) for c in d.columns]
    kind="C" if ("_C_" in key or key.endswith("#C")) else "B"
    P=P_C if kind=="C" else P_B
    out=pd.DataFrame(index=d.index); used={}
    for k,pats in P.items():
        c=pick(list(d.columns),pats); used[k]=c
        out[k]=d[c] if c else None
    m=re.search(r"_(20\d\d)",key); out["year"]=int(m.group(1)); out["ind"]="pharma" if key.startswith("製薬") else "device"; out["kind"]=kind
    out["amt"]=pd.to_numeric(out["amt"],errors="coerce"); out["n"]=pd.to_numeric(out["n"],errors="coerce")
    out=out[~(out.drop(columns=["year","ind","kind"]).isna().all(axis=1))]
    out=out[out["amt"].notna() | out["company"].notna()]
    return out,used
def kc(x):
    try: return str(int(float(x)))
    except Exception: return nk(x)
def cname(s):
    s=nk(s); s=re.sub(r"^\d+_","",s)
    return s.replace("株式会社","").replace("(株)","")
allC=[];allB=[]
for key in CFG:
    pre=key.split("#")[0]
    o,used=load(find(pre),key)
    miss=[k for k,v in used.items() if v is None]
    print(f"{key:14s} rows={len(o):7d} missing_fields={miss}")
    (allC if o.kind.iloc[0]=="C" else allB).append(o)
C=pd.concat(allC,ignore_index=True); B=pd.concat(allB,ignore_index=True)
for df in (C,B):
    for c in df.columns:
        if df[c].dtype==object: df[c]=df[c].map(lambda v: None if v is None or (isinstance(v,float) and np.isnan(v)) else str(v).strip())
    df["catx"]=df["cat"].where(df["cat"].notna(),df["cat_raw"])
    df["k"]=df["code"].map(kc); df["co"]=df["company"].map(cname)
mc=pd.read_csv(CONF/"category_map_C.csv").set_index("catx")["c3"]; mb=pd.read_csv(CONF/"category_map_B.csv").set_index("catx")["b5"]
C["c3"]=C["catx"].map(mc).fillna("unk"); B["b5"]=B["catx"].map(mb).fillna("unk")
C["nm"]=C["name"].where(C["name"].notna(),C["name_raw"]).map(nk).str.translate(VAR); C["pidn"]=pd.to_numeric(C["pid"],errors="coerce")
B["recip"]=B["recip"].where(B["recip"].notna(),B["recip_raw"])
C.to_pickle(WORK/"C.pkl"); B.to_pickle(WORK/"B.pkl")
inv=pd.concat([
 C.groupby(["kind","ind","year"]).agg(rows=("amt","size"),pid_fill=("pidn",lambda s:round(100*s.notna().mean(),1)),companies=("co","nunique"),oku=("amt",lambda s:round(s.sum()/1e8,1))).reset_index(),
 B.groupby(["kind","ind","year"]).agg(rows=("amt","size"),companies=("co","nunique"),oku=("amt",lambda s:round(s.sum()/1e8,1)),scholarship_oku=("amt",lambda s:round(s[B.loc[s.index,"b5"]=="scholarship"].sum()/1e8,1))).reset_index()])
inv.to_csv(WORK/"inventory.csv",index=False,encoding="utf-8-sig"); print(inv.to_string(index=False)); print("C",C.shape,"B",B.shape)
