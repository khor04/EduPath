"""
Generates the final UM career title -> O*NET mapping for all titles using
rule R4 (Curated -> Gemini), the strategy selected by the blind evaluation
(see career_mapping/README.md and data/mapping_eval/results_final_2026-09-18.txt).

  1. Curated: exact match of the title against O*NET occupation titles and
     O*NET's Sample of Reported Titles; used only when exactly ONE
     occupation matches.
  2. Gemini fallback for everything else: same model, prompt and settings
     as the evaluation run. Titles already answered in that run (the
     100-title sample) reuse those answers instead of spending quota.

Built for the free tier's 20 requests/day, shared with the deployed app:
  - progress is saved after every batch, so re-running resumes;
  - a title is never re-sent once it has a valid answer;
  - a DAILY quota error stops the run immediately (a per-minute one waits
    and retries);
  - any answer that isn't a real O*NET code is logged and retried on a
    later run, never saved.

Run from anywhere (paths are relative to this file, not the working directory):
    python career_mapping/scripts/final_mapping_r4.py
GEMINI_API_KEY is read from the environment or from the repo's .env. Use --dry-run to see how many calls a
run would need without calling Gemini.
"""
import csv
import json
import os
import re
import sys
import time
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # the career_mapping/ folder

MODEL = "gemini-3.6-flash"
BATCH_SIZE = 50
SECONDS_BETWEEN_CALLS = 15
PER_MINUTE_RETRY_WAITS = [60, 120]

UM_CAREERS = os.path.join(ROOT, "data", "um_career_prospects.csv")
ONET_TITLES = os.path.join(ROOT, "data", "onet_occupation_titles.csv")
ONET_REPORTED = os.path.join(ROOT, "data", "onet_reported_titles.csv")
EVAL_GEMINI = os.path.join(ROOT, "data", "mapping_eval", "PRIVATE_do_not_share", "method_gemini.csv")

OUT_DIR = os.path.join(ROOT, "data", "mapping_final")
PROGRESS = os.path.join(OUT_DIR, "gemini_answers.json")
FAILURE_LOG = os.path.join(OUT_DIR, "failures.log")
TITLE_MAPPING = os.path.join(ROOT, "data", "career_title_onet_mapping.csv")
PROGRAMME_MAPPING = os.path.join(ROOT, "data", "programme_career_onet_mapping.csv")

PROMPT = """You are mapping Malaysian university career titles to occupations in the US O*NET-SOC taxonomy.

For EACH numbered career title below, choose the ONE O*NET occupation (from the list below) whose
main work duties best represent that career. Choose ONLY codes that appear in the list — never invent a code.

If no occupation in the list reasonably represents the career's main duties, answer "NONE" rather than
forcing a weak match.

Give a confidence between 0 and 1 that your chosen occupation (or NONE) is the correct answer.

O*NET OCCUPATIONS (code | title):
{occ_block}

CAREER TITLES:
{titles_block}

Respond with ONLY a JSON object keyed by the career number (as a string):
{{"1": {{"onet_code": "<code from the list, or NONE>", "confidence": 0.0}}, "2": ...}}"""


def read_csv(path):
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def norm(title):
    """Same normalisation as the evaluated curated method (curated_method.py)."""
    t = title.lower().replace("&", " and ")
    t = re.sub(r"[^a-z0-9 ]", " ", t)
    words = t.split()
    if words and len(words[-1]) > 3 and words[-1].endswith("s") and not words[-1].endswith("ss"):
        words[-1] = words[-1][:-1]
    return " ".join(words)


def title_variants(title):
    base = re.sub(r"\(.*?\)", "", title).strip()
    yield title
    if base != title:
        yield base
    if "/" in base:
        yield from base.split("/")


def curated_matches(um_titles, occupations):
    lookup = {}
    for code, title in occupations.items():
        lookup.setdefault(norm(title), set()).add(code)
    for r in read_csv(ONET_REPORTED):
        lookup.setdefault(norm(r["reported_title"]), set()).add(r["onet_code"])

    result = {}
    for t in um_titles:
        hits = next((lookup[norm(v)] for v in title_variants(t) if lookup.get(norm(v))), set())
        if len(hits) == 1:
            result[t] = next(iter(hits))
    return result


def log_failure(message):
    with open(FAILURE_LOG, "a", encoding="utf-8") as f:
        f.write(f"{datetime.now().isoformat(timespec='seconds')}  {message}\n")


