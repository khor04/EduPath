# Career mapping: UM career titles → O*NET occupations

Everything about how EduPath's career list was built lives in this folder.
**Open `edupath_mapping_evaluation.ipynb`.** It summarises the whole experiment and
recomputes every result from the saved files (no API key needed).

```
career_mapping/
├── README.md                              this file
├── edupath_mapping_evaluation.ipynb       the summary notebook (open this)
├── edupath_mapping_evaluation.zip         data for running the notebook in Google Colab
├── data/                                  all inputs, method outputs, reviewer labels, final mapping
│   ├── um_career_prospects.csv            scraped UM Career Prospects (80 programmes, 1,615 rows)
│   ├── career_title_onet_mapping.csv      FINAL mapping, one row per unique title
│   ├── programme_career_onet_mapping.csv  FINAL mapping, one row per programme × career
│   ├── mapping_eval_sample.csv            the 100-title evaluation sample
│   ├── onet_*.csv                         O*NET 31.0 occupation / reported job titles
│   ├── mapping_eval/                      reviewer workbooks, method outputs, results
│   └── mapping_final/                     progress + log of the final Gemini run (resumable)
└── scripts/                               everything that produced the data
```

## Outcome

Strategy **R4 = Curated → Gemini**, chosen by a blind evaluation (results in
`data/mapping_eval/results_final_2026-09-18.txt` and the notebook). Final mapping,
run 2026-09-19: 1,010 titles → 243 curated, 748 Gemini, 19 unmapped (Gemini answered
NONE), 0 invalid codes, every programme has at least 6 mapped careers.

Gemini is used only here, once, for data preparation. EduPath's career *ranking*
is O*NET-based cosine similarity against the student's academic profile.

## Scripts, in the order they were used

Scripts 1, 2 and 8–10 find their files relative to this folder, so they run from
any working directory. Scripts 3–7 were experiment scripts run from a scratch
working directory containing `onet/db_31_0_csv/` (the O*NET 31.0 CSV bundle,
https://www.onetcenter.org/dl_files/database/db_31_0_csv.zip, 16 MB, not stored here)
and a copy of `um_career_prospects.csv`; they are kept as the record of how the
evaluation was produced.

| # | Script | Output |
|---|---|---|
| 1 | `scrape_um_career_prospects.py` (needs `pip install beautifulsoup4`) | `um_career_prospects.csv` |
| 2 | `sample_mapping_eval.py`: fixed seed, drawn before any method output was seen | `mapping_eval_sample.csv` |
| 3 | `curated_method.py`: exact match on O*NET occupation titles + Sample of Reported Titles; only when exactly one occupation matches | `method_curated.csv` |
| 4 | `jobbert_map.py` (TechWolf/JobBERT-v2; needs `sentence-transformers` + CPU PyTorch in a separate virtualenv, not the app's) | `jobbert_top3.csv` |
| 5 | `gemini_map.py` (gemini-3.6-flash, all 1,016 occupations, NONE allowed, temperature 0; the 100 sample titles only) | `method_gemini.csv`, `gemini_raw/` |
| 6 | `build_review_sheet.py`: blind, shuffled candidate pools | `review_Reviewer_A/B.xlsx`, `review_PRIVATE_option_key.csv` |
| 7 | `build_tiebreak_sheet.py`: the 28 titles where A and B disagreed | `review_Reviewer_C_tiebreak.xlsx` |
| 8 | `score.py` / `score_final.py` (run from `data/mapping_eval/`) | `results_*.txt` |
| 9 | **`final_mapping_r4.py`**: applies R4 to all 1,010 titles | the two FINAL mapping CSVs |
| 10 | `build_notebook_zip.py` | `edupath_mapping_evaluation.zip` |

### Regenerating the final mapping

    python career_mapping/scripts/final_mapping_r4.py            # --dry-run to see how many calls are needed

It saves after every batch, resumes on re-run, rejects any code that isn't a real
O*NET occupation, and stops cleanly at the daily quota. The Gemini free tier allows
20 requests/day per project, shared with the deployed app, so don't run it while
the site is being tested. It reads `GEMINI_API_KEY` from the environment or the
repo's `.env`.

### Updating the notebook's data

After any change under `data/`, run `python career_mapping/scripts/build_notebook_zip.py`,
then in Colab: **Runtime → Restart session and run all** and upload the new zip.

## Candidate rules (pre-registered 2026-09-18, before any labels existed)

Only these were scored, so the winner wasn't tuned to the 100 sampled titles. Method
scores are on different scales (binary / embedding similarity / LLM self-reported
confidence), so rules combine methods by agreement, never by comparing scores.

| Rule | Logic |
|---|---|
| R1 | Curated only |
| R2 | JobBERT top-1 only |
| R3 | Gemini only |
| R4 | Curated, else Gemini **(selected)** |
| R5 | Curated, else JobBERT & Gemini agree, else Gemini |
| R6 | Curated, else JobBERT & Gemini agree, else unmapped |

**Scoring rule (fixed before labelling):** a method is correct on a title if it returns
the reviewer's occupation, or if both it and the reviewer say no occupation fits (NONE).
Reported per method: precision (correct ÷ mapped), coverage (mapped ÷ evaluated).
Reviewer B is independent (primary reference); A is the system developer; C is an
independent tie-break on the titles where A and B disagreed.

## Sensitive folder

`data/mapping_eval/PRIVATE_do_not_share/` holds method outputs and the key that decodes
the reviewers' option letters. It had to stay hidden from reviewers while they labelled;
now that labelling is finished it is evidence, and the zip ships it as `method_outputs/`.
