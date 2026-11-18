# -*- coding: utf-8 -*-
"""Stage 22 (2026-11-03): the tables and figures of manuscript v1, in English, generated from the results ledger only.
The stage 17-21 version (Chinese labels, old numbering) is kept in out/archive_stage22/scripts/113_paper_tables.py; its outputs in
out/archive_stage22/paper/. Rerunning that copy reproduced every old table byte for byte before this rewrite (only selfcheck.md carries a date).

Numbering follows the first mention in the v1 text:
  main    Table 1  public form of the authors' declarations and the guidelines' own statements (totals only, no society names)
          Table 2  agreement with the three reference sets and between repeated extractions (manual check skipped on 2026-11-03: its rows are gone)
          Table 3  main analysis set, pharmaceutical and device, three columns (main estimate, flagged guidelines excluded, frozen pipeline output)
          Fig. 1   flow from the guideline census to the analysis sets;  Fig. 2  forest plot per guideline, main analysis set
  suppl.  Table S1 the seven public forms;  S2 company-name corrections;  S3 the two channels;  S4 every guideline;  S5 period-inferred layer (with
          the narrow window);  S6 every sampled society;  S7 pharmaceutical-device overlap;  S8 dermatology thresholds at the society bylaw amount
          Fig. S1  forest plot per guideline, period-inferred layer
Society names appear only in the supplementary tables. The figures carry letter codes for the lead society; Table S6 defines them.
Every number comes from out/RESULTS_LEDGER.csv, through a machine key (work/ledger/keys.csv) or, for the narrow-window rows that have no key, by
ledger number. No data number is written in this script. Text (labels, English names of societies and guidelines, definitions) is written here.
Each table is written as .md (readable), .csv (one line per cell with its ledger numbers) and .json (the layout read by the docx builder of the
manuscript). The self-check reads every number of every cell again and looks for it in the cited ledger rows; it also checks that every footnote
symbol appears both in a note and in the table, that Fig. 1 and Tables 3 and S5 carry the same counts, the PDF font sizes and the PNG resolution.
Usage: python 113_paper_tables.py "<project>"
Reads  out/RESULTS_LEDGER.csv, work/ledger/keys.csv; text only from config/guidelines_analysis_sets.csv, work/expansion/society_rank.csv,
       work/stage18/report_numbers.pkl (the lead society of each guideline)
Writes out/paper/: table1-3, tableS1-S8 (.md .csv .json), figure1_flow, figure2_forest_main, figureS1_forest_inferred (.pdf .png .csv),
       selfcheck.md, README.md. Prints counts only.
"""
import pandas as pd, sys, pathlib, re, time, json
from collections import Counter

P = pathlib.Path(sys.argv[1]); O = P/"out"/"paper"; O.mkdir(parents=True, exist_ok=True)
rd = lambda f: pd.read_csv(f, dtype=str, keep_default_na=False, encoding="utf-8-sig")
LG = rd(P/"out"/"RESULTS_LEDGER.csv").set_index("编号"); KY = rd(P/"work"/"ledger"/"keys.csv"); K2 = dict(zip(KY.key, KY["编号"]))
AS = rd(P/"config"/"guidelines_analysis_sets.csv").set_index("key")
RANK = rd(P/"work"/"expansion"/"society_rank.csv"); FRAME = list(RANK.society_id)
GSOC = {k: v["soc"] for k, v in pd.read_pickle(P/"work"/"stage18"/"report_numbers.pkl")["NUM"]["B7"].items()}
SKILL = pathlib.Path(r"C:\Users\<user>\Documents\ClaudeCode\nature-skills\skills\nature-figure\scripts")


def val(key):
    i = K2[key]; return LG.loc[i, "数值"], i
def lval(i):
    return LG.loc[i, "数值"], i
def parts(key):
    v, i = val(key); return [x.strip() for x in v.split(" / ")], i
def fparts(key):
    v, i = val(key); return [x.strip() for x in v.split("；")], i
SH = re.compile(r"^([\d.]+)，95% CI \[([\d.]+), ([\d.]+)\]（([\d,]+)/([\d,]+)）$")
def sh(s):
    m = SH.match(s.strip())
    if m: return dict(e=m[1], lo=m[2], hi=m[3], k=m[4], n=m[5], ci=f"[{m[2]}, {m[3]}]")
    if s.strip().startswith("—"): return None
    raise ValueError(s)
def est_ci(s):
    d = sh(s); return f"{d['e']} {d['ci']}" if d else "—"
def est_ci_kn(s):
    d = sh(s); return f"{d['e']} {d['ci']} ({d['k']}/{d['n']})" if d else "—"
def rate_ci(s):                                                       # '0.97，95% CI [0.94, 0.98]' -> '0.97 [0.94, 0.98]'
    return re.sub(r"，95% CI ", " ", s.strip())
MED = re.compile(r"^([\d.]+)（四分位距 ([\d.]+)–([\d.]+)，[\d,]+ 部）$")
def med(s):
    m = MED.match(s.strip()); return f"{m[1]} ({m[2]}–{m[3]})" if m else s
def gl_n(s):                                                          # '12（7 / 5）' -> '12 (7 / 5)'
    return s.replace("（", " (").replace("）", ")")

# ================================================================ English text (labels, not data)
SOC_EN = {"S029": "Japanese Dermatological Association", "S008": "Japanese Society of Hematology", "S022": "Japanese Circulation Society",
          "S051": "Japan Diabetes Society", "S030": "Japanese Urological Association", "S059": "Japan College of Rheumatology",
          "SN0011": "Japanese Association of Cardiovascular Intervention and Therapeutics", "S078": "Japan Society of Clinical Oncology",
          "S025": "Japanese Orthopaedic Association", "S021": "Japanese Society of Gastroenterology", "S077": "Japan Gastroenterological Endoscopy Society",
          "S107": "Japanese Society of Medical Oncology", "S057": "Japanese Respiratory Society", "SN0012": "Japanese Heart Rhythm Society",
          "S042": "Japanese Society of Allergology", "S102": "Japanese Breast Cancer Society", "S119": "Japan Lung Cancer Society",
          "S053": "Japanese Society of Neurology", "S062": "Japan Society of Hepatology", "S058": "Japanese Society of Nephrology",
          "S047": "Japan Neurosurgical Society", "S130": "Japanese Society for Neuroendovascular Therapy", "S046": "Japanese Association for Thoracic Surgery",
          "S045": "Japanese Society of Anesthesiologists", "S101": "Japan Society for Endoscopic Surgery"}
