"""
Read-only data check for the course-statistics feature (see
services/course_stats_services.py): how much real data is there, how many
courses clear each anonymity floor, and does anything in the data threaten the
"first attempt" rule?

Two pools are reported throughout, because the two views count different people:

  STUDENT pool -- students who opted into benchmark_consent. This is what other
      students see (Peer Benchmarking page, floor MIN_PEERS).
  STAFF pool   -- every non-admin student with an uploaded transcript, whatever
      their sharing choice. This is what Course Difficulty and Performance
      Trends count (floor MIN_COURSE_GROUP).

Admin accounts are in neither pool.

Prints AGGREGATES ONLY -- counts, histograms, and distinct code/grade/session
values. No user ids, names, emails, or per-student rows.

Read-only by construction: on Postgres the transaction is switched to READ ONLY
before any query, so the server itself rejects a write, and it is rolled back at
the end rather than committed. It also builds the Flask app by hand instead of
calling create_app(), so db.create_all() never runs.

Usage:
    python scripts/course_stats_data_check.py
"""
import os
import re
import sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Flask
from sqlalchemy import text

from config import Config
from extensions import db

app = Flask(__name__)
app.config.from_object(Config)
db.init_app(app)

# Registers every model so relationships resolve, exactly as app.py does.
import models.career_recommendation, models.contact, models.course  # noqa: E401,F401
import models.course_skill_mapping, models.feedback, models.onet_occupation  # noqa: E401,F401
import models.onet_occupation_concept, models.programme_course_relevance  # noqa: E401,F401
import models.report_share, models.semester, models.skill_profile  # noqa: E401,F401
import models.target_cgpa, models.tracked_course, models.transcript, models.users  # noqa: E401,F401

import services.course_stats_services as course_stats
from models.course import Course
from models.semester import Semester
from models.transcript import Transcript
from models.users import User
from services.admin_services import MIN_COURSE_GROUP
from services.benchmark_services import MIN_PEERS
from services.cgpa_services import GRADE_POINTS

BUCKETS = [(1, 1), (2, 2), (3, 3), (4, 4), (5, 5), (6, 9), (10, 19), (20, None)]


def bucket_label(lo, hi):
    return f"{lo}+" if hi is None else (str(lo) if lo == hi else f"{lo}-{hi}")


def histogram(sizes):
    return {
        bucket_label(lo, hi): sum(1 for s in sizes if s >= lo and (hi is None or s <= hi))
        for lo, hi in BUCKETS
    }


def section(title):
    print(f"\n=== {title} ===")


def quality_report(rows, label):
    """
    Data-quality checks over one pool's course rows. `rows` are tuples of
    (user_id, programme, course_code, course_name, grade, session, semester_no).
    Reports counts only; the flagged VALUES (a bad grade, a malformed session)
    are course/transcript metadata, not anything student-identifying.
    """
    print(f"\n  -- {label} ({len(rows)} course rows) --")
    if not rows:
        print("     nothing to check")
        return

    raw_codes = {r[2] for r in rows}
    norm_codes = {r[2].strip().upper() for r in rows}
    print(f"     distinct course codes raw: {len(raw_codes)}  after trim+upper: {len(norm_codes)}"
          + ("   <-- codes differ only by case/spacing" if len(raw_codes) != len(norm_codes) else ""))

    names = defaultdict(set)
    for r in rows:
        names[r[2].strip().upper()].add((r[3] or "").strip())
    multi_name = sorted(c for c, n in names.items() if len(n) > 1)
    print(f"     course codes with more than one distinct course name: {len(multi_name)}"
          + (f"   e.g. {multi_name[:5]}" if multi_name else ""))

    bad_grades = Counter((r[4] or "").strip().upper() for r in rows
                         if (r[4] or "").strip().upper() not in GRADE_POINTS)
    print(f"     rows with a grade not in GRADE_POINTS: {sum(bad_grades.values())}   {dict(bad_grades)}")

    bad_sessions = Counter(r[5] for r in rows if not re.fullmatch(r"\d{4}/\d{4}", r[5] or ""))
    print(f"     rows with a session not in YYYY/YYYY form: {sum(bad_sessions.values())}   {dict(bad_sessions)}")
    print(f"     semester_no values: {dict(sorted(Counter(r[6] for r in rows).items()))}")

    # The first-attempt rule orders a student's attempts by (session,
    # semester_no). A tie there would make "first" ambiguous.
    attempts = defaultdict(list)
    for user_id, _programme, code, _name, _grade, session, semester_no in rows:
        attempts[(user_id, code.strip().upper())].append((session, semester_no))
    multi = [a for a in attempts.values() if len(a) > 1]
    tied = [a for a in multi if len(set(a)) < len(a)]
    print(f"     student-course pairs: {len(attempts)}   with 2+ attempts (retakes): {len(multi)}"
          f"   with a tie on (session, semester_no): {len(tied)}"
          + ("   <-- FIRST ATTEMPT AMBIGUOUS" if tied else ""))


