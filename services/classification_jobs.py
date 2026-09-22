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
from concurrent.futures import ThreadPoolExecutor

from flask import current_app

from services.career_services import build_student_profile

# Bounded on purpose: this is background work competing for the same
# Gemini quota, so a burst of uploads should queue rather than fan out.
_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="classify")

_lock = threading.Lock()
_in_progress = set()


def is_building(user_id):
    """True while this user's profile is being classified in the background."""
    with _lock:
        return user_id in _in_progress


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

    def _run():
        try:
            with app.app_context():
                build_student_profile(user_id)
        except Exception:
            app.logger.exception(
                "Background skill classification failed for user %s -- the next "
                "Dashboard/Career visit will retry it inline", user_id
            )
        finally:
            with _lock:
                _in_progress.discard(user_id)

    _executor.submit(_run)
    return True