assert set(SOC_EN) == set(FRAME)
CODE = {s: chr(ord("A") + j) for j, s in enumerate(FRAME)}           # letter codes in the order of the sampling list
GL = {  # key: (short label for the figures, English title for Table S4)
    "breast_2022": ("Breast cancer", "Evidence-based clinical practice guidelines for breast cancer"),
    "lung_2022": ("Lung cancer", "Clinical practice guidelines for lung cancer"),
    "lung_2023": ("Lung cancer", "Clinical practice guidelines for lung cancer"),
    "lung_2024": ("Lung cancer", "Clinical practice guidelines for lung cancer"),
    "s119_2025_lung_cancer": ("Lung, pleural and thymic tumors", "Clinical practice guidelines for lung cancer, including pleural mesothelioma and thymic tumors"),
    "jds_dm_2024": ("Diabetes", "Clinical practice guideline for diabetes"),
    "s051_2023_elderly_dm": ("Diabetes in older adults", "Clinical practice guideline for diabetes in older adults"),
    "s051_2024_pediatric_dm": ("Diabetes in children and adolescents", "Consensus guideline for diabetes in children and adolescents"),
    "jcs_arrhythmia_2024": ("Arrhythmia treatment, update", "Focused update on the treatment of arrhythmia"),
    "jcs_cad_prev_2023": ("Primary prevention of coronary disease", "Guideline on the primary prevention of coronary artery disease"),
    "jcs_2025_pte_ph": ("Pulmonary embolism, DVT and PH", "Guideline on pulmonary thromboembolism, deep vein thrombosis and pulmonary hypertension"),
    "jcs_2025_achd": ("Adult congenital heart disease", "Guideline on adult congenital heart disease"),
    "jcs_2025_school_screening": ("School heart screening, update", "Focused update on school heart screening"),
    "jcs_2025_heart_failure": ("Heart failure", "Guideline on heart failure"),
    "jcs_2025_heart_transplant": ("Heart transplantation", "Guideline on heart transplantation"),
    "jcs_2025_pad_fu": ("Peripheral artery disease, update", "Focused update on peripheral artery disease"),
    "jcs_2024_diversity": ("Diversity in cardiovascular care", "Guideline on cardiovascular care with consideration of diversity"),
    "jcs_2024_genetic_testing": ("Cardiovascular genetic testing", "Guideline on genetic testing and genetic counseling in cardiovascular disease"),
    "jcs_2023_mcs": ("Mechanical circulatory support, update", "Focused update on percutaneous cardiopulmonary support, ECMO and mechanical circulatory support"),
    "jcs_2023_myocarditis": ("Myocarditis", "Guideline on the diagnosis and treatment of myocarditis"),
    "jcs_2023_sleep_apnea": ("Sleep-disordered breathing, cardiology", "Guideline on sleep-disordered breathing in cardiovascular medicine"),
    "jcs_2023_vsa_cmd": ("Coronary spasm, microvascular disease", "Focused update on vasospastic angina and coronary microvascular dysfunction"),
    "jcs_2022_noncardiac_surgery": ("Heart disease in noncardiac surgery", "Guideline on the assessment and management of heart disease in noncardiac surgery"),
    "jcs_2022_stable_cad_fu": ("Stable coronary disease, update", "Focused update on the diagnosis and treatment of stable coronary artery disease"),
    "jcs_2022_arrhythmia_risk": ("Arrhythmia diagnosis and risk", "Guideline on the diagnosis and risk assessment of arrhythmia"),
    "jcs_2022_achd_postop": ("Congenital heart disease after surgery", "Guideline on long-term management and interventions after surgery for congenital heart disease"),
    "jcs_2022_pad": ("Peripheral artery disease", "Guideline on peripheral artery disease"),
    "s042_2022_anaphylaxis": ("Anaphylaxis", "Anaphylaxis guidelines"),
    "s053_2022_mg_lems": ("Myasthenia gravis, Lambert–Eaton", "Clinical practice guidelines for myasthenia gravis and Lambert–Eaton myasthenic syndrome"),
    "s053_2023_als": ("Amyotrophic lateral sclerosis", "Clinical practice guidelines for amyotrophic lateral sclerosis"),
    "s053_2023_ms_nmosd": ("Multiple sclerosis and NMOSD", "Clinical practice guidelines for multiple sclerosis and neuromyelitis optica spectrum disorder"),
    "s053_2024_cidp_mmn": ("CIDP and MMN", "Clinical practice guidelines for chronic inflammatory demyelinating polyradiculoneuropathy and multifocal motor neuropathy"),
    "s053_2024_gbs": ("Guillain–Barré and Fisher syndromes", "Clinical practice guidelines for Guillain–Barré syndrome and Fisher syndrome"),
    "s053_2025_ham": ("HTLV-1-associated myelopathy", "Clinical practice guidelines for HTLV-1-associated myelopathy"),
    "s058_2023_ckd": ("Chronic kidney disease", "Evidence-based clinical practice guideline for chronic kidney disease"),
    "s029_2025_cutaneous_lymphoma": ("Cutaneous lymphoma", "Clinical practice guidelines for cutaneous lymphoma"),
    "s029_2025_porphyria": ("Porphyria", "Clinical practice guidelines for porphyria"),
    "s029_2024_alopecia_areata": ("Alopecia areata", "Clinical practice guidelines for alopecia areata"),
    "s029_2024_atopic_dermatitis": ("Atopic dermatitis", "Clinical practice guidelines for atopic dermatitis"),
    "s029_2023_acne_rosacea": ("Acne vulgaris and rosacea", "Guidelines for the treatment of acne vulgaris and rosacea"),
    "s029_2023_hailey_hailey": ("Hailey–Hailey disease", "Clinical practice guidelines for familial benign chronic pemphigus (Hailey–Hailey disease)"),
    "s029_2023_hyperhidrosis": ("Primary focal hyperhidrosis", "Clinical practice guidelines for primary focal hyperhidrosis"),
    "s030_2023_hematuria": ("Hematuria", "Guidelines for the diagnosis of hematuria"),
    "s030_2023_upper_tract_uc": ("Upper tract urothelial carcinoma", "Clinical practice guidelines for renal pelvic and ureteral cancer"),
    "s078_2022_chemo_nephrotoxicity": ("Kidney injury in cancer drug therapy", "Clinical practice guidelines for kidney injury during cancer drug therapy"),
    "s107_2023_extravasation": ("Extravasation in cancer drug therapy", "Joint guidelines on extravasation associated with cancer drug therapy"),
    "s047_2024_brain_tumor_adult": ("Brain tumors, adults", "Clinical practice guidelines for brain tumors: adult brain tumors"),
    "s047_2022_brain_tumor_pediatric": ("Brain tumors, children", "Clinical practice guidelines for brain tumors: pediatric brain tumors"),
    "s029_2025_fungal": ("Cutaneous fungal infections", "Clinical practice guidelines for cutaneous fungal infections"),
    "s029_2025_herpes_zoster": ("Herpes zoster", "Clinical practice guidelines for herpes zoster"),
    "s029_2025_vitiligo": ("Vitiligo vulgaris", "Clinical practice guidelines for vitiligo vulgaris"),
    "s029_2024_tuberous_sclerosis": ("Tuberous sclerosis complex", "Clinical practice guidelines for tuberous sclerosis complex"),
    "s029_2023_dihs": ("Drug hypersensitivity syndrome", "Clinical practice guidelines for drug-induced hypersensitivity syndrome"),
    "s008_2023_hem_genome": ("Genomic testing, hematologic tumors", "Guidelines for genomic testing in hematopoietic tumors"),
    "s030_2025_prostate_screening": ("Prostate cancer screening", "Guidelines for prostate cancer screening"),
    "s030_2024_male_infertility": ("Male infertility", "Clinical practice guidelines for male infertility"),
    "s030_2024_testicular_cancer": ("Testicular cancer", "Clinical practice guidelines for testicular cancer"),
    "s030_2024_urethral_stricture": ("Urethral stricture", "Clinical practice guidelines for urethral stricture"),
    "s030_2023_periop_infection": ("Perioperative infection in urology", "Guidelines for the prevention of perioperative infection in urology"),
    "s030_2023_prostate_cancer": ("Prostate cancer", "Clinical practice guidelines for prostate cancer"),
    "s030_2023_tsc_aml": ("Angiomyolipoma in tuberous sclerosis", "Clinical practice guidelines for renal angiomyolipoma associated with tuberous sclerosis complex"),
    "s030_2023_urolithiasis": ("Urolithiasis", "Clinical guidelines for urolithiasis"),
    "s030_2022_adrenal_incidentaloma": ("Nonfunctioning adrenal tumors", "Clinical practice guidelines for endocrinologically nonfunctioning adrenal tumors"),
    "s030_2022_urologic_trauma": ("Urologic trauma", "Clinical practice guidelines for urologic trauma"),
    "s078_2022_tumor_agnostic_genome": ("Tumor-agnostic genomic medicine", "Guidelines for tumor-agnostic genomic medicine in advanced solid tumors in adults and children"),
    "s077_2024_eus_fna": ("EUS-guided fine-needle aspiration", "Guidelines for endoscopic ultrasound-guided fine-needle aspiration"),
    "s077_2024_ibd_endoscopy": ("IBD endoscopy", "Guidelines for endoscopic practice in inflammatory bowel disease"),
    "s077_2024_nonvariceal_bleeding": ("Nonvariceal upper GI bleeding", "Guidelines for endoscopic management of nonvariceal upper gastrointestinal bleeding"),
    "s057_2025_ph_lung_disease": ("Pulmonary hypertension in lung disease", "Clinical practice guidelines for pulmonary hypertension associated with lung disease"),
    "s057_2024_adult_pneumonia": ("Adult pneumonia", "Clinical practice guidelines for pneumonia in adults"),
    "s057_2022_copd": ("COPD", "Guidelines for the diagnosis and treatment of chronic obstructive pulmonary disease"),
    "s057_2022_pap": ("Pulmonary alveolar proteinosis", "Clinical practice guidelines for pulmonary alveolar proteinosis"),
    "s045_2025_malignant_hyperthermia": ("Malignant hyperthermia", "Guidelines for the management of malignant hyperthermia"),
}
FORM_EN = ["Individual and itemized (auditable)", "Individual, not itemized", "Individual and itemized, no lecture or manuscript fees among the items",
           "Committee-level statement only", "No disclosure", "Individual and itemized, full text not obtained", "Form not known"]
FORM_DEF = ["For each author, the guideline lists company names by payment category (lecture fees, manuscript fees and others). The frozen pipeline can audit this form.",
            "For each author, the guideline lists company names, or only the presence of a relationship, without payment categories. The pipeline matches author × company × category and cannot audit this form.",
            "For each author, the guideline lists companies by payment category, but neither lecture fees nor manuscript fees are among the categories. The guideline was audited; all its units were unassessable and it is only counted.",
            "The guideline gives a conflict-of-interest statement for the committee as a whole, with no individual content.",
            "The guideline gives no conflict-of-interest disclosure.",
            "At the census, the guideline listed company names for each author, but its full text could not be obtained; it was not audited.",
            "The public form could not be determined (the document could not be obtained, or could be read only in a viewer that does not allow download)."]
THR_SRC = {"写在指南里": "guideline", "取自发行学会的规定": "society rule", "门槛不清（学会文件不一致）": "unclear", "未写明": "not stated"}
def thr_src_en(s):                                                    # '写在指南里：1、门槛不清（学会文件不一致）：6' -> 'guideline: 1; unclear: 6'
    out = []
    for part in s.split("、"):
        a, b = part.rsplit("：", 1); out.append(f"{THR_SRC[a]}: {b}")
    return "; ".join(out)