with app.app_context():
    # Must be the first statement of the transaction. Postgres-only syntax --
    # skipped on SQLite, which is only ever used to exercise this script.
    if db.engine.dialect.name == "postgresql":
        db.session.execute(text("SET TRANSACTION READ ONLY"))

    print(f"engine: {db.engine.url.get_backend_name()}   "
          f"student floor (MIN_PEERS) = {MIN_PEERS}   staff floor (MIN_COURSE_GROUP) = {MIN_COURSE_GROUP}")

    # ------------------------------------------------------------
    section("1. Students and consent")
    by_role = Counter(
        ("admin" if is_admin else "student",
         {True: "consented", False: "declined", None: "undecided"}[c])
        for c, is_admin in db.session.query(User.benchmark_consent, User.is_admin).all()
    )
    print(f"total users: {sum(by_role.values())}")
    print(f"by (role, sharing choice): {dict(by_role)}")

    base = (
        db.session.query(
            User.user_id, User.programme, Course.course_code, Course.course_name,
            Course.grade, Semester.academic_session, Semester.semester_no,
        )
        .join(Transcript, Transcript.user_id == User.user_id)
        .join(Semester, Semester.transcript_id == Transcript.transcript_id)
        .join(Course, Course.semester_id == Semester.semester_id)
        .filter(User.is_admin == False)
    )
    staff_rows = base.all()
    student_rows = base.filter(User.benchmark_consent == True).all()

    def per_programme(rows):
        seen, counts = set(), Counter()
        for user_id, programme, *_ in rows:
            if user_id not in seen:
                seen.add(user_id)
                counts[programme] += 1
        return counts

    staff_students = per_programme(staff_rows)
    student_students = per_programme(student_rows)
    print(f"STAFF pool   (all non-admin, with a transcript): {sum(staff_students.values())} students, "
          f"{len(staff_rows)} course rows")
    print(f"  per programme: {dict(staff_students.most_common())}")
    print(f"STUDENT pool (consenting only):                 {sum(student_students.values())} students, "
          f"{len(student_rows)} course rows")
    print(f"  per programme: {dict(student_students.most_common())}")

    # ------------------------------------------------------------
    section("2. Courses vs the anonymity floors (pooled across programmes)")
    # Ask for every course (floor 1) so courses below the real floors stay
    # visible, then apply each floor here.
    #
    # The STUDENT numbers are an upper bound: this counts the whole consenting
    # pool, while a real viewer is also excluded from their own view, so a
    # course they took shows one fewer student to them than it does here.
    student_courses = course_stats.compute_course_stats(min_students=1)
    staff_courses = course_stats.compute_course_stats(min_students=1, consenting_only=False)

    for label, courses, floor in (
        ("STUDENT (Peer Benchmarking)", student_courses, MIN_PEERS),
        ("STAFF (Course Difficulty)", staff_courses, MIN_COURSE_GROUP),
    ):
        sizes = [c["sample_size"] for c in courses]
        meeting = sum(1 for s in sizes if s >= floor)
        print(f"\n  {label}, floor {floor}")
        print(f"     courses with any first attempt: {len(sizes)}")
        print(f"       shown (n >= {floor}): {meeting}      hidden: {len(sizes) - meeting}")
        print(f"     students-per-course distribution: {histogram(sizes)}")
        print("     would still show at a higher floor: "
              + ", ".join(f"n>={n}: {sum(1 for s in sizes if s >= n)}" for n in (3, 5, 10, 20)))

    # ------------------------------------------------------------
    section("3. (Programme, course) pairs -- what a programme-filtered table would show")
    for label, programmes, floor, consenting_only in (
        ("STUDENT", student_students, MIN_PEERS, True),
        ("STAFF", staff_students, MIN_COURSE_GROUP, False),
    ):
        pair_sizes = [
            c["sample_size"]
            for p in programmes
            for c in course_stats.compute_course_stats(
                programme=p, min_students=1, consenting_only=consenting_only)
        ]
        meeting = sum(1 for s in pair_sizes if s >= floor)
        print(f"  {label:8s} pairs with any first attempt: {len(pair_sizes):4d}   "
              f"shown (n >= {floor}): {meeting}")
        print(f"           distribution: {histogram(pair_sizes)}")

    # ------------------------------------------------------------
    section("4. Data quality")
    print("  Checked on BOTH pools: a problem in a non-consenting student's transcript")
    print("  still affects the staff pages, so the staff pool is the one that matters most.")
    quality_report(staff_rows, "STAFF pool (all non-admin students)")
    quality_report(student_rows, "STUDENT pool (consenting only)")

    db.session.rollback()
    print("\nDone. Nothing was written (transaction rolled back).")
