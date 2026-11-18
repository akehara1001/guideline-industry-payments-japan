# Industry payments to clinical practice guideline committees and to the issuing societies in Japan

Data and code for the manuscript "Industry payments to clinical practice guideline committees and to the issuing societies in Japan: an audit of 25 medical societies, 2022 to 2025".

The repository holds the audit units behind the main estimate, the guideline-company pairs behind the comparison of the two channels, the frozen prompts of the extraction pipeline and the analysis code. It holds no name of a person, no institution of a person and no amount paid to a person.

## Payment data

The payment data are public: they are the payments that pharmaceutical and medical device companies disclose. Personal payments of pharmaceutical companies in 2018, 2019, 2022 and 2023 come from the revised version of the pharmaceutical payment database (製薬マネーデータベース) dated 17 November 2026; S1 Text, section 1, of the manuscript lists the four files and their MD5 checksums. That version does not include the later re-acquisition of the AbbVie 2019 and Sun Pharma 2022 records. In fiscal year 2022, persons are defined by the person identifier of that version. Institutional payments (donations and co-sponsorship fees paid to medical societies) are those the companies disclosed for 2016 to 2023.

## Definitions

- Unit: one author × one company × one fiscal year × one payment category (lecture fees or manuscript fees) in which the company paid the author at least JPY 500,000 (the audit threshold) in a year within the guideline's declaration period.
- Declaration threshold: the amount from which the guideline asked its authors to declare a payment, taken from the guideline or, when the guideline did not state it, from the conflict-of-interest rules of the issuing society (data/guidelines_v10.csv, in 10,000 JPY).
- Judgment of a unit: declared (the author's declaration lists the company in that category and year), undeclared (it does not), not assessable (the documents do not allow a judgment, including a payment category outside the guideline's disclosed items), below the guideline's threshold (not counted).
- Amount class of a unit (data/units_v10.csv): the amount relative to the guideline's own declaration threshold for the category. "at or above the threshold" means at least the threshold and less than twice the threshold; "at least twice the threshold" means twice the threshold or more; "below the guideline's threshold" means less than the threshold. Every unit reached the audit threshold of JPY 500,000.
- Window of a guideline (two channels): the guideline's audit years, up to 2023 (the last year of the payment data).
- Groups of a guideline-company pair (two channels): A, the company paid one author of the guideline a lecture fee of at least the audit threshold (the larger of JPY 500,000 and the guideline's lecture-fee threshold) in one window year; B, the company paid at least one author a personal payment of any category in the window but is not in A; C, the company paid no author any personal payment in the window. The companies of a guideline are the merged companies with any published payment record (personal or institutional) in a window year.
- Society channel: the company paid the issuing societies of the guideline (each issuing society, its branches and regional meetings, and its meetings) society donations or co-sponsorship fees in the window.

## data/units_v10.csv (7,753 rows)

One row per audit unit: guideline × author × company node × payment category × fiscal year, for the 73 guidelines of the main analysis set (48) and the period-inferred layer (25).

| Column | Content |
|---|---|
| guideline | guideline key (data/guidelines_v10.csv) |
| analysis_set | main analysis set (declaration period stated) or period-inferred layer (period inferred from the title year) |
| author | committee member, replaced by a number (A0001 to A0851); the same number for the same normalized name across guidelines |
| payment_person | the person in the payment data to whom the author was linked, replaced by a number (Q00001 to Q00851); used for the deduplication by author × company × year |
| company_id, company_node | paying company and the merged company (data/companies_v10.csv) |
| company_node_industry | industry of the merged company (pharmaceutical or medical device); the industry used in the paper |
| payment_data | the data set in which the payment was disclosed (pharmaceutical or medical device) |
| payment_category | lecture fees or manuscript fees |
| fiscal_year | Japanese fiscal year of the payment (April to March) |
| amount_class | below the guideline's threshold, at or above the threshold, at least twice the threshold (see Definitions) |
| judgment_main | judgment of the main estimate (company-name corrections, item rule and threshold rule applied): declared, undeclared, not assessable, below the guideline's threshold |
| judgment_frozen_pipeline | judgment of the frozen pipeline before the corrections: declared, undeclared, not assessable |
| external_evaluation_committee | the author was a member of the external evaluation committee of one society (True or False) |
| last_fiscal_year_excluded_in_S10 | the unit lies in the last fiscal year of a declaration period that ended in 2023 or earlier (S10 Table) |

Check from this file alone (main analysis set, judgment_main declared or undeclared, deduplicated to payment_person × company_node × fiscal_year; a group is undeclared when all its units are undeclared):
pharmaceutical 730 of 3,479 undeclared (Table 4); at least twice the threshold 159 of 1,249; also outside the last fiscal year 116 of 942 (S10 Table);
medical device 87 of 331, 21 of 105 and 18 of 78.

## data/two_channels_pairs_v10.csv (12,537 rows)

One row per guideline × company pair of the 73 guidelines: the source of Table 3 and of panels A to C of S3 Table.

| Column | Content |
|---|---|
| guideline | guideline key (data/guidelines_v10.csv) |
| analysis_set | main analysis set or period-inferred layer |
| lead_society | lead society of the guideline (data/societies_v10.csv); the rows of S3 Table |
| window_first_year, window_last_year | the guideline's window (calendar years of the payment data) |
| company_node | merged company (data/companies_v10.csv) |
| company_node_industry | pharmaceutical or medical device (panels B and C of S3 Table) |
| group | A, B or C (see Definitions) |
| paid_issuing_society | the company is in the society channel of the guideline (True or False) |
| society_payment_jpy | the amount the company paid the issuing societies of the guideline in the window, in JPY (society donations and co-sponsorship fees; 0 when none). Amounts paid to organizations, not to persons. |
| paid_any_society_in_window | the company paid any medical society donations or co-sponsorship fees in the window (True or False); the companies of panel D of Table 3 |

Check from this file alone (proportion of pairs whose company paid the issuing society, Wilson 95% CI, with pairs; share of the society payments from the group: median (quartiles) over the guidelines with a non-zero total, numpy-linear quartiles; ratio of the proportions, group A vs group C; two decimals, rounded half up):

| Table 3 panel | Group A: pairs, proportion, share | Group B | Group C | Ratio A vs C |
|---|---|---|---|---|
| A all 73 | 1,081 | 0.98 [0.97, 0.99] (1,060/1,081) | 0.64 (0.47–0.75) | 2,937 | 0.77 [0.75, 0.78] (2,257/2,937) | 0.31 (0.23–0.47) | 8,519 | 0.22 [0.21, 0.23] (1,867/8,519) | 0.03 (0.01–0.06) | 4.47 |
| B main 48 | 808 | 0.98 [0.96, 0.98] (789/808) | 0.69 (0.48–0.79) | 2,028 | 0.75 [0.73, 0.77] (1,514/2,028) | 0.27 (0.20–0.46) | 5,413 | 0.21 [0.20, 0.22] (1,141/5,413) | 0.03 (0.01–0.06) | 4.63 |
| C inferred 25 | 273 | 0.99 [0.97, 1.00] (271/273) | 0.58 (0.47–0.68) | 909 | 0.82 [0.79, 0.84] (743/909) | 0.35 (0.29–0.47) | 3,106 | 0.23 [0.22, 0.25] (726/3,106) | 0.03 (0.02–0.06) | 4.25 |
| D universe d | 1,081 | 0.98 [0.97, 0.99] (1,060/1,081) | 0.64 (0.47–0.75) | 2,931 | 0.77 [0.75, 0.78] (2,257/2,931) | 0.31 (0.23–0.47) | 8,089 | 0.23 [0.22, 0.24] (1,867/8,089) | 0.03 (0.01–0.06) | 4.25 |

S3 Table, total row: 1,081 pairs in group A, 1,060 of them paying the issuing society; payments to the issuing societies 5,950,176 (10,000 JPY). Panel D of S3 Table (other definitions of the two sets) needs code/analysis/120_two_channels.py.

## data/guidelines_v10.csv, data/companies_v10.csv, data/societies_v10.csv

- guidelines_v10.csv: guideline key, title as published, title year, analysis set, declaration thresholds for lecture fees and manuscript fees (10,000 JPY), source class of the threshold (写在指南里 = stated in the guideline; 取自发行学会的规定 = taken from the issuing society's rules; values as in the project files).
- companies_v10.csv: company id, company name, industry of the company, the merged company (company_node) and its industry.
- societies_v10.csv: the 25 sampled societies: id, English name, code letter in Fig 2 and S1 Fig, number of guidelines of this study whose lead society it is.

## prompts/

The extraction prompt and the company-resolution prompt of pipeline v3.1, frozen on 11 October 2026. The sha256 of the frozen originals (as in the project's freeze record) are prompt_extraction_v3.md 4b75086155cb… and prompt_company_resolve_v2.md ed21781aac8a…. In these copies, and in code\analysis\113_paper_tables.py, the local user folder in file paths is replaced with &lt;user&gt;; nothing else differs from the files as run.

## code/

- pipeline/: building the payment tables (01), company keys (02), person keys (03, with its institution and specialty reference table), conversion of guideline documents to text (06) and the audit of pipeline v3.1 (04, frozen).
- analysis/: the analysis sets and their estimates (115), the paper tables and figures (113), the two channels (120, twochannel_comparison.py) and the pharmaceutical-device overlap (122).
- revised_data/: reading the revised 2018, 2019, 2022 and 2023 pharmaceutical files with the frozen 01 (mixload.py and its four settings).
- v9/: the AbbVie 2019 and Sun Pharma 2022 check (s3), the fiscal-year analysis of S10 Table (s4), the Table 2 recomputation (v9s0, v9t2) and the earlier release script.
- v10/: re-rounding half up of the proportions in the tables and figures (v10_rounding.py, v10_ledger_halfup.py) and the script that built this repository (v10_release.py).

The scripts are copied as they were run; their paths point to the project folders. The model extraction outputs, the guideline documents and the payment files are not included.