def thr_cell(s):                                                      # '50（学会规定） / 50（学会规定）' -> ('50 / 50', 'Society rule')
    amt = re.sub(r"（.*?）", "", s).strip()
    src = "Society rule" if "学会规定" in s else ("Unclear" if "门槛不清" in s else ("Not stated" if "未写明" in s else "Guideline"))
    return amt, src

TXT = lambda s: (s, [], "label")
CELLS, SPECS = [], {}
SYMS = "✱†‡§¶‖"


class Table:
    def __init__(self, name, title, tcite=()):
        self.name, self.title, self.tcite, self.panels, self.notes = name, title, set(tcite), [], []
    def panel(self, label, header, hcite=None):
        self.panels.append(dict(label=label, header=header, hcite=hcite or {}, rows=[]))
    def row(self, cells, key=""):
        self.panels[-1]["rows"].append((key, cells))
    def note(self, text, cite=()):
        self.notes.append((text, set(cite)))
    def write(self):
        md = [f"# {self.title}", ""]
        cs = [dict(table=self.name, panel="", r="", c="", rkey="（标题）", ckey="", text=self.title, ledger_ids="|".join(sorted(self.tcite)), role="label")]
        spec = dict(name=self.name, title=self.title, panels=[], notes=[n for n, _ in self.notes])
        for pi, p in enumerate(self.panels):
            if p["label"]: md += [f"**{p['label']}**", ""]
            md += ["| " + " | ".join(p["header"]) + " |", "|" + "---|" * len(p["header"])]
            md += ["| " + " | ".join(c[0] for c in cells) + " |" for _, cells in p["rows"]] + [""]
            if p["label"]:
                cs.append(dict(table=self.name, panel=pi, r="", c="", rkey="（面板）", ckey="", text=p["label"], ledger_ids="", role="label"))
            for ci, h in enumerate(p["header"]):
                cs.append(dict(table=self.name, panel=pi, r="", c=ci, rkey="（表头）", ckey=h, text=h, ledger_ids="|".join(sorted(p["hcite"].get(h, []))), role="label"))
            for ri, (key, cells) in enumerate(p["rows"]):
                assert len(cells) == len(p["header"]), (self.name, key)
                for ci, (h, c) in enumerate(zip(p["header"], cells)):
                    cs.append(dict(table=self.name, panel=pi, r=ri, c=ci, rkey=key, ckey=h, text=c[0], ledger_ids="|".join(c[1]), role=c[2]))
            spec["panels"].append(dict(label=p["label"], header=p["header"], rows=[[c[0] for c in cells] for _, cells in p["rows"]],
                                       keys=[k for k, _ in p["rows"]]))
        md += [n for n, _ in self.notes] + ["", f"Numbers: `{self.name}.csv` (ledger number of every cell). Script: `scripts/113_paper_tables.py`, reads `out/RESULTS_LEDGER.csv` only.", ""]
        cs += [dict(table=self.name, panel="", r="", c="", rkey="（注）", ckey="", text=n, ledger_ids="|".join(sorted(ci)), role="label") for n, ci in self.notes]
        (O/f"{self.name}.md").write_text("\n".join(md), encoding="utf-8")
        df = pd.DataFrame(cs); df.to_csv(O/f"{self.name}.csv", index=False, encoding="utf-8-sig")
        (O/f"{self.name}.json").write_text(json.dumps(spec, ensure_ascii=False, indent=1), encoding="utf-8")
        CELLS.append(df); SPECS[self.name] = self
        return df


_, SCOPE_ID = val("B1|total|n")                                     # its 说明 carries '25 个学会、标题年份 2022–2025 年'
_, MAIN_ID = val("sets|main"); _, INF_ID = val("sets|inferred"); _, AN_ID = val("B1b|total")

# ================================================================ Table 1
T1 = Table("table1_public_forms", "Table 1. Public form of authors' declarations and the guidelines' own statements on development funding and "
           "society-level conflicts of interest: clinical practice guidelines with title years 2022 to 2025 issued by 25 medical societies in Japan✱", [SCOPE_ID])
T1.panel("Panel A. Public form of authors' declarations, all guidelines", ["Public form†", "Guidelines"])
v, i = val("B1|total|n"); T1.row([TXT("All guidelines"), (v, [i], "value")], "all")
for j, f_ in enumerate(FORM_EN):
    v, i = val(f"B1|total|form{j}"); T1.row([TXT(f_), (v, [i], "value")], f"form{j}")
T1.panel("Panel B. Statements in the audited guidelines‡", ["Statement", "Yes", "No", "Unclear"])
for it, lab in (("item1", "Source of development funding stated"), ("item2", "Source was the issuing societies' own funds§"),
                ("item3", "Society- or committee-level industry funding or organizational conflict of interest mentioned¶")):
    p_, i = parts(f"fs|全部|{it}"); T1.row([TXT(lab)] + [(x, [i], "value") for x in p_], it)
T1.panel("Panel C. Content of the society-level statement among guidelines answering yes in the last row of panel B‖", ["Content", "Guidelines"])
q, i = fparts("fs|sub|全部")
for j, lab in zip((1, 2, 3, 4), ("General sentence only", "Names of paying companies listed", "Amounts stated", "Handling of the society-level conflict for guideline content stated")):
    T1.row([TXT(lab), (q[j], [i], "value")], f"sub{j}")
T1.note("✱ A guideline issued jointly by several societies is counted once. Panels B and C are model judgments on sentences retrieved from each guideline's documents (Supplementary Methods 7).")
T1.note("† Definitions of the seven forms are in Table S1.")
T1.note("‡ Audited guidelines are those with individual and itemized declarations whose disclosed items included lecture fees or manuscript fees (the analysis set). Unclear means the statement was ambiguous, or no statement was found in a partial document.")
T1.note("§ Yes means every stated source was the issuing societies' own funds; unclear includes guidelines that stated no source.")
T1.note("¶ Statements about the society, the committee or the developing organization rather than individual authors: funds received, or stated as not received, from companies, or management of organizational conflicts of interest.")
T1.note("‖ A guideline could meet more than one content category.")
T1.write()

# ================================================================ Table 2
T2 = Table("table2_validation", "Table 2. Agreement of the extraction pipeline with reference sets and between repeated extractions✱")
T2.panel("", ["Comparison", "Units compared", "Agreeing units", "Agreement [95% CI]"])
for tag, lab in (("heldout", "Earlier frozen version vs manual data entry, held-out guidelines†"), ("r8", "Earlier frozen version vs a published final adjudication‡"),
                 ("dev", "Final frozen version vs the corrected adjudication, development guidelines§"),
                 ("rep9", "Final frozen version, repeated extraction, first sample¶"), ("rep12", "Final frozen version, repeated extraction, second sample¶"),
                 ("rep13", "Final frozen version, repeated extraction, third sample¶")):
    p_, i = parts(f"T2|{tag}"); T2.row([TXT(lab), (p_[0], [i], "value"), (p_[1], [i], "value"), (rate_ci(p_[2]), [i], "value")], tag)
T2.note("✱ Units are author × company × year units (by payment category where the reference had categories) that could be evaluated. Agreement is the share of units with the same judgment, with Wilson 95% confidence intervals (CIs).")
T2.note("† Cancer guidelines not used to develop this version, compared with the manual data entry of a previous audit {ref:r8letter}.")
T2.note("‡ The final adjudication table of the same published audit, lecture fees only.")
T2.note("§ Guidelines used to develop the final version; three-way judgment (declared, undeclared, unassessable) against the published adjudication after correction.")
T2.note("¶ Guidelines drawn at random from the census and extracted twice with the final version; agreement between the two runs measures reproducibility, not accuracy.")
T2.write()


