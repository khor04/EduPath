"""
Programme-name helpers shared by transcript upload (does the transcript's programme match
the one the student registered with?) and career recommendation (which UM programme's
career list applies to this student?). Moved out of routes/transcript.py so services can
use them without importing a route module.
"""
import re


def normalize_programme(programme):
    if not programme:
        return ""

    programme = programme.upper().strip()

    programme = programme.replace("&", "AND")

    # Drop punctuation (commas, parentheses, hyphens, periods, ...)
    # but keep the words themselves — a programme's parenthetical
    # specialization (e.g. "(INFORMATION SYSTEMS)") is often the
    # ONLY thing that distinguishes it from a sibling programme in
    # the same faculty, so we must never discard that text.
    programme = re.sub(r"[^A-Z0-9\s]", " ", programme)

    programme = re.sub(r"\s+", " ", programme).strip()

    return programme


def programme_word_set(programme):
    """
    Order-independent, singularized word set for a programme name.

    Used to tolerate cosmetic differences between the programme
    name a student picks at registration (from a fixed, official
    list) and however it happens to be printed on their PDF
    transcript — case, punctuation, "&" vs "and", and singular vs
    plural nouns (e.g. "SYSTEM" vs "SYSTEMS") — without loosening
    the comparison enough to treat two genuinely different
    programmes/specializations as the same.
    """

    def singularize(word):
        if len(word) > 3 and word.endswith("S") and not word.endswith("SS"):
            return word[:-1]
        return word

    words = normalize_programme(programme).split()

    return {singularize(word) for word in words}


def programmes_match(transcript_programme, registered_programme):
    if not transcript_programme or not registered_programme:
        return False

    if (
        normalize_programme(transcript_programme)
        == normalize_programme(registered_programme)
    ):
        return True

    return (
        programme_word_set(transcript_programme)
        == programme_word_set(registered_programme)
    )
