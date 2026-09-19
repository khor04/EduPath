from collections import Counter, defaultdict

from sqlalchemy.orm import joinedload

from extensions import db
from models.users import User
from models.semester import Semester
from models.transcript import Transcript
from models.contact import ContactMessage
from models.career_recommendation import CareerRecommendation
from models.feedback import Feedback
from models.target_cgpa import TargetCGPA
from services.cgpa_services import detect_trend

# Anonymity floor for the Performance Trends view. Deliberately stricter
# than benchmark_services.MIN_PEERS (2): that one only gates a student
# seeing their own standing, whereas this one is what stops an admin
# from pinning "declining" on a specific student in a small group.
MIN_TREND_GROUP = 5

INSUFFICIENT_DATA = "Insufficient Data"

# Display order, best -> worst, with the no-verdict bucket last.
TREND_LABELS = [
    "Improving",
    "Slightly Improving",
    "Stable",
    "Volatile",
    "Slightly Declining",
    "Declining",
    INSUFFICIENT_DATA,
]

# "Volatile" is intentionally not in here: an unstable GPA pattern isn't
# the same claim as a downward one.
DECLINING_LABELS = ("Slightly Declining", "Declining")


def get_feedback_summary():
    """
    One row per distinct career name that has at least one rating,
    aggregated across every student who was ever recommended that
    career -- not per-recommendation-instance, since the point is to
    see how a given career is landing across the whole student body.

    Sorted by average rating ascending, so the careers most worth an
    admin's attention (algorithm says "Strong Match", students keep
    rating it low) surface first.
    """
    rows = (
        db.session.query(
            CareerRecommendation.career_name,
            CareerRecommendation.career_score,
            CareerRecommendation.match_level,
            Feedback.rating,
        )
        .join(Feedback, Feedback.career_id == CareerRecommendation.career_id)
        .all()
    )

    by_career = {}
    for career_name, career_score, match_level, rating in rows:
        entry = by_career.setdefault(career_name, {
            "career_name": career_name,
            "ratings": [],
            "scores": [],
            "match_levels": Counter(),
        })
        entry["ratings"].append(rating)
        entry["scores"].append(career_score or 0)
        entry["match_levels"][match_level] += 1

    summary = []
    for entry in by_career.values():
        ratings = entry["ratings"]
        distribution = Counter(ratings)

        summary.append({
            "career_name": entry["career_name"],
            "avg_rating": round(sum(ratings) / len(ratings), 2),
            "num_ratings": len(ratings),
            "distribution": {star: distribution.get(star, 0) for star in range(1, 6)},
            "avg_score": round(sum(entry["scores"]) / len(entry["scores"]), 4),
            "match_level": entry["match_levels"].most_common(1)[0][0],
        })

    summary.sort(key=lambda row: row["avg_rating"])
    return summary


def get_feedback_overview(summary):
    """
    Single-number roll-up across every rated career, for the summary
    header on the Career Feedback page -- built from get_feedback_summary()'s
    output rather than re-querying, since it already has every rating
    grouped by career.
    """
    if not summary:
        return {"avg_rating": None, "total_responses": 0}

    total_responses = sum(row["num_ratings"] for row in summary)
    weighted_total = sum(row["avg_rating"] * row["num_ratings"] for row in summary)

    return {
        "avg_rating": round(weighted_total / total_responses, 2),
        "total_responses": total_responses,
    }


def get_contact_messages():
    return (
        ContactMessage.query
        .options(joinedload(ContactMessage.user))
        .order_by(ContactMessage.created_at.desc())
        .all()
    )