# ================================================================ Table 3 and Table S5
def results_table(name, title, tab, tcite, narrow=False):
    T = Table(name, title, tcite)
    H = ["Industry", "Measure", "Main estimate†", "Flagged guidelines excluded‡", "Frozen pipeline output§"]
    T.panel("Panel A. Assessed declaration period" if narrow else "", H)
    for ind, il in (("pharma", "Pharmaceutical"), ("device", "Medical device")):
        def cells(kind, pick):
            out = []
            for col in ("r12", "excl", "frozen"):
                v, i = val(f"{tab}|{kind}|{ind}|0|{col}"); out.append((pick(v), [i], "value"))
            return out
        T.row([TXT(il), TXT("Evaluable units, before deduplication")] + cells("raw", lambda v: sh(v)["n"] if sh(v) else "0"), f"{ind}.raw_n")
        T.row([TXT(il), TXT("Evaluable units, after deduplication¶")] + cells("dedup", lambda v: sh(v)["n"] if sh(v) else "0"), f"{ind}.dd_n")
        T.row([TXT(il), TXT("Undeclared units, after deduplication")] + cells("dedup", lambda v: sh(v)["k"] if sh(v) else "0"), f"{ind}.dd_k")
        T.row([TXT(il), TXT("Proportion undeclared [95% CI]")] + cells("dedup", est_ci), f"{ind}.dd_p")
        T.row([TXT(il), TXT("Authors with at least one evaluable unit")] + cells("person", lambda v: sh(v)["n"] if sh(v) else "0"), f"{ind}.pp_n")
        T.row([TXT(il), TXT("Authors with at least one undeclared unit")] + cells("person", lambda v: sh(v)["k"] if sh(v) else "0"), f"{ind}.pp_k")
        T.row([TXT(il), TXT("Proportion of authors [95% CI]")] + cells("person", est_ci), f"{ind}.pp_p")
        for j, lab in zip((1, 2, 3, 4), ("Authors with no undeclared unit‖", "Authors with one undeclared unit‖", "Authors with two to four undeclared units‖", "Authors with five or more undeclared units‖")):
            out = []
            for col in ("r12", "excl", "frozen"):
                p_, i = parts(f"{tab}|dist|{ind}|0|{col}"); out.append((p_[j], [i], "value"))
            T.row([TXT(il), TXT(lab)] + out, f"{ind}.dist{j}")
    if narrow:
        T.panel("Panel B. Narrow window: middle year of the inferred period only, main estimate", ["Measure", "Pharmaceutical", "Medical device"])
        for lab, a, b in (("Proportion undeclared before deduplication [95% CI] (undeclared/evaluable)", "L789", "L790"),
                          ("Proportion undeclared after deduplication [95% CI] (undeclared/evaluable)", "L791", "L792"),
                          ("Proportion of authors with at least one undeclared unit [95% CI] (authors/authors with an evaluable unit)", "L793", "L794")):
            va, ia = lval(a); vb, ib = lval(b)
            T.row([TXT(lab), (est_ci_kn(va), [ia], "value"), (est_ci_kn(vb), [ib], "value")], f"narrow.{a}")
    T.note("✱ A unit is an author × company × year × payment category (lecture fees, manuscript fees) whose payment reached the audit threshold within the guideline's declaration period; an evaluable unit was judged declared or undeclared. Authors are counted once across guidelines. Members of the external evaluation committee of one society are counted within the disclosure scope. Proportions are given with Wilson 95% confidence intervals (CIs); no statistical tests were done.")
    T.note("† Company-name corrections (Table S2) applied; units whose payment category was not among the guideline's disclosed items (item rule) and units below the guideline's declaration threshold (threshold rule) are not counted. The threshold was taken from the guideline, otherwise from the issuing society's rules; where two society documents disagreed, the lower amount was used (Table S8).")
    moved = [k.split("|", 1)[1] for k in KY.key if k.startswith("moved|") and k not in ("moved|n_diff", "moved|total16") and int(parts(k)[0][1]) > 0]
    assert set(moved) <= {k.split("|")[1] for k in KY.key if k.startswith("B7|") and k.endswith("|flag")}, moved
    T.note("‡ Corrections and the item rule applied, and the guidelines flagged by extraction diagnostics (Table S4) removed. Every unit moved by the threshold rule lies in a flagged guideline, so this column also equals the main estimate without the flagged guidelines.")
    T.note("§ Judgments of the frozen pipeline before company-name corrections, with the item rule applied.")
    T.note("¶ Units deduplicated to author × company × year across payment categories and guidelines.")
    T.note("‖ Authors with at least one evaluable unit, by their number of undeclared units after deduplication.")
    return T.write()


results_table("table3_main_results", "Table 3. Undeclared industry payments among the authors of the main analysis set: 48 guidelines with a stated declaration period, "
              "25 medical societies in Japan, title years 2022 to 2025✱", "B2", [SCOPE_ID, MAIN_ID])

# ================================================================ Table S1 (forms) and S2 (errata)
TS1 = Table("tableS1_public_forms", "Table S1. The seven public forms of authors' declarations✱")
TS1.panel("", ["Public form", "Definition"])
for f_, d in zip(FORM_EN, FORM_DEF): TS1.row([TXT(f_), TXT(d)], f_)
TS1.note("✱ Forms were assigned at the guideline census from the documents published by the issuing societies; the same forms are counted in Table 1.")
TS1.write()

ERR_EN = {  # declared form, company in the payment data, reason (English text written from the ledger's basis column)
    "日本メドトロニック": ("Medtronic Japan", "Medtronic Japan group", "The company node merges three Medtronic entities, including this name."),
    "アボット バスキュラー ジャパン": ("Abbott Vascular Japan", "Abbott Medical Japan", "In the payment years, the vascular business was disclosed by Abbott Medical Japan, not by Abbott Japan."),
    "カネカ": ("Kaneka", "Kaneka Medix", "The declaration named the parent company; payments were disclosed by its medical device sales subsidiary."),
    "アステラス・アムジェン・バイオファーマ": ("Astellas Amgen BioPharma", "Amgen", "Predecessor of Amgen in Japan, a joint venture with Astellas, renamed in April 2020."),
    "サノフィアベンティス": ("Sanofi-Aventis", "Sanofi", "Former company name of Sanofi."),
    "メルク": ("Merck", "Merck Biopharma", "The US company Merck declares as MSD in Japan, not as Merck."),
    "オリンパスメディカルシステムズ": ("Olympus Medical Systems", "Olympus", "Subsidiary within the Olympus group; no other company of this name in the company list."),
    "オリンパスマーケティング": ("Olympus Marketing", "Olympus", "Subsidiary within the Olympus group; no other company of this name in the company list."),
    "協和キリンファーマ": ("Kyowa Kirin Pharma", "Kyowa Kirin", "Near-identical name of Kyowa Kirin; no other company of this name in the company list."),
}
TS2 = Table("tableS2_errata", "Table S2. Company names in declarations that were assigned to a company in the payment data outside the frozen pipeline✱")
TS2.panel("", ["Name as declared (original)", "Name as declared (English)", "Company in the payment data", "Reason"])
for k in [k for k in KY.key if re.match(r"^errata\|\d+$", k)]:
    v, i = val(k); w = re.search(r"「(.*)」", LG.loc[i, "说明"]).group(1); e = ERR_EN[w]
    TS2.row([TXT(w), TXT(e[0]), (e[1], [i], "value"), (e[2], [i], "value")], k)
TS2.note("✱ The frozen pipeline left these declared names unmatched or matched them to a different company. The corrections were fixed before the main estimate and apply to all guidelines (Supplementary Methods 4).")
TS2.write()

# ================================================================ Table S3: the two channels
IND3 = (("all", "All companies"), ("pharma", "Pharmaceutical-dominant companies"), ("device", "Device-dominant companies"))
SETS3 = (("主分析集", "Total, main analysis set"), ("期间推定层", "Total, period-inferred layer"), ("全部", "Total, all analyzed guidelines"))
socs4 = [k.split("|")[2] for k in KY.key if k.startswith("ch|soc|") and k.endswith("|all")]
frame4 = [s for s in FRAME if s in socs4]
TS3 = Table("tableS3_two_channels", "Table S3. The two channels: companies that paid authors lecture fees above the audit threshold (set A) and companies that paid "
            "the issuing societies donations or co-sponsorship fees (set B), 73 guidelines from 25 medical societies in Japan, title years 2022 to 2025✱", [SCOPE_ID, AN_ID])
def ch_cells(q, i, m=None):              # q: 0 n, 1 A, 2 AB, 3 AB/A, 4 B, 5 AB/B, 6 total, 7 fromA, 8 pooled share, 9 median
    mm = m if m is not None else (med(q[9]), [i])
    return [(q[1], [i], "value"), (est_ci_kn(q[3]), [i], "value"), (q[6], [i], "value"), (mm[0], mm[1], "value")]
CHH = ["Guideline-company pairs in set A†", "Share of set A also in set B [95% CI] (pairs)", "Payments to the issuing societies (10,000 JPY)‡", "Share of society payments from set A, median (IQR)§"]
for pj, (ind, il) in enumerate(IND3):
    TS3.panel(f"Panel {'ABC'[pj]}. {il}" + ("¶" if ind != "all" else ""), ["Society or total"] + (["Guidelines (main / inferred)"] if ind == "all" else []) + CHH)
    for sid in frame4:
        q, i = fparts(f"ch|soc|{sid}|{ind}"); q0, i0 = fparts(f"ch|soc|{sid}|all")
        TS3.row([TXT(SOC_EN[sid])] + ([(gl_n(q0[0]), [i0], "value")] if ind == "all" else []) + ch_cells(q, i), f"{ind}.{sid}")
    qn, inn = fparts("ch|nonframe|count"); q, i = fparts(f"ch|nonframe|{ind}")
    TS3.row([(f"Co-issuing societies outside the sample ({qn[0]} societies), total‖", [inn], "label")] + ([(q[0], [i], "value")] if ind == "all" else []) + ch_cells(q, i), f"{ind}.nonframe")
    for s_, lab in SETS3:
        q, i = fparts(f"ch|pool|{s_}|{ind}"); m, mi = fparts(f"ch|med|{s_}|{ind}")
        TS3.row([TXT(lab)] + ([(q[0], [i], "value")] if ind == "all" else []) + ch_cells(q, i, (med(m[2]), [mi])), f"{ind}.pool.{s_}")
TS3.panel("Panel D. Sensitivity analyses, all analyzed guidelines", ["Analysis", "Companies", "Guideline-company pairs in set A", "Share of set A also in set B [95% CI] (pairs)",
                                                                     "Guideline-company pairs in set B", "Share of set B also in set A [95% CI] (pairs)", "Payments to the issuing societies (10,000 JPY)", "Share of society payments from set A, median (IQR)"])
