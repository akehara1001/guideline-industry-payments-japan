# -*- coding: utf-8 -*-
# Reference script from the 2026-10-04 pilot. Run with the working directory set to <project>\work (reads C.pkl, B.pkl there).
# Prints aggregate numbers only.
import pandas as pd, numpy as np, re, unicodedata
C=pd.read_pickle("C.pkl"); B=pd.read_pickle("B.pkl")
C=C[C.ind=="pharma"].copy(); B=B[B.ind=="pharma"].copy()
def nk(s): return "" if s is None or (isinstance(s,float) and np.isnan(s)) else re.sub(r"[\s　]+","",unicodedata.normalize("NFKC",str(s)))
def kc(x):
    try: return str(int(float(x)))
    except Exception: return nk(x)
C["k"]=C["code"].map(kc); B["k"]=B["code"].map(kc)
UNIV={"北海道大学":[],"旭川医科大学":[],"札幌医科大学":[],"弘前大学":[],"岩手医科大学":[],"東北大学":[],"東北医科薬科大学":[],"秋田大学":[],"山形大学":[],"福島県立医科大学":[],"筑波大学":[],"自治医科大学":[],"獨協医科大学":["独協医科大学"],"群馬大学":[],"埼玉医科大学":[],"防衛医科大学校":[],"千葉大学":[],"国際医療福祉大学":[],"東京大学":[],"東京医科歯科大学":["東京科学大学"],"杏林大学":[],"慶應義塾大学":["慶応義塾大学"],"順天堂大学":[],"昭和大学":["昭和医科大学"],"帝京大学":[],"東京医科大学":[],"東京慈恵会医科大学":["慈恵会医科大学"],"東京女子医科大学":[],"東邦大学":[],"日本大学":[],"日本医科大学":[],"横浜市立大学":[],"北里大学":[],"聖マリアンナ医科大学":[],"東海大学":[],"新潟大学":[],"富山大学":[],"金沢大学":[],"金沢医科大学":[],"福井大学":[],"山梨大学":[],"信州大学":[],"岐阜大学":[],"浜松医科大学":[],"名古屋大学":[],"名古屋市立大学":[],"愛知医科大学":[],"藤田医科大学":["藤田保健衛生大学"],"三重大学":[],"滋賀医科大学":[],"京都大学":[],"京都府立医科大学":[],"大阪大学":[],"大阪公立大学":["大阪市立大学"],"大阪医科薬科大学":["大阪医科大学"],"関西医科大学":[],"近畿大学":[],"神戸大学":[],"兵庫医科大学":[],"奈良県立医科大学":[],"和歌山県立医科大学":[],"鳥取大学":[],"島根大学":[],"岡山大学":[],"川崎医科大学":[],"広島大学":[],"山口大学":[],"徳島大学":[],"香川大学":[],"愛媛大学":[],"高知大学":[],"九州大学":[],"福岡大学":[],"久留米大学":[],"産業医科大学":[],"佐賀大学":[],"長崎大学":[],"熊本大学":[],"大分大学":[],"宮崎大学":[],"鹿児島大学":[],"琉球大学":[]}
PAT=[(u,a) for u,al in UNIV.items() for a in [u]+al]; PAT.sort(key=lambda x:-len(x[1]))
urx=re.compile("|".join(re.escape(a) for _,a in PAT)); amap={a:u for u,a in PAT}
def univ(s):
    m=urx.search(s)
    if not m: return None
    # guard: '西日本大学' etc. not in list; '東京大学' inside e.g. '東京大学' ok
    return amap[m.group(0)]
