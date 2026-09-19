"""
Draws the evaluation sample for the UM-career-title -> O*NET mapping
experiment: a fixed, faculty-stratified random sample of unique UM
career titles that independent reviewers label, and that every
mapping method (curated O*NET title match, JobBERT, Gemini) is later
scored against.

The sample is drawn BEFORE any method's output is inspected, and
from a fixed seed, so the choice of titles can't be (even
unconsciously) steered towards titles some method happens to get
right -- and anyone re-running this gets the identical sample.

Stratification: every faculty gets at least MIN_PER_FACULTY titles
(so small faculties like Nursing or Pharmacy are actually tested),
the rest is allocated proportionally to each faculty's number of
unique titles. A title listed by more than one faculty (127 of 1,010)
is counted under the alphabetically-first one, so it can only be
drawn once.

Usage (paths default to this folder's data/, whatever the working directory):
    python career_mapping/scripts/sample_mapping_eval.py [input.csv] [output.csv]
"""
import csv
import os
import random
import sys
from collections import defaultdict

SEED = 20260918
SAMPLE_SIZE = 100
MIN_PER_FACULTY = 3


def allocate(counts, total, minimum):
    """Largest-remainder proportional allocation with a per-stratum floor."""
    alloc = {f: min(minimum, n) for f, n in counts.items()}
    remaining = total - sum(alloc.values())
    spare = {f: n - alloc[f] for f, n in counts.items()}
    spare_total = sum(spare.values())

    quotas = {f: remaining * s / spare_total for f, s in spare.items()}
    for f, q in quotas.items():
        alloc[f] += int(q)
    leftover = total - sum(alloc.values())
    for f in sorted(quotas, key=lambda f: quotas[f] - int(quotas[f]), reverse=True)[:leftover]:
        alloc[f] += 1
    return alloc


def draw_sample(rows):
    faculties_by_title = defaultdict(set)
    programmes_by_title = defaultdict(set)
    for r in rows:
        faculties_by_title[r["career_title"]].add(r["faculty"])
        programmes_by_title[r["career_title"]].add(r["programme"])

    titles_by_faculty = defaultdict(list)
    for title, faculties in faculties_by_title.items():
        titles_by_faculty[sorted(faculties)[0]].append(title)

    alloc = allocate({f: len(t) for f, t in titles_by_faculty.items()}, SAMPLE_SIZE, MIN_PER_FACULTY)

    rng = random.Random(SEED)
    sample = []
    for faculty in sorted(titles_by_faculty):
        for title in rng.sample(sorted(titles_by_faculty[faculty]), alloc[faculty]):
            sample.append({
                "um_title": title,
                "stratum_faculty": faculty,
                "programmes": "; ".join(sorted(programmes_by_title[title])),
            })
    return sample, alloc


if __name__ == "__main__":
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # the career_mapping/ folder
    src = sys.argv[1] if len(sys.argv) > 1 else os.path.join(root, "data", "um_career_prospects.csv")
    out = sys.argv[2] if len(sys.argv) > 2 else os.path.join(root, "data", "mapping_eval_sample.csv")

    with open(src, encoding="utf-8") as f:
        sample, alloc = draw_sample(list(csv.DictReader(f)))

    with open(out, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["um_title", "stratum_faculty", "programmes"])
        writer.writeheader()
        writer.writerows(sample)

    for faculty, n in sorted(alloc.items(), key=lambda x: -x[1]):
        print(f"{n:3}  {faculty}")
    print(f"\n{len(sample)} titles -> {out} (seed {SEED})")