for mode, lab in (("any", "Set A: any personal payment, no threshold"), ("win2", "Window: the three years before the title year"), ("allcat", "Set B: all categories of institutional payments")):
    for ind, il in IND3:
        q, i = fparts(f"ch|sens|{mode}|全部|{ind}")
        TS3.row([TXT(lab), TXT(il), (q[1], [i], "value"), (est_ci_kn(q[3]), [i], "value"), (q[4], [i], "value"), (est_ci_kn(q[5]), [i], "value"), (q[6], [i], "value"), (med(q[9]), [i], "value")], f"sens.{mode}.{ind}")
TS3.note("✱ Set A: companies that, within the guideline's audit window, paid an author within the disclosure scope lecture fees reaching the guideline's audit threshold in at least one year. Set B: companies that, within the same window, paid the issuing societies (all co-issuers together, including their branches and the scientific meetings they host) donations or co-sponsorship fees. Descriptive only; no statistical tests.")
T_sym = "† Pairs are summed over guidelines; a company counts once per guideline. Shares of pairs carry Wilson 95% confidence intervals (CIs)."
TS3.note(T_sym)
TS3.note("‡ Donations and co-sponsorship fees received by the issuing societies within the audit windows, summed over guidelines (overlapping windows of one society's guidelines are counted for each guideline), in nominal Japanese yen (JPY).")
TS3.note("§ Amount share per guideline, summarized as median and interquartile range (IQR, first to third quartile) across guidelines; no CI because the share is not a count.")
TS3.note("¶ Companies are grouped by their main industry; merged pharmaceutical and device entities of the same group count as one company.")
TS3.note("‖ Guidelines with at least one co-issuing society outside the 25 sampled societies, each guideline counted once. A co-issued guideline appears under every sampled issuing society, so society rows sum to more than the totals.")
TS3.notes[-1] = (TS3.notes[-1][0], {SCOPE_ID})
TS3.write()

# ================================================================ Table S4: every guideline
G7 = [k.split("|")[1] for k in KY.key if k.startswith("B7|") and k.endswith("|year")]
assert set(G7) == set(GL), set(G7) ^ set(GL)
MAIN7 = [k for k in G7 if AS.loc[k, "analysis_set"] == "主分析集"]; INF7 = [k for k in G7 if AS.loc[k, "analysis_set"] == "期间推定层"]
def gl_sorted(keys):
    return sorted(keys, key=lambda k: (FRAME.index(GSOC[k]), -int(val(f"B7|{k}|year")[0]), GL[k][0]))
FLAGSYM = {"F1": "§", "F3": "¶"}
TS4 = Table("tableS4_guidelines", "Table S4. Undeclared payments by guideline: 73 guidelines from 25 medical societies in Japan, title years 2022 to 2025✱", [SCOPE_ID, AN_ID])
H4 = ["Guideline (title year)", "Lead society (code in Figs. 2 and S1)†", "Author seats", "Pharmaceutical: undeclared/evaluable", "Pharmaceutical: proportion [95% CI]",
      "Device: undeclared/evaluable", "Device: proportion [95% CI]", "Threshold, lecture / manuscript fees (10,000 JPY)", "Threshold source‡"]
for lab_, keys in (("Panel A. Main analysis set (declaration period stated)", MAIN7), ("Panel B. Period-inferred layer", INF7)):
    TS4.panel(lab_, H4)
    for k in gl_sorted(keys):
        y, yi = val(f"B7|{k}|year"); r_, ri = val(f"B7|{k}|roster"); ph, phi = parts(f"B7|{k}|ph"); dv, dvi = parts(f"B7|{k}|dv"); th, thi = val(f"B7|{k}|thr")
        fl = val(f"B7|{k}|flag") if f"B7|{k}|flag" in K2 else None
        amt, src = thr_cell(th)
        lab = f"{GL[k][1]} ({y})" + (FLAGSYM[fl[0]] if fl else "")
        TS4.row([(lab, [yi] + ([fl[1]] if fl else []), "label"), TXT(f"{SOC_EN[GSOC[k]]} ({CODE[GSOC[k]]})"), (r_, [ri], "value"),
                 (f"{ph[1]}/{ph[0]}" if ph[0] != "0" else "—", [phi], "value"), (est_ci(ph[2]), [phi], "value"),
                 (f"{dv[1]}/{dv[0]}" if dv[0] != "0" else "—", [dvi], "value"), (est_ci(dv[2]), [dvi], "value"), (amt, [thi], "value"), (src, [thi], "value")], k)
TS4.note("✱ Main estimate (company-name corrections, item rule and threshold rule applied), deduplicated to author × company × year within each guideline. Author seats are rows of the guideline's committee roster. — means no evaluable unit. Wilson 95% confidence intervals (CIs). Abbreviations: ECMO, extracorporeal membrane oxygenation; HTLV-1, human T-lymphotropic virus type 1; JPY, Japanese yen.")
TS4.note("† The first issuing society; guidelines co-issued with the Japanese Circulation Society are grouped under it. Letters are the codes used in Fig. 2 and Fig. S1.")
TS4.note("‡ Guideline: threshold stated in the guideline. Society rule: not stated in the guideline, taken from the issuing society's conflict-of-interest rules. Unclear: the society's documents disagreed, and the lower amount was used.")
TS4.note("§ Flagged by extraction diagnostics: fewer than six in ten declared company names could be matched to a company.")
TS4.note("¶ Flagged by extraction diagnostics: at least ten authors within the disclosure scope, but fewer than one in ten with any extracted declaration.")
TS4.write()

results_table("tableS5_inferred_layer", "Table S5. Undeclared industry payments among the authors of the period-inferred layer: 25 guidelines whose declaration period "
              "was inferred from the title year, 25 medical societies in Japan, title years 2022 to 2025✱", "B3", [SCOPE_ID, INF_ID], narrow=True)

# ================================================================ Table S6: every sampled society
TS6 = Table("tableS6_societies", "Table S6. Guidelines, public forms, own statements and audit results by society: the 25 sampled medical societies in Japan, title years 2022 to 2025✱", [SCOPE_ID])
TS6.panel("Panel A. Public form of authors' declarations, all guidelines", ["Society", "Code†", "Guidelines"] + FORM_EN)
for sid in FRAME:
    v, i = val(f"B1|{sid}|n")
    TS6.row([TXT(SOC_EN[sid]), TXT(CODE[sid]), (v, [i], "value")] + [(val(f"B1|{sid}|form{j}")[0], [val(f"B1|{sid}|form{j}")[1]], "value") for j in range(7)], f"A.{sid}")
TS6.panel("Panel B. Statements in the audited guidelines (model judgments)‡", ["Society", "Audited guidelines", "Source of development funding stated", "Source was the societies' own funds",
                                                                              "Society-level funding or conflict mentioned", "Names of paying companies listed"])
for sid in FRAME:
    q, i = fparts(f"fs|soc|{sid}")
    TS6.row([TXT(SOC_EN[sid])] + [(x, [i], "value") for x in q], f"B.{sid}")
socs = [k.split("|")[1] for k in KY.key if k.startswith("soc|") and k.endswith("|n")]
TS6.panel("Panel C. Audit, main analysis set, main estimate§", ["Society", "Guidelines", "Author seats", "Authors", "Threshold source (guidelines)",
                                                              "Pharmaceutical: proportion undeclared [95% CI] (units)", "Device: proportion undeclared [95% CI] (units)",
                                                              "Pharmaceutical: authors with at least one undeclared unit [95% CI] (authors)", "Device: authors with at least one undeclared unit [95% CI] (authors)"])
for sid in [s for s in FRAME if s in socs]:
    g = lambda x: val(f"soc|{sid}|{x}")
    TS6.row([TXT(SOC_EN[sid]), (g("n")[0], [g("n")[1]], "value"), (g("times")[0], [g("times")[1]], "value"), (g("persons")[0], [g("persons")[1]], "value"),
             (thr_src_en(g("src")[0]), [g("src")[1]], "value")] + [(est_ci_kn(g(x)[0]), [g(x)[1]], "value") for x in ("dd2|pharma", "dd2|device", "pp2|pharma", "pp2|device")], f"C.{sid}")
TS6.note("✱ A guideline co-issued by several societies is counted under each of them, so society rows sum to more than the totals in Table 1 and Table 3. Societies are listed in the order of the sampling list.")
TS6.note("† Code used for the lead society in Fig. 2, Fig. S1 and Table S4.")
TS6.note("‡ Audited guidelines of the main analysis set and the period-inferred layer; same judgments as Table 1, panel B (yes counts).")
TS6.note("§ Guidelines of the main analysis set only. Co-issuing societies outside the sample are not listed. Proportions are deduplicated to author × company × year; Wilson 95% confidence intervals (CIs). — means no evaluable unit.")
TS6.write()

# ================================================================ Table S7: overlap
YRS5 = [2019, 2020, 2021, 2022, 2023]; DAG5 = {2022: "†", 2023: "‡"}
TS7 = Table("tableS7_overlap", "Table S7. Persons who received personal payments from both pharmaceutical-dominant and device-dominant companies in the same year, Japan, 2019 to 2023✱",
            [val("ov|main|2019")[1], val("ov|main|2023")[1]])