SPEC=[("心臓血管外科",r"心臓血管外科|心臓外科|血管外科|胸部外科|心臓大血管"),("脳神経外科",r"脳神経外科|脳外科"),("呼吸器外科",r"呼吸器外科"),
 ("消化器外科",r"消化器.{0,6}外科|消化管外科|肝胆膵.{0,4}外科|胃腸外科|大腸.{0,4}外科|食道.{0,3}外科|移植外科"),("乳腺",r"乳腺"),("整形外科",r"整形"),("形成外科",r"形成"),
 ("泌尿器",r"泌尿器|腎泌尿"),("産婦人科",r"産婦人科|産科|婦人科|女性|周産期"),("小児",r"小児|新生児"),("眼科",r"眼科|視覚"),("耳鼻咽喉",r"耳鼻|頭頸部"),("皮膚",r"皮膚"),
 ("精神",r"精神|心療"),("麻酔",r"麻酔|疼痛|ペイン"),("放射線",r"放射線|画像診断|核医学"),("循環器",r"循環器|心臓内科|心血管|不整脈"),("消化器内科",r"消化器|消化管|肝臓|胃腸|肝胆膵|内視鏡"),
 ("呼吸器内科",r"呼吸器"),("血液",r"血液"),("腎臓",r"腎"),("糖尿病内分泌",r"糖尿|内分泌|代謝"),("神経内科",r"神経内科|脳神経内科|神経学|神経病態|脳卒中"),
 ("リウマチ膠原病",r"リウマチ|膠原|免疫|アレルギー"),("腫瘍",r"腫瘍|がん|癌|化学療法"),("感染",r"感染"),("救急",r"救急|集中治療"),("薬剤",r"薬剤|薬学"),("外科その他",r"外科"),("内科その他",r"内科")]
SPEC=[(k,re.compile(p)) for k,p in SPEC]
def spec(s):
    for k,p in SPEC:
        if p.search(s): return k
    return None
B["txt"]=(B["recip"].map(nk)+B["dept"].map(nk)); C["txt"]=(C["inst"].map(nk)+C["dept"].map(nk))
for df in (B,C):
    u=pd.Series(df["txt"].unique()); m=pd.DataFrame({"txt":u,"univ":u.map(univ),"spec":u.map(spec)})
    df[["univ","spec"]]=df[["txt"]].merge(m,on="txt",how="left")[["univ","spec"]].values
SD=B[B.b5=="scholarship"].copy()
print("scholarship rows:",len(SD),"amt億 %.1f"%(SD.amt.sum()/1e8))
print("  share of amount with univ: %.1f%% ; with univ+spec: %.1f%%"%(100*SD[SD.univ.notna()].amt.sum()/SD.amt.sum(),100*SD[SD.univ.notna()&SD.spec.notna()].amt.sum()/SD.amt.sum()))
print("  by year univ+spec share:",(SD[SD.univ.notna()&SD.spec.notna()].groupby("year").amt.sum()/SD.groupby("year").amt.sum()).round(2).to_dict())
print("C: share of amount with univ: %.1f%% ; univ+spec: %.1f%%"%(100*C[C.univ.notna()].amt.sum()/C.amt.sum(),100*C[C.univ.notna()&C.spec.notna()].amt.sum()/C.amt.sum()))
print("  by year:",(C[C.univ.notna()&C.spec.notna()].groupby("year").amt.sum()/C.groupby("year").amt.sum()).round(2).to_dict())
SD.to_pickle("SD.pkl"); C[["year","k","company","univ","spec","amt","n","c3","title","name","inst","dept"]].to_pickle("Cp.pkl")
# company-year scholarship totals and stop years
w=SD.pivot_table(index="k",columns="year",values="amt",aggfunc="sum").reindex(columns=range(2017,2024)).fillna(0)
names=B.drop_duplicates("k").set_index("k")["company"]
def stop(r):
    pk=r.max()
    if pk<5e7: return None
    for y in range(2018,2024):
        if r[[z for z in r.index if z>=y]].max()<=0.02*pk and r[[z for z in r.index if z<y]].max()>=0.5*pk: return y
    return None
st=w.apply(stop,axis=1).dropna().astype(int)
print("\nstoppers:",len(st),st.value_counts().sort_index().to_dict())
t=w.loc[st.index].div(1e8).round(2); t.insert(0,"stop",st); t.insert(0,"company",[str(names.get(i))[:14] for i in t.index]); print(t.sort_values("stop").to_string())
cont=w[(w[2023]>=0.5*w.max(axis=1))&(w.max(axis=1)>=5e7)]
print("continuers (2023 >= 50%% of peak, peak>=0.5億): %d"%len(cont)); 
pd.Series(st).to_pickle("stop.pkl"); w.to_pickle("sd_wide.pkl")
