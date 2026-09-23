"""
Runs the Gemini-backed skill/relevance classification for a student in
the background, instead of inside the request that triggers it.

Why: classifying a transcript's courses is the slowest thing the app
does -- measured 2026-09-23 at 39s and 65s for the two batches a
15-course transcript needs, and a full 8-semester transcript needs
about three times that. Doing it inside /save-transcript meant the
student sat on a spinner for a minute or more after pressing Save,
with the transcript already safely committed before that step even
started.

While a build is running, pages that would otherwise call
build_student_profile() themselves ask is_building() first and show a
"still preparing" state instead. That is what stops a student who goes
straight to Career/Dashboard from kicking off a SECOND, concurrent
classification of the very same courses (duplicate Gemini calls on a
quota that is already the app's tightest constraint).

Scope of the flag: in-memory, so it covers this process only. The app
runs one gunicorn worker (see Procfile), so that is the whole app
today; with several workers a build started in one wouldn't be visible
in another, and the worst case there is the old behaviour -- the page
classifies inline rather than waiting. Nothing is lost either way,
since every finished batch is cached in the database as it goes.
"""
import threading
import time
from concurrent.futures import ThreadPoolExecutor

from flask import current_app

from extensions import db
from models.course import Course
from models.course_skill_mapping import CourseSkillMapping
from models.programme_course_relevance import ProgrammeCourseRelevance
from models.semester import Semester
from models.transcript import Transcript
from models.users import User
from services.career_services import build_student_profile
from services.cgpa_services import GRADE_POINTS

# Bounded on purpose: this is background work competing for the same
# Gemini quota, so a burst of uploads should queue rather than fan out.
_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="classify")

_lock = threading.Lock()
_in_progress = set()

# When each user was last auto-started by ensure_profile_build(). Without
# this, a course Gemini legitimately returns no concepts for would look
# "unclassified" forever, and every page view would start another job for
# it. One attempt per user per window, at most.
_last_auto_start = {}
AUTO_RETRY_COOLDOWN = 10 * 60   # seconds

# Users seen fully classified recently, so the common case costs no
# queries at all. ensure_profile_build() runs on every Dashboard view
# and on /api/chat/suggestions, which the chat widget fires on EVERY
# page load -- without this, each page would pay for the lookup below
# just to be told again that there is nothing to do.
_known_clean = {}
CLEAN_CACHE_TTL = 5 * 60   # seconds


def is_building(user_id):
    """True while this user's profile is being classified in the background."""
    with _lock:
        return user_id in _in_progress


def needs_classification(user_id):
    """
    True if this student has gradeable courses that still have no cached
    classification -- i.e. a page asking for their profile right now
    would have to call Gemini inline and block on it.

    Mirrors build_student_profile()'s own filter (a real grade and
    credit hours), so a course it would skip anyway never counts as
    "missing" -- otherwise this would report work that can never be
    done and retrigger forever.
    """
    codes = {
        code for (code,) in
        db.session.query(Course.course_code)
        .join(Semester, Course.semester_id == Semester.semester_id)
        .join(Transcript, Semester.transcript_id == Transcript.transcript_id)
        .filter(Transcript.user_id == user_id)
        .filter(Course.grade.in_(list(GRADE_POINTS)))
        .filter(Course.credit_hour > 0)
        .distinct()
    }
    if not codes:
        return False

    classified = {
        code for (code,) in
        db.session.query(CourseSkillMapping.course_code)
        .filter(CourseSkillMapping.course_code.in_(codes)).distinct()
    }
    if codes - classified:
        return True

    user = db.session.get(User, user_id)
    if user is None:
        return False

    rated = {
        code for (code,) in
        db.session.query(ProgrammeCourseRelevance.course_code)
        .filter(ProgrammeCourseRelevance.course_code.in_(codes))
        .filter(ProgrammeCourseRelevance.programme == user.programme)
        .distinct()
    }
    return bool(codes - rated)


def ensure_profile_build(user_id):
    """
    Returns True if this student's classification is in progress -- so
    the caller should show "preparing" rather than compute inline.

    Starting it here is what makes the whole thing self-healing. The
    upload's own background job (start_profile_build) covers the normal
    case, but it can't cover a student whose transcript predates this
    feature, whose job failed on a Gemini outage, or whose job was cut
    short when the process restarted (a deploy, or the free tier going
    to sleep) -- the in-memory flag dies with the process while the
    unclassified courses remain. Without this, the next page view for
    any of those students silently falls back to classifying inline and
    blocks on Gemini for as long as that takes.
    """
    if is_building(user_id):
        return True

    now = time.time()
    with _lock:
        clean_at = _known_clean.get(user_id, 0)
    if now - clean_at < CLEAN_CACHE_TTL:
        return False

    # Checked BEFORE the cooldown below, so a student whose job has just
    # finished is recorded as clean right away rather than re-queried on
    # every page view until the cooldown expires.
    try:
        if not needs_classification(user_id):
            with _lock:
                _known_clean[user_id] = now
            return False
    except Exception:
        current_app.logger.exception(
            "Could not check classification state for user %s", user_id
        )
        return False

    with _lock:
        last = _last_auto_start.get(user_id, 0)
    if now - last < AUTO_RETRY_COOLDOWN:
        # Work is still outstanding, but we started a job for this
        # student recently and it didn't clear it -- don't spin on every
        # page view. Falls through to the inline path (the old
        # behaviour), and tries again after the cooldown.
        return False

    with _lock:
        _last_auto_start[user_id] = now

    current_app.logger.info(
        "User %s has unclassified courses and no job running -- starting one "
        "in the background instead of classifying inline", user_id
    )
    return start_profile_build(user_id)


def start_profile_build(user_id):
    """
    Kicks off build_student_profile(user_id) in the background and
    returns immediately. Returns False if a build for this user is
    already running (so a re-upload doesn't start a second one).

    Takes a plain user_id, never an ORM object: the request's session
    is torn down as soon as it returns, and touching an object bound to
    it from another thread is exactly what crashed production on
    2026-09-22 (sqlalchemy IllegalStateChangeError).
    """
    app = current_app._get_current_object()

    with _lock:
        if user_id in _in_progress:
            return False
        _in_progress.add(user_id)
        # A new upload brings new courses, so any earlier "fully
        # classified" answer for this student is stale.
        _known_clean.pop(user_id, None)

    def _run():
        try:
            with app.app_context():
                build_student_profile(user_id)
        except Exception:
            app.logger.exception(
                "Background skill classification failed for user %s -- a later "
                "page view will start a fresh attempt (see ensure_profile_build)",
                user_id
            )
        finally:
            with _lock:
                _in_progress.discard(user_id)
                # Re-checked from the database next time rather than
                # assumed done: the run above may have failed, or only
                # got partway before the quota ran out.
                _known_clean.pop(user_id, None)

    _executor.submit(_run)
    return True