hd = [f"{y}{DAG5.get(y, '')}" for y in YRS5]
TS7.panel("", ["Group"] + hd, {h: [val(f"ov|main|{y}")[1]] for h, y in zip(hd, YRS5)})
for g, lab in (("main", "Authors of the main analysis set"), ("inf", "Authors of the period-inferred layer"), ("all", "Authors of all analyzed guidelines"),
               ("everyone", "All persons who received personal payments that year"), ("board", "Board members of basic-specialty societies§")):
    cells = [(est_ci_kn(val(f"ov|{g}|{y}")[0]), [val(f"ov|{g}|{y}")[1]], "value") for y in YRS5]
    TS7.row([TXT(lab)] + cells, g)
TS7.note("✱ Proportion [Wilson 95% confidence interval] (persons with payments from both industries / persons with any personal payment that year). Authors are those within the disclosure scope, each person counted once across guidelines. Companies of the same group count as one company, classified by main industry.")
TS7.note("† Pharmaceutical payment data for this year carry no person identifier; persons were linked by rule.")
TS7.note("‡ Device payment data for this year carry no person identifier; persons were linked by rule.")
TS7.note("§ Board members in 2021 of the basic-specialty societies.", [val("ov|board|2021")[1]])
TS7.write()

# ================================================================ Table S8: dermatology thresholds
SKs = [k.split("|")[2] for k in KY.key if k.startswith("sens|per|")]
alt, alti = val("sens|alt"); al, am = [x.strip() for x in alt.split(" / ")]
TS8 = Table("tableS8_derm_sensitivity", f"Table S8. Sensitivity analysis: thresholds of the Japanese Dermatological Association guidelines set at the amount in the society's bylaw "
            f"({al} / {am} × 10,000 JPY for lecture / manuscript fees)✱", [alti])
TS8.panel("", ["Set", "Measure", "Main estimate†", "Sensitivity‡", "Units moved by the sensitivity analysis"])
mt, mti = parts("sens|moved_total")
TS8.row([TXT("Both sets"), TXT("Units below the guideline's threshold"), (mt[2], [mti], "value"), (mt[0], [mti], "value"), TXT("")], "moved_units")
TS8.row([TXT("Both sets"), TXT("Guidelines with such units"), (mt[3], [mti], "value"), (mt[1], [mti], "value"), TXT("")], "moved_gl")
for lab, setname in (("主分析集", "Main analysis set"), ("期间推定层", "Period-inferred layer")):
    for kind, ind, rl in (("dedup", "pharma", "Pharmaceutical: proportion undeclared"), ("dedup", "device", "Device: proportion undeclared"),
                          ("person", "pharma", "Pharmaceutical: authors with at least one undeclared unit"), ("person", "device", "Device: authors with at least one undeclared unit")):
        v, i = val(f"sens|{lab}|{kind}|{ind}"); a, b = v.split("；")
        TS8.row([TXT(setname), TXT(rl), (est_ci_kn(a), [i], "value"), (est_ci_kn(b), [i], "value"), TXT("")], f"{lab}.{kind}.{ind}")
for k in gl_sorted(SKs):
    v, i = val(f"sens|per|{k}"); q = v.split("；"); y, yi = val(f"B7|{k}|year")
    TS8.row([(f"{GL[k][1]} ({y})", [yi], "label"), TXT("Pharmaceutical: proportion undeclared"), (est_ci_kn(q[0]), [i], "value"), (est_ci_kn(q[1]), [i], "value"), (q[4], [i], "value")], f"per.{k}")
TS8.note("✱ The society's bylaw and the declaration form used by its guideline committees state different thresholds. The main estimate uses the lower amount and marks these guidelines as having an unclear threshold. — means no evaluable unit. Proportions are deduplicated to author × company × year (within each guideline in the per-guideline rows) with Wilson 95% confidence intervals (CIs); — in the last column means not applicable. No device unit was evaluable in these guidelines. JPY, Japanese yen.")
TS8.note("† Main estimate: company-name corrections, item rule and threshold rule applied (Table 3).")
TS8.note("‡ Only the thresholds of these guidelines were changed to the bylaw amount; the threshold rule was applied again outside the frozen pipeline, without re-running extraction.")
for p in TS8.panels:
    p["rows"] = [(k, [c if c[0] != "" else ("—", [], "label") for c in cells]) for k, cells in p["rows"]]
TS8.write()

# ================================================================ figures
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.transforms import blended_transform_factory
from matplotlib.patches import Rectangle, FancyBboxPatch
sys.path.insert(0, str(SKILL))
from audit_panel_alignment import require_matplotlib_panel_alignment
FONT = 8
plt.rcParams.update({"font.family": "Times New Roman", "font.size": FONT, "pdf.fonttype": 42, "svg.fonttype": "none", "axes.unicode_minus": False,
                     "axes.linewidth": 0.6, "xtick.major.width": 0.6, "xtick.major.size": 2.5, "axes.spines.right": False, "axes.spines.top": False})
SMALL_N = {"ten": 10}["ten"]                                          # cut-off for open points (fewer than ten evaluable units), written once as a word
FIGS = {}; LABEL_RIGHT = {}


def forest(name, keys):
    rows = []
    for k in keys:
        ph, phi = parts(f"B7|{k}|ph"); dv, dvi = parts(f"B7|{k}|dv")
        if ph[0] == "0" and dv[0] == "0": continue
        y, yi = val(f"B7|{k}|year"); r_, ri = val(f"B7|{k}|roster")
        rows.append(dict(key=k, soc=GSOC[k], year=int(y), label=f"{GL[k][0]} ({y})", seats=r_, ph=ph, dv=dv, phi=phi, dvi=dvi, yi=yi, ri=ri))
    R = sorted(rows, key=lambda r: (FRAME.index(r["soc"]), -r["year"], r["label"]))
    N = len(R); rp = 0.158; top = 0.60; bottom = 0.40; W = 7.40; H = top + N * rp + bottom
    X = dict(code=0.02, gl=0.18, a0=2.32, a1=2.96, b0=3.06, b1=3.70, seats=4.01, pu=4.30, pk=4.83, pc=4.88, du=5.96, dk=6.49, dc=6.54)
    fig = plt.figure(figsize=(W, H))
    axa = fig.add_axes([X["a0"] / W, bottom / H, (X["a1"] - X["a0"]) / W, N * rp / H])
    axb = fig.add_axes([X["b0"] / W, bottom / H, (X["b1"] - X["b0"]) / W, N * rp / H])
    for ax in (axa, axb):
        ax.set_ylim(N - 0.5, -0.5); ax.set_xlim(0, 1); ax.set_yticks([]); ax.patch.set_alpha(0)
        ax.set_xticks([0, 0.5, 1]); ax.set_xticklabels(["0", "0.5", "1"])
        ax.spines["left"].set_visible(False)
        for xg in (0.5,): ax.axvline(xg, color="0.6", lw=0.4, ls=(0, (2, 2)), zorder=1)
    tr = blended_transform_factory(fig.transFigure, axa.transData); fx = lambda inch: inch / W
    fig.text(fx((X["a0"] + X["b1"]) / 2), (bottom - 0.29) / H, "Proportion undeclared", ha="center", va="center", fontsize=FONT)
    # society bands
    groups = []
    for j, r in enumerate(R):
        if not groups or groups[-1][0] != r["soc"]: groups.append([r["soc"], j, j])
        else: groups[-1][2] = j
    for g_i, (soc, j0, j1) in enumerate(groups):
        if g_i % 2 == 0:
            fig.add_artist(Rectangle((0.0, j0 - 0.5), 1.0, j1 - j0 + 1, transform=tr, facecolor="0.90", edgecolor="none", zorder=-5))
        fig.text(fx(X["code"]), (j0 + j1) / 2, CODE[soc], transform=tr, ha="left", va="center", fontsize=FONT)
    hy1, hy2, hy3 = -2.80, -1.05, -1.75
    t = lambda x_, y_, s, ha="left", **kw: fig.text(fx(x_), y_, s, transform=tr, ha=ha, va="center", **({"fontsize": FONT} | kw))
    t(X["code"], hy2, "Society, guideline (title year)")
    for ax, lab, ttl in ((axa, "a", "Pharmaceutical"), (axb, "b", "Medical device")):
        x0 = X["a0"] if ax is axa else X["b0"]
        t(x0, hy1, lab, fontweight="bold", fontsize=FONT + 1); t(x0 + 0.32, hy3, ttl, "center")
    t(X["seats"], hy2, "Seats", "right")
    for g0, g1, ttl in ((X["pu"] - 0.26, X["pc"] + 0.78, "Pharmaceutical"), (X["du"] - 0.26, X["dc"] + 0.78, "Medical device")):
        t((g0 + g1) / 2, hy1, ttl, "center")
        fig.add_artist(plt.Line2D([fx(g0), fx(g1)], [hy1 + 0.45, hy1 + 0.45], transform=tr, color="black", lw=0.4))
    for xu, xk, xc in ((X["pu"], X["pk"], X["pc"]), (X["du"], X["dk"], X["dc"])):
        t(xu, hy2, "Units", "right"); t(xk, hy2, "Undeclared", "right"); t(xc, hy3, "Proportion"); t(xc, hy2, "[95% CI]")
    fig.add_artist(plt.Line2D([0, 1], [-0.5, -0.5], transform=tr, color="black", lw=0.5))
    csv = []
    for j, r in enumerate(R):
        t(X["gl"], j, r["label"]); t(X["seats"], j, r["seats"], "right")
        csv += [dict(table=name, rkey=r["key"], ckey="label", text=r["label"], ledger_ids=r["yi"], role="label"),
                dict(table=name, rkey=r["key"], ckey="code", text=CODE[r["soc"]], ledger_ids="", role="label"),
                dict(table=name, rkey=r["key"], ckey="seats", text=r["seats"], ledger_ids=r["ri"], role="value")]
        for ax, p_, pi, xu, xk, xc, tag in ((axa, r["ph"], r["phi"], X["pu"], X["pk"], X["pc"], "ph"), (axb, r["dv"], r["dvi"], X["du"], X["dk"], X["dc"], "dv")):
            d = sh(p_[2])
            if d is None:
                t(xu, j, "—", "right"); t(xk, j, "—", "right"); t(xc, j, "—")
                csv += [dict(table=name, rkey=r["key"], ckey=f"{tag}_ci", text="—", ledger_ids=pi, role="value")]
                continue
            e, lo, hi = float(d["e"]), float(d["lo"]), float(d["hi"])
            ax.plot([lo, hi], [j, j], color="black", lw=0.8, solid_capstyle="butt", zorder=2, clip_on=False)
            ax.plot([e], [j], marker="o", ms=3.4, mec="black", mew=0.7, mfc="black" if int(d["n"].replace(",", "")) >= SMALL_N else "white", ls="none", zorder=3, clip_on=False)
            ci_txt = f"{d['e']} {d['ci']}"
            t(xu, j, d["n"], "right"); t(xk, j, d["k"], "right"); t(xc, j, ci_txt)
            csv += [dict(table=name, rkey=r["key"], ckey=f"{tag}_n", text=d["n"], ledger_ids=pi, role="value"),
                    dict(table=name, rkey=r["key"], ckey=f"{tag}_k", text=d["k"], ledger_ids=pi, role="value"),
                    dict(table=name, rkey=r["key"], ckey=f"{tag}_ci", text=ci_txt, ledger_ids=pi, role="value")]
    fig.canvas.draw(); rend = fig.canvas.get_renderer()
    right = max(tx.get_window_extent(rend).x1 for tx in fig.texts if tx.get_position()[0] == fx(X["gl"])) / fig.dpi
    assert right < X["a0"] - 0.03, ("label overlaps forest", right)
    LABEL_RIGHT[name] = round(right, 2)
    require_matplotlib_panel_alignment(fig, json_out=str(O/f"{name}.alignment.json"), overlay_svg=str(O/f"{name}.alignment.svg"),
                                       tolerance_pt=1.5, gutter_tolerance_pt=1.5, strict=True, panel_ids=["a", "b"], row_groups=[{"id": "forests", "panels": ["a", "b"]}])
    fig.savefig(O/f"{name}.pdf"); fig.savefig(O/f"{name}.png", dpi=600); plt.close(fig)
    C = pd.DataFrame(csv); C.to_csv(O/f"{name}.csv", index=False, encoding="utf-8-sig"); CELLS.append(C)
    FIGS[name] = dict(rows=N, groups=[(CODE[g[0]], g[2] - g[1] + 1) for g in groups], open_ph=sum(1 for r in R if sh(r["ph"][2]) and int(sh(r["ph"][2])["n"].replace(",", "")) < SMALL_N),
                      open_dv=sum(1 for r in R if sh(r["dv"][2]) and int(sh(r["dv"][2])["n"].replace(",", "")) < SMALL_N),
                      no_ph=sum(1 for r in R if r["ph"][0] == "0"), no_dv=sum(1 for r in R if r["dv"][0] == "0"), codes=sorted({CODE[r["soc"]] for r in R}))
    return R