def get_platform_stats():
    # These stats describe student adoption of the system, so admin
    # accounts are excluded throughout -- an admin is provisioned with
    # placeholder faculty/programme/batch ("N/A", see
    # scripts/create_admin.py) since it never goes through /signup,
    # and would otherwise show up as a fake "N/A" faculty/programme
    # category or inflate the verified-user count.
    students = User.query.filter_by(is_admin=False)

    total_users = students.count()
    verified_users = students.filter_by(is_verified=True).count()
    unverified_users = total_users - verified_users
    total_transcripts = Transcript.query.count()

    career_users = (
        db.session.query(CareerRecommendation.user_id)
        .distinct()
        .count()
    )
    target_cgpa_plans = TargetCGPA.query.count()

    users_by_programme = dict(
        db.session.query(User.programme, db.func.count(User.user_id))
        .filter(User.is_admin == False)
        .group_by(User.programme)
        .order_by(db.func.count(User.user_id).desc())
        .all()
    )

    users_by_faculty = dict(
        db.session.query(User.faculty, db.func.count(User.user_id))
        .filter(User.is_admin == False)
        .group_by(User.faculty)
        .order_by(db.func.count(User.user_id).desc())
        .all()
    )

    # Tri-state, same as User.benchmark_consent itself -- "declined"
    # and "hasn't decided yet" are different signals for an admin
    # (e.g. a large "not yet decided" group suggests students aren't
    # discovering the consent prompt, not that they're rejecting it).
    benchmark_participation = {
        "Consented": students.filter_by(benchmark_consent=True).count(),
        "Declined": students.filter_by(benchmark_consent=False).count(),
        "Not yet decided": students.filter(User.benchmark_consent.is_(None)).count(),
    }

    return {
        "total_users": total_users,
        "verified_users": verified_users,
        "unverified_users": unverified_users,
        "total_transcripts": total_transcripts,
        "career_users": career_users,
        "target_cgpa_plans": target_cgpa_plans,
        "users_by_programme": users_by_programme,
        "users_by_faculty": users_by_faculty,
        "benchmark_participation": benchmark_participation,
    }


def get_trend_filter_options():
    """Programmes / batches that actually have students, for the filter dropdowns."""
    def distinct(column):
        rows = (
            db.session.query(column)
            .filter(User.is_admin == False)
            .distinct()
            .order_by(column)
            .all()
        )
        return [value for (value,) in rows]

    return {"programmes": distinct(User.programme), "batches": distinct(User.batch)}


# Internal key: Slightly Declining + Declining treated as ONE unit for
# suppression, because the page shows their sum as the headline.
_DECLINING_UNIT = "declining-total"


def _pins_a_cell(units, hidden, min_group):
    """
    True if some hidden unit's true value could be worked out from what
    the page shows: the overall total, every visible unit, and the
    public rule for hidden ones (a genuinely small unit is 1..min_group-1;
    one hidden only to protect a neighbour is >= min_group).

    Simple interval arithmetic: the hidden units must add up to a known
    remainder, so each one is squeezed between its own bounds and what
    the others leave over. Pinned when that range is a single value.
    """
    if not hidden:
        return False

    total = sum(units.values())
    remainder = total - sum(n for unit, n in units.items() if unit not in hidden)
    bounds = {
        unit: (1, min_group - 1) if 0 < units[unit] < min_group else (min_group, remainder)
        for unit in hidden
    }
    low_sum = sum(low for low, _ in bounds.values())
    high_sum = sum(high for _, high in bounds.values())

    for low, high in bounds.values():
        narrowed_low = max(low, remainder - (high_sum - high))
        narrowed_high = min(high, remainder - (low_sum - low))
        if narrowed_low >= narrowed_high:
            return True
    return False


def _hidden_units(units, min_group):
    """
    Which units (see _DECLINING_UNIT) must not show their real count.

    Primary suppression: counts of 1..min_group-1. (A 0 says nothing
    about an individual, so it stays visible.)

    Complementary suppression: the page also shows the overall total,
    so a lone hidden count would just be total minus the rest. While
    any hidden count can still be pinned down (see _pins_a_cell), hide
    one more: the smallest visible unit that fixes it, else the largest
    one and check again. The declining headline is the number the
    admin actually wants, so it is the last to go.

    Returns None when even hiding every non-zero unit can't stop a
    value being pinned down (only possible in very small groups, e.g.
    12 students split 1/5/5/1) -- the caller then shows nothing.
    """
    hidden = {unit for unit, n in units.items() if 0 < n < min_group}

    while _pins_a_cell(units, hidden, min_group):
        candidates = sorted(
            (unit for unit, n in units.items() if n > 0 and unit not in hidden),
            key=lambda unit: (unit == _DECLINING_UNIT, units[unit]),
        )
        if not candidates:
            return None

        for unit in candidates:
            if not _pins_a_cell(units, hidden | {unit}, min_group):
                hidden.add(unit)
                break
        else:
            hidden.add(([u for u in candidates if u != _DECLINING_UNIT] or candidates)[-1])

    return hidden


