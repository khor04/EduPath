"""
Programme -> the careers UM officially lists for it, each linked to an
O*NET occupation.

This is what restricts EduPath's career recommendations to careers a
student's own degree actually leads to. Ranking every O*NET occupation
(the earlier approach) suggested e.g. Orthoptists and Physicians to a
Nursing student, because skill similarity alone cannot know that a
degree qualifies you for one job and not another. The mapping itself is
built and evaluated offline -- see career_mapping/README.md.

Reads the programme x career mapping CSV once per process and keeps it
in memory, like the O*NET occupation vectors in career_services. It is
static reference data: regenerate the CSV (career_mapping/scripts/
final_mapping_r4.py) and restart the app to pick up changes.
"""
import csv
import logging
import os

from utils.programmes import normalize_programme, programmes_match

log = logging.getLogger(__name__)

MAPPING_CSV = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "career_mapping", "data", "programme_career_onet_mapping.csv",
)

# Names a student can pick at signup that differ from the programme's
# name on UM's own programme page (the source of the career lists).
PROGRAMME_ALIASES = {
    "Bachelor of Accounting": "BACHELOR IN ACCOUNTING",
    "Bachelor of Pharmacy": "BACHELOR OF PHARMACY WITH HONOURS",
    "Bachelor of Media Studies": "BACHELOR OF MEDIA STUDIES (INDUSTRIAL MODE)",
    "Bachelor of Exercise Science": "BACHELOR OF SPORTS SCIENCE (EXERCISE SCIENCE)",
}
_ALIASES_BY_NORMALIZED_NAME = {normalize_programme(k): v for k, v in PROGRAMME_ALIASES.items()}

_careers_by_programme = None   # {UM programme name: [career dicts in UM's own list order]}
_resolved = {}                 # student's programme string -> UM programme name (or None)


def _load():
    """Only careers with an O*NET link can be scored, so unmapped ones are left out."""
    global _careers_by_programme
    if _careers_by_programme is not None:
        return _careers_by_programme

    careers = {}
    try:
        with open(MAPPING_CSV, encoding="utf-8", newline="") as f:
            for row in csv.DictReader(f):
                if not row["onet_code"]:
                    continue
                careers.setdefault(row["programme"], []).append({
                    "um_title": row["um_title"],
                    "onet_code": row["onet_code"],
                    "onet_title": row["onet_title"],
                    "mapping_method": row["mapping_method"],
                })
    except OSError:
        # Callers fall back to the unrestricted O*NET ranking, so a missing
        # file degrades recommendation quality but never breaks the page.
        log.error("Programme career mapping not found at %s", MAPPING_CSV)

    _careers_by_programme = careers
    return careers


def resolve_um_programme(programme):
    """The UM programme name matching what the student registered with, or None."""
    if not programme:
        return None
    if programme in _resolved:
        return _resolved[programme]

    target = _ALIASES_BY_NORMALIZED_NAME.get(normalize_programme(programme), programme)
    matches = [name for name in _load() if programmes_match(target, name)]

    # Zero matches = unknown programme (e.g. an admin's placeholder "N/A").
    # More than one = ambiguous; refuse to guess rather than pick the wrong degree.
    resolved = matches[0] if len(matches) == 1 else None
    if len(matches) > 1:
        log.warning("Programme %r matches several UM programmes: %s", programme, matches)
    _resolved[programme] = resolved
    return resolved


def get_programme_careers(programme):
    """
    The student's programme's careers that have an O*NET link, in UM's own
    order: a list of {"um_title", "onet_code", "onet_title", "mapping_method"}.
    None if the programme can't be resolved, so the caller can fall back.
    """
    um_programme = resolve_um_programme(programme)
    if um_programme is None:
        return None
    return _load()[um_programme]