forest("figure2_forest_main", MAIN7)
forest("figureS1_forest_inferred", INF7)


# ---------------------------------------------------------------- Fig. 1: flow
def flow():
    name = "figure1_flow"; csv = []
    W, H = 7.30, 6.05
    fig = plt.figure(figsize=(W, H)); fx = lambda x: x / W; fy = lambda y: 1 - y / H
    def box(x, y, w, lines, ids, key, fs=FONT + 1):
        h = 0.20 + 0.165 * len(lines)
        fig.add_artist(FancyBboxPatch((fx(x), fy(y + h)), w / W, h / H, boxstyle="round,pad=0,rounding_size=0.008", transform=fig.transFigure,
                                          facecolor="white", edgecolor="black", lw=0.7))
        for j, s in enumerate(lines):
            fig.text(fx(x + 0.09), fy(y + 0.17 + 0.165 * j), s, ha="left", va="center", fontsize=fs)
            lid = ids[j] if isinstance(ids, list) else [ids]
            csv.append(dict(table=name, rkey=key, ckey=str(j), text=s, ledger_ids="|".join(lid), role="label" if (SCOPE_ID in lid or not re.search(r"\d", s)) else "value"))
        return y + h
    def arrow(x0, y0, x1, y1):
        fig.add_artist(matplotlib.patches.FancyArrowPatch((fx(x0), fy(y0)), (fx(x1), fy(y1)), transform=fig.transFigure, arrowstyle="-|>", mutation_scale=7, lw=0.7, color="black"))
    n, ni = val("B1|total|n"); scope = re.search(r"(\d+) 个学会、标题年份 (\d{4})–(\d{4}) 年", LG.loc[SCOPE_ID, "说明"])
    b, bi = parts("B1b|total"); fm = [val(f"B1|total|form{j}") for j in range(7)]
    no_item, nii = val("sets|no_item"); mset, msi = val("sets|main"); iset, isi = val("sets|inferred")
    cx, bw = 0.55, 3.30
    y = box(cx, 0.10, bw, [f"Guidelines with title years {scope[2]}–{scope[3]}", f"issued by the {scope[1]} sampled medical societies", f"n = {n}"],
            [[SCOPE_ID], [SCOPE_ID], [ni]], "census")
    ex = [f"Not audited, by public form of authors' declarations:"] + [f"   {FORM_EN[j]}: {fm[j][0]}" for j in (1, 3, 4, 5, 6)]
    yx = box(4.20, 0.62, 3.00, ex, [[]] + [[fm[j][1]] for j in (1, 3, 4, 5, 6)], "excluded1", fs=FONT)
    arrow(cx + bw / 2, y, cx + bw / 2, 1.85); arrow(cx + bw / 2, 1.18, 4.20, 1.18)
    y = box(cx, 1.85, bw, ["Guidelines audited by the frozen pipeline", "(individual and itemized declarations)", f"n = {b[1]}"], [[], [], [bi]], "audited")
    box(4.20, 2.38, 3.00, ["Excluded: no lecture or manuscript fees", f"among the disclosed items: {no_item}"], [[], [nii]], "excluded2", fs=FONT)
    arrow(cx + bw / 2, y, cx + bw / 2, 3.25); arrow(cx + bw / 2, 2.72, 4.20, 2.72)
    y = box(cx, 3.25, bw, ["Analysis set", f"n = {b[2]}"], [[], [bi]], "analysis")
    for xs, ys in (([cx + bw / 2] * 2, [y, 3.92]), ([1.80, 5.50], [3.92, 3.92])):
        fig.add_artist(plt.Line2D([fx(v) for v in xs], [fy(v) for v in ys], transform=fig.transFigure, color="black", lw=0.7))
    arrow(1.80, 3.92, 1.80, 4.05); arrow(5.50, 3.92, 5.50, 4.05)
    def detail(lab):
        p_, i = parts(f"B8|{lab}")
        return [f"Guidelines: {p_[0]}", f"Author seats: {p_[1]}; authors: {p_[2]}", f"Seats within the disclosure scope: {p_[3]}", f"Seats linked to payment data: {p_[4]}",
                f"Units, pharmaceutical: {p_[5]}; device: {p_[6]}", "Evaluable units before deduplication,", f"   pharmaceutical: {p_[7]}; device: {p_[8]}",
                "Evaluable units after deduplication,", f"   pharmaceutical: {p_[9]}; device: {p_[10]}"], i
    dm, dmi = detail("主分析集"); di, dii = detail("期间推定层")
    box(0.10, 4.05, 3.40, ["Main analysis set (declaration period stated)"] + dm, [[]] + [[dmi]] * len(dm), "main", fs=FONT)
    box(3.80, 4.05, 3.40, ["Period-inferred layer (period inferred from title year)"] + di, [[]] + [[dii]] * len(di), "inferred", fs=FONT)
    fig.savefig(O/f"{name}.pdf"); fig.savefig(O/f"{name}.png", dpi=600); plt.close(fig)
    C = pd.DataFrame(csv); C.to_csv(O/f"{name}.csv", index=False, encoding="utf-8-sig"); CELLS.append(C)
    FIGS[name] = dict(boxes=len(set(C.rkey)))
    return C
FLOW = flow()