def get_trend_summary(programme=None, batch=None, min_group=MIN_TREND_GROUP):
    """
    Anonymous, counts-only breakdown of students' GPA trends for one
    programme and/or batch (None = all).

    Each student's trend is worked out from their semester GPAs with
    the same detect_trend() the student's own dashboard alert uses, so
    the two can't disagree. The per-student labels only exist inside
    this function -- what comes back is counts per label, already
    passed through the small-group suppression below, so nothing
    student-level can reach a template.

    Students with no semester GPA at all (no transcript uploaded yet)
    aren't counted. Students with only one semester get
    "Insufficient Data" rather than detect_trend()'s default "Stable",
    which would pass off "no comparison possible" as "steady".

    Known limit: suppression is per view. An admin comparing "All
    programmes" against a single programme can still subtract one from
    the other, so every group shown must independently clear
    min_group.
    """
    query = (
        db.session.query(
            Transcript.user_id,
            Semester.academic_session,
            Semester.semester_no,
            Semester.semester_gpa,
        )
        .join(Transcript, Semester.transcript_id == Transcript.transcript_id)
        .join(User, Transcript.user_id == User.user_id)
        .filter(User.is_admin == False, Semester.semester_gpa != None)
    )
    if programme:
        query = query.filter(User.programme == programme)
    if batch:
        query = query.filter(User.batch == batch)

    histories = defaultdict(list)
    for user_id, session, semester_no, gpa in query.all():
        histories[user_id].append((session, semester_no, float(gpa)))

    counts = Counter({label: 0 for label in TREND_LABELS})
    for semesters in histories.values():
        semesters.sort(key=lambda s: (s[0], s[1]))
        if len(semesters) < 2:
            counts[INSUFFICIENT_DATA] += 1
        else:
            counts[detect_trend([{"gpa": gpa} for _, _, gpa in semesters])] += 1

    return _present_counts(counts, min_group)


def _present_counts(counts, min_group):
    """
    Turns true per-label counts into what the admin page may show.
    Split out from get_trend_summary() so the suppression can be tested
    without a database.
    """
    total = sum(counts.values())
    result = {
        "min_group": min_group,
        "group_too_small": False,
        "total_students": total,
        "rows": [],
        "declining_display": None,
    }

    units = {label: counts[label] for label in TREND_LABELS if label not in DECLINING_LABELS}
    units[_DECLINING_UNIT] = sum(counts[label] for label in DECLINING_LABELS)
    hidden = _hidden_units(units, min_group) if total >= min_group else None

    if hidden is None:
        result.update(group_too_small=True, total_students=None)
        return result

    # The two declining rows are only broken out when the headline is
    # itself visible and neither part is a small non-zero count --
    # otherwise showing one part next to the headline would give away
    # the other.
    show_declining_parts = (
        _DECLINING_UNIT not in hidden
        and all(counts[l] == 0 or counts[l] >= min_group for l in DECLINING_LABELS)
    )

    def is_hidden(label):
        if label in DECLINING_LABELS:
            return not show_declining_parts
        return label in hidden

    visible_counts = [counts[l] for l in TREND_LABELS if not is_hidden(l)]
    largest = max(visible_counts + [1])

    for label in TREND_LABELS:
        n = counts[label]
        if is_hidden(label):
            # "<5" is only truthful for a genuinely small count; a
            # complementary-hidden cell can be large, so don't imply it.
            display = f"<{min_group}" if 0 < n < min_group and label not in DECLINING_LABELS else "Withheld"
            result["rows"].append({"label": label, "display": display, "bar_pct": 0})
        else:
            result["rows"].append({
                "label": label,
                "display": str(n),
                "bar_pct": round(n / largest * 100),
            })

    headline = units[_DECLINING_UNIT]
    if _DECLINING_UNIT not in hidden:
        result["declining_display"] = str(headline)
    elif 0 < headline < min_group:
        result["declining_display"] = f"<{min_group}"
    else:
        result["declining_display"] = "Withheld"

    return result
