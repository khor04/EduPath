from collections import Counter

from sqlalchemy.orm import joinedload

from extensions import db
from models.users import User
from models.transcript import Transcript
from models.contact import ContactMessage
from models.career_recommendation import CareerRecommendation
from models.feedback import Feedback
from models.target_cgpa import TargetCGPA


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