# ================================================================ self-check
NUM = re.compile(r"\d[\d,]*(?:\.\d+)?")
XREF = re.compile(r"(Supplementary Methods \d+|Figs\. \d+ and S\d+|Tables? S?\d+|Figs?\. S?\d+|HTLV-1|virus type 1|panel [A-D]|10,000 JPY|× 10,000 JPY|95% CI|95% confidence interval[s]?|\{ref:[^}]+\})")
def nums(s):
    return [x.replace(",", "") for x in NUM.findall(XREF.sub(" ", str(s)))]
ALL = pd.concat(CELLS, ignore_index=True); bad = []; n_val = n_lab = ok_val = ok_lab = 0
for r in ALL.itertuples():
    txt = re.sub(r"^(Table S?\d+|Fig\. S?\d+)\.\s*", "", r.text) if r.rkey == "（标题）" else r.text
    got = nums(txt)
    if not got: continue
    ids = [x for x in str(r.ledger_ids).split("|") if x]
    pool = Counter()
    for i in ids:
        pool += Counter(nums(LG.loc[i, "数值"]))
        if r.role == "label": pool += Counter(nums(LG.loc[i, "说明"]))
    ok = bool(ids) and not (Counter(got) - pool)
    if r.role == "value": n_val += 1; ok_val += ok
    else: n_lab += 1; ok_lab += ok
    if not ok: bad.append(dict(table=r.table, row=r.rkey, column=r.ckey, text=r.text, ledger_ids=r.ledger_ids))
# footnote symbols: one-to-one between notes and the table body
SYMRE = re.compile(r"([✱†‡§¶‖]+)$")
sym_rows = []
for nm, T in SPECS.items():
    in_notes = [re.match(r"^([✱†‡§¶‖]+) ", n).group(1) for n, _ in T.notes]
    body = [T.title] + [p["label"] for p in T.panels] + [h for p in T.panels for h in p["header"]] + [c[0] for p in T.panels for _, cells in p["rows"] for c in cells]
    in_body = [m.group(1) for s in body for m in [SYMRE.search(s.strip())] if m]
    ok = set(in_notes) == set(in_body) and len(in_notes) == len(set(in_notes)) and T.title.strip().endswith(in_notes[0]) if in_notes else not in_body
    sym_rows.append((nm, len(in_notes), len(set(in_body)), ok))
# Fig. 1 against Tables 3 and S5
def cell(tab, rkey, col):
    d = ALL[(ALL.table == tab) & (ALL.rkey == rkey) & (ALL.ckey == col)]; return d.text.iloc[0]
cons = []
for tab, lab in (("table3_main_results", "主分析集"), ("tableS5_inferred_layer", "期间推定层")):
    p_, _ = parts(f"B8|{lab}")
    for rk, j in (("pharma.raw_n", 7), ("device.raw_n", 8), ("pharma.dd_n", 9), ("device.dd_n", 10)):
        tv = cell(tab, rk, "Main estimate†"); cons.append((tab, rk, p_[j], tv, p_[j] == tv))
    cons.append((tab, "guidelines", p_[0], val("sets|main" if lab == "主分析集" else "sets|inferred")[0], p_[0] == val("sets|main" if lab == "主分析集" else "sets|inferred")[0]))
# flow arithmetic: census minus the five not-audited forms equals audited; audited minus the no-item guideline equals the analysis set = main + inferred
b, _ = parts("B1b|total"); fm = [int(val(f"B1|total|form{j}")[0]) for j in range(7)]
arith = [("census − not audited = audited", int(val("B1|total|n")[0]) - sum(fm[j] for j in (1, 3, 4, 5, 6)), int(b[1])),
         ("audited − no-item = analysis set", int(b[1]) - int(val("sets|no_item")[0]), int(b[2])),
         ("main + inferred = analysis set", int(val("sets|main")[0]) + int(val("sets|inferred")[0]), int(b[2]))]
import fitz
from PIL import Image
FS = {}
for nm in ("figure1_flow", "figure2_forest_main", "figureS1_forest_inferred"):
    doc = fitz.open(O/f"{nm}.pdf"); sz = [s["size"] for p in doc for b_ in p.get_text("dict")["blocks"] for l in b_.get("lines", []) for s in l["spans"] if s["text"].strip()]
    fonts = sorted({s["font"] for p in doc for b_ in p.get_text("dict")["blocks"] for l in b_.get("lines", []) for s in l["spans"] if s["text"].strip()})
    pw, ph = doc[0].rect.width / 72, doc[0].rect.height / 72; doc.close()
    im = Image.open(O/f"{nm}.png"); dpi = im.info.get("dpi", (0, 0))
    FS[nm] = (min(sz), max(sz), len(sz), round(pw, 2), round(ph, 2), im.size, tuple(round(x) for x in dpi), fonts)
md = ["# Self-check of the v1 tables and figures", "", f"Script: `scripts/113_paper_tables.py`. Date: {time.strftime('%Y-%m-%d')}. Ledger: `out/RESULTS_LEDGER.csv` ({len(LG)} rows).", "",
      "Method: every cell of every table and figure carries the ledger numbers it uses; the script reads every number in the cell again and looks for it in those ledger rows "
      "(value cells: in 数值 only; label and header cells: in 说明 or 数值). Thousands separators, the strings 95% CI, cross-references (Table S4, Supplementary Methods 6, panel A) and the unit 10,000 JPY are not data and are skipped.", "",
      "| Item | Cells | Matched | Not matched |", "|---|---|---|---|",
      f"| Value cells with numbers | {n_val} | {ok_val} | {n_val - ok_val} |", f"| Label and header cells with numbers | {n_lab} | {ok_lab} | {n_lab - ok_lab} |", "",
      "Not matched: " + ("none." if not bad else ""), ""]
if bad: md += ["| Table | Row | Column | Text | Ledger |", "|---|---|---|---|---|"] + [f"| {x['table']} | {x['row']} | {x['column']} | {x['text']} | {x['ledger_ids']} |" for x in bad] + [""]
md += ["## Footnote symbols (notes vs table body; the table-wide note sits at the end of the title)", "", "| Table | Notes | Distinct symbols in body | One-to-one |", "|---|---|---|---|"]
md += [f"| {a} | {b_} | {c} | {'yes' if d else 'NO'} |" for a, b_, c, d in sym_rows] + [""]
md += ["## Fig. 1 against Tables 3 and S5 (main estimate column)", "", "| Table | Row | Fig. 1 | Table | Same |", "|---|---|---|---|---|"]
md += [f"| {a} | {b_} | {c} | {d} | {'yes' if e else 'NO'} |" for a, b_, c, d, e in cons] + [""]
md += ["## Flow arithmetic", "", "| Check | Computed | Ledger | Same |", "|---|---|---|---|"] + [f"| {a} | {b_} | {c} | {'yes' if b_ == c else 'NO'} |" for a, b_, c in arith] + [""]
md += ["## Figures (PDF fonts measured with PyMuPDF; PNG pixels and dpi with Pillow)", "", "| Figure | Min pt | Max pt | Text runs | Page (in) | PNG pixels | PNG dpi | Fonts |", "|---|---|---|---|---|---|---|---|"]
md += [f"| `{k}` | {v[0]:.1f} | {v[1]:.1f} | {v[2]} | {v[3]} × {v[4]} | {v[5][0]} × {v[5][1]} | {v[6][0]} | {', '.join(v[7])} |" for k, v in FS.items()] + [""]
md += [f"- `{k}`: {v}" for k, v in FIGS.items()] + [f"- right edge of the longest guideline label (inches; forest starts at 2.32): {LABEL_RIGHT}", ""]
(O/"selfcheck.md").write_text("\n".join(md), encoding="utf-8")
files = sorted(p.name for p in O.iterdir() if p.is_file() and p.name != "README.md")
(O/"README.md").write_text("\n".join(["# Tables and figures of manuscript v1 (stage 22, 2026-11-03)", "",
    "Script: `scripts/113_paper_tables.py`; every number is read from `out/RESULTS_LEDGER.csv` (machine keys in `work/ledger/keys.csv`; the narrow-window rows L789–L794 by number). "
    "The .json files are the layouts read by the docx builder of manuscript v1 (run once on 2026-11-03, then archived with the draft in `Desktop/上研/archive_influence_kg/paper_v1_20261103/build/build_docx.py`). Self-check: `selfcheck.md`. "
    "Earlier outputs (stage 17–21 numbering, Chinese labels): `out/archive_stage22/paper/`.", "", "Files:", ""] + [f"- `{f}`" for f in files]) + "\n", encoding="utf-8")
print("tables", len(SPECS), "| value cells", n_val, "matched", ok_val, "| label cells", n_lab, "matched", ok_lab, "| unmatched", len(bad))
print("symbols one-to-one", sum(1 for x in sym_rows if x[3]), "/", len(sym_rows), "| fig1 vs tables", sum(1 for x in cons if x[4]), "/", len(cons), "| arithmetic", sum(1 for a, b_, c in arith if b_ == c), "/", len(arith))
print("figures", {k: (round(v[0], 1), v[5], v[6]) for k, v in FS.items()}, {k: v.get("rows") for k, v in FIGS.items()})
