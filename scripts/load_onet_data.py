"""
One-time reference-data loader: reads the O*NET 31.0 CSV exports
(Occupation Data, Essential Skills, Transferable Skills, Knowledge)
and populates OnetOccupation / OnetOccupationConcept.

Not run automatically by the app -- this is reference data that
changes only when O*NET publishes a new release, not per-request.
Re-running is safe: every call clears both tables first, then reloads
from scratch, so running it twice never produces duplicate rows.

Usage:
    python scripts/load_onet_data.py <path-to-directory-containing-the-4-csvs>
"""
import sys
import os

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from extensions import db
from models.onet_occupation import OnetOccupation
from models.onet_occupation_concept import OnetOccupationConcept
from services.career_services import SKILL_NAMES, KNOWLEDGE_NAMES

# Rows flagged Y here are O*NET's own recommendation to exclude them
# (small sample size / unreliable rating) -- found during Phase 2A
# inspection: only 21 of ~18,200 essential-skill rows are flagged.
SUPPRESS_FLAG_VALUE = "Y"


def _normalize(raw_value, scale_min=1, scale_max=5):
    return (raw_value - scale_min) / (scale_max - scale_min)


def load_onet_data(data_dir):
    """
    Returns a dict summary of what was loaded/skipped, so callers
    (the __main__ block, or a test) can report on it without needing
    to re-query the DB themselves.
    """
    occ = pd.read_csv(os.path.join(data_dir, "occupation_data.csv"))
    essential = pd.read_csv(os.path.join(data_dir, "essential_skills.csv"))
    transferable = pd.read_csv(os.path.join(data_dir, "transferable_skills.csv"))
    knowledge = pd.read_csv(os.path.join(data_dir, "knowledge.csv"))

    summary = {
        "occupations_loaded": 0,
        "skill_concepts_loaded": 0,
        "knowledge_concepts_loaded": 0,
        "unexpected_concept_names": set(),
        "suppressed_rows_skipped": 0,
    }

    # ---- Occupations ----
    OnetOccupation.query.delete()
    for _, row in occ.iterrows():
        db.session.add(OnetOccupation(
            onet_soc_code=row["O*NET-SOC Code"],
            title=row["Title"],
            description=row["Description"],
        ))
        summary["occupations_loaded"] += 1
    db.session.commit()

    # ---- Skills (essential + transferable, Importance scale only) ----
    OnetOccupationConcept.query.delete()

    skills = pd.concat([essential, transferable])
    skills_im = skills[skills["Scale ID"] == "IM"]

    for _, row in skills_im.iterrows():
        if row.get("Recommend Suppress") == SUPPRESS_FLAG_VALUE:
            summary["suppressed_rows_skipped"] += 1
            continue

        name = row["Element Name"]
        if name not in SKILL_NAMES:
            summary["unexpected_concept_names"].add(("skill", name))
            continue

        raw = float(row["Data Value"])
        db.session.add(OnetOccupationConcept(
            onet_soc_code=row["O*NET-SOC Code"],
            concept_type="skill",
            concept_name=name,
            importance_raw=raw,
            importance_normalized=_normalize(raw),
        ))
        summary["skill_concepts_loaded"] += 1

    # ---- Knowledge (Importance scale only) ----
    knowledge_im = knowledge[knowledge["Scale ID"] == "IM"]

    for _, row in knowledge_im.iterrows():
        if row.get("Recommend Suppress") == SUPPRESS_FLAG_VALUE:
            summary["suppressed_rows_skipped"] += 1
            continue

        name = row["Element Name"]
        if name not in KNOWLEDGE_NAMES:
            summary["unexpected_concept_names"].add(("knowledge", name))
            continue

        raw = float(row["Data Value"])
        db.session.add(OnetOccupationConcept(
            onet_soc_code=row["O*NET-SOC Code"],
            concept_type="knowledge",
            concept_name=name,
            importance_raw=raw,
            importance_normalized=_normalize(raw),
        ))
        summary["knowledge_concepts_loaded"] += 1

    db.session.commit()

    return summary


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python scripts/load_onet_data.py <path-to-onet-csv-directory>")
        sys.exit(1)

    from app import create_app
    app = create_app()

    with app.app_context():
        result = load_onet_data(sys.argv[1])
        print(result)