def load_progress():
    if os.path.exists(PROGRESS):
        with open(PROGRESS, encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_progress(answers):
    tmp = PROGRESS + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(answers, f, indent=1, ensure_ascii=False)
    os.replace(tmp, PROGRESS)


def call_gemini(model, prompt):
    """Returns the response, or None if the DAILY quota is exhausted."""
    from google.api_core.exceptions import ResourceExhausted

    for wait in [0] + PER_MINUTE_RETRY_WAITS:
        if wait:
            print(f"  per-minute limit hit, waiting {wait}s", flush=True)
            time.sleep(wait)
        try:
            return model.generate_content(prompt)
        except ResourceExhausted as e:
            if "PerDay" in str(e):
                return None
    return None


def run_gemini(pending, occupations, answers):
    import google.generativeai as genai
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    genai.configure(api_key=os.environ["GEMINI_API_KEY"])
    model = genai.GenerativeModel(MODEL, generation_config={"temperature": 0, "response_mime_type": "application/json"})
    occ_block = "\n".join(f"{c} | {t}" for c, t in occupations.items())

    for start in range(0, len(pending), BATCH_SIZE):
        batch = pending[start:start + BATCH_SIZE]
        prompt = PROMPT.format(occ_block=occ_block, titles_block="\n".join(f"{i + 1}. {t}" for i, t in enumerate(batch)))

        response = call_gemini(model, prompt)
        if response is None:
            print("Daily quota reached -- progress saved, re-run tomorrow to continue.")
            log_failure(f"daily quota reached with {len(pending) - start} titles still pending")
            return False

        try:
            raw = json.loads(response.text)
        except ValueError:
            log_failure(f"unparseable response for batch starting at {batch[0]!r}")
            continue

        saved = 0
        for i, title in enumerate(batch, 1):
            entry = raw.get(str(i), {})
            code = str(entry.get("onet_code", "")).strip()
            if code == "NONE" or code in occupations:
                answers[title] = {"onet_code": code, "confidence": entry.get("confidence"), "source_run": "final"}
                saved += 1
            else:
                log_failure(f"invalid code {code!r} for {title!r} -- will retry next run")

        save_progress(answers)
        print(f"  batch {start // BATCH_SIZE + 1}/{-(-len(pending) // BATCH_SIZE)}: {saved}/{len(batch)} saved", flush=True)
        time.sleep(SECONDS_BETWEEN_CALLS)

    return True


def write_outputs(um_rows, occupations, curated, answers):
    by_title = {}
    for t in sorted({r["career_title"] for r in um_rows}):
        if t in curated:
            by_title[t] = {"onet_code": curated[t], "mapping_method": "curated", "gemini_confidence": ""}
        elif t in answers and answers[t]["onet_code"] != "NONE":
            by_title[t] = {"onet_code": answers[t]["onet_code"], "mapping_method": "gemini",
                           "gemini_confidence": answers[t]["confidence"]}
        else:
            by_title[t] = {"onet_code": "", "mapping_method": "unmapped" if t in answers else "pending",
                           "gemini_confidence": answers.get(t, {}).get("confidence", "")}

    fields = ["um_title", "onet_code", "onet_title", "mapping_method", "gemini_confidence"]
    with open(TITLE_MAPPING, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for t, m in by_title.items():
            w.writerow({"um_title": t, "onet_title": occupations.get(m["onet_code"], ""), **m})

    with open(PROGRAMME_MAPPING, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["faculty", "programme", "programme_slug"] + fields)
        w.writeheader()
        for r in um_rows:
            m = by_title[r["career_title"]]
            w.writerow({"faculty": r["faculty"], "programme": r["programme"], "programme_slug": r["programme_slug"],
                        "um_title": r["career_title"], "onet_title": occupations.get(m["onet_code"], ""), **m})
    return by_title


def validate(by_title, um_rows, occupations):
    counts = {}
    for m in by_title.values():
        counts[m["mapping_method"]] = counts.get(m["mapping_method"], 0) + 1
    invalid = sum(1 for m in by_title.values() if m["onet_code"] and m["onet_code"] not in occupations)

    per_programme = {}
    for r in um_rows:
        mapped = bool(by_title[r["career_title"]]["onet_code"])
        per_programme.setdefault(r["programme"], [0, 0])
        per_programme[r["programme"]][0] += mapped
        per_programme[r["programme"]][1] += 1
    thin = {p: v for p, v in per_programme.items() if v[0] < 6}

    print("\n=== Validation ===")
    print(f"Total unique titles : {len(by_title)}")
    for k in ["curated", "gemini", "unmapped", "pending"]:
        print(f"  {k:9}: {counts.get(k, 0)}")
    print(f"Invalid O*NET codes : {invalid}")
    print(f"Programmes          : {len(per_programme)}, with < 6 mapped careers: {len(thin)}")
    for p, (m, n) in sorted(thin.items()):
        print(f"    {p}: {m}/{n}")


def main():
    dry_run = "--dry-run" in sys.argv
    os.makedirs(OUT_DIR, exist_ok=True)

    um_rows = read_csv(UM_CAREERS)
    um_titles = sorted({r["career_title"] for r in um_rows})
    occupations = {r["onet_code"]: r["onet_title"] for r in read_csv(ONET_TITLES)}

    curated = curated_matches(um_titles, occupations)

    answers = load_progress()
    for r in read_csv(EVAL_GEMINI):
        if r["um_title"] not in answers and (r["onet_code"] == "NONE" or r["onet_code"] in occupations):
            answers[r["um_title"]] = {"onet_code": r["onet_code"], "confidence": float(r["confidence"]),
                                      "source_run": "evaluation"}
    save_progress(answers)

    pending = [t for t in um_titles if t not in curated and t not in answers]
    print(f"{len(um_titles)} titles: {len(curated)} curated, {len(um_titles) - len(curated) - len(pending)} "
          f"already answered by Gemini, {len(pending)} pending -> {-(-len(pending) // BATCH_SIZE)} Gemini calls needed")

    if pending and not dry_run:
        run_gemini(pending, occupations, answers)

    by_title = write_outputs(um_rows, occupations, curated, answers)
    validate(by_title, um_rows, occupations)


if __name__ == "__main__":
    main()
