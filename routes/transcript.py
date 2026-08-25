from flask import Blueprint, render_template, request, jsonify,url_for, flash
from flask_login import login_required, current_user
import fitz
import re
import os
import uuid
from extensions import db
from models.transcript import Transcript
from models.semester import Semester
from models.course import Course
from models.target_cgpa import TargetCGPA
from datetime import datetime
from zoneinfo import ZoneInfo


transcript_bp = Blueprint("transcript", __name__)


UPLOAD_FOLDER = "uploads"
ALLOWED_EXTENSIONS = {"pdf"}

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


@transcript_bp.route("/upload")
@login_required
def upload():

    transcripts = (
        Transcript.query
        .filter_by(user_id=current_user.user_id)
        .order_by(Transcript.uploaded_at.desc())
        .all()
    )

    upload_history = []

    has_transcript = Transcript.query.filter_by(
        user_id=current_user.user_id
    ).first() is not None

    for transcript in transcripts:
        semesters = Semester.query.filter_by(
            transcript_id=transcript.transcript_id
        ).all()


        upload_history.append({
            "uploaded_at": transcript.uploaded_at.strftime("%d %b %Y, %H:%M"),
            "status": transcript.status,
            "uploaded_type": transcript.uploaded_type,
            "summary": transcript.summary,
        })

    return render_template(
        "upload.html",
        active_page="upload",
        upload_history=upload_history,
        has_transcript=has_transcript
    )

def get_or_create_semester(transcript_id, sem_no, session):
    semester = Semester.query.filter_by(
        transcript_id=transcript_id,
        semester_no=sem_no,
        academic_session=session
    ).first()

    return semester


def compute_semester_gpa(courses):
    """
    Recompute a semester's GPA from its own courses (credit-hour
    weighted), instead of trusting whatever GPA figure happens to
    be printed on the most recently uploaded PDF for that
    semester.

    This matters for appeals/re-uploads: a re-issued transcript
    may only list a subset of a semester's courses (e.g. a single
    retaken course), and its own printed GPA can reflect just that
    subset rather than the semester as a whole. Deriving the GPA
    from the full, current set of Course rows keeps it internally
    consistent with what is actually stored, regardless of how
    partial any single upload was.

    `courses` may be a mix of Course ORM objects (attributes
    `credit_hour` / `grade_point`) and freshly-uploaded course
    dicts (keys "credits" / "grade_point", string values).
    """

    total_credits = 0.0
    total_points = 0.0

    for course in courses:

        if isinstance(course, dict):
            credit = float(course.get("credits") or 0)
            points = float(course.get("grade_point") or 0)
        else:
            credit = float(course.credit_hour or 0)
            points = float(course.grade_point or 0)

        total_credits += credit
        total_points += points

    if total_credits <= 0:
        return 0.0

    return round(total_points / total_credits, 2)

import re


def extract_programme_from_transcript(all_words):
    """
    Locate the "Programme" label by its word coordinates and
    reconstruct the value from whatever text sits on the same
    visual row (same y, to the right of the label).

    This is coordinate-based rather than a plain text/regex search
    over the linear extracted text on purpose: some transcript
    PDFs (e.g. ones that had a field value edited/overlaid) place
    the value's text in a different position in the PDF's internal
    content stream than the label, even though it still renders in
    the correct spot visually. A linear "Programme\\s*:\\s*(.+)"
    search misses that value entirely; reading by row position
    does not.
    """

    label_word = None

    for word in all_words:

        if word["text"].strip().rstrip(":").upper() == "PROGRAMME":
            label_word = word
            break

    if label_word is None:
        return None

    label_page = label_word["page"]
    label_y = label_word["y0"]

    # Same row spacing assumption used for the course table
    # (~12pt between fields/rows); 5pt safely covers the small
    # (~1-2pt) drift seen between a label and an overlaid value
    # without reaching the next field's row.
    Y_TOLERANCE = 5

    row_words = [
        word
        for word in all_words
        if word["page"] == label_page
        and word is not label_word
        and abs(word["y0"] - label_y) <= Y_TOLERANCE
        and word["x0"] > label_word["x1"]
    ]

    if not row_words:
        return None

    row_words.sort(key=lambda word: word["x0"])

    value = " ".join(word["text"] for word in row_words)
    value = value.strip().lstrip(":").strip()
    value = re.sub(r"\s+", " ", value)

    return value or None


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

@transcript_bp.route("/upload-transcript", methods=["POST"])
@login_required
def upload_transcript():

    if "pdf" not in request.files:
        return jsonify({
            "success": False,
            "message": "No file uploaded."
        })

    file = request.files["pdf"]

    if file.filename == "":
        return jsonify({
            "success": False,
            "message": "Please select a PDF file."
        })

    if not allowed_file(file.filename):
        return jsonify({
            "success": False,
            "message": "Only PDF files are supported."
        })

    os.makedirs(UPLOAD_FOLDER, exist_ok=True)

    filename = f"{uuid.uuid4()}.pdf"
    filepath = os.path.join(UPLOAD_FOLDER, filename)

    file.save(filepath)

    try:

        # ==================================================
        # EXTRACT TEXT USING PYMUPDF
        # ==================================================

        all_words = []
        page_texts = []

        with fitz.open(filepath) as doc:

            for page_no, page in enumerate(doc):

                # Normal text extraction
                page_texts.append(
                    page.get_text("text")
                )

                # Word-level extraction
                words = page.get_text("words")

                for word in words:

                    x0, y0, x1, y1, word_text, block, line, word_no = word

                    all_words.append({
                        "page": page_no,
                        "x0": x0,
                        "y0": y0,
                        "x1": x1,
                        "y1": y1,
                        "text": word_text,
                        "block": block,
                        "line": line,
                        "word_no": word_no
                    })

        # ==================================================
        # BUILD FULL TEXT
        # ==================================================

        full_text = "\n".join(page_texts)

        # Fallback using words if normal text is empty
        if len(full_text.strip()) < 20:

            full_text = " ".join(
                word["text"]
                for word in all_words
            )

        # ==================================================
        # BASIC TEXT VALIDATION
        # ==================================================

        if len(full_text.strip()) < 20:
            return jsonify({
                "success": False,
                "message": (
                    "Unable to read this PDF. Please upload a "
                    "text-based (not scanned/image) transcript PDF."
                )
            })

        text_upper = full_text.upper()

        # ==================================================
        # VERIFY UM TRANSCRIPT
        # ==================================================

        has_exam_result = (
            "EXAMINATION RESULT" in text_upper
        )

        has_exam_centre = (
            "EXAMINATION AND GRADUATION CENTRE"
            in text_upper
        )

        if not (has_exam_result and has_exam_centre):
            return jsonify({
                "success": False,
                "message": "Invalid Universiti Malaya transcript."
            })

        # ==================================================
        # EXTRACT PROGRAMME
        # ==================================================

        transcript_programme = (
            extract_programme_from_transcript(all_words)
        )

        if not transcript_programme:
            return jsonify({
                "success": False,
                "message": "Unable to identify programme from transcript."
            })

        # ==================================================
        # COMPARE PROGRAMME
        # ==================================================

        registered_programme = current_user.programme

        print("\n========== PROGRAMME DEBUG ==========")
        print(
            "Transcript programme:",
            repr(transcript_programme)
        )
        print(
            "Registered programme:",
            repr(registered_programme)
        )

        print(
            "Normalized transcript:",
            repr(normalize_programme(transcript_programme))
        )

        print(
            "Normalized registered:",
            repr(normalize_programme(registered_programme))
        )

        print("=====================================\n")

        if not programmes_match(
            transcript_programme,
            registered_programme
        ):

            return jsonify({
                "success": False,
                "message": (
                    f"Programme Mismatch:\n\n"
                    f"Your account is registered under "
                    f"'{registered_programme}', "
                    f"but the uploaded transcript belongs to "
                    f"'{transcript_programme}'."
                )
            })

        # ==================================================
        # EXTRACT SEMESTER + COURSE DATA
        # ==================================================

        semesters = extract_transcript_data(all_words)

        if not semesters:
            return jsonify({
                "success": False,
                "message": (
                    "Unable to extract semester results from "
                    "this transcript."
                )
            })

        # ==================================================
        # DEBUG
        # ==================================================

        print("\n========== EXTRACTED SEMESTERS ==========")

        for semester in semesters:

            print(
                f"\n{semester['semester']}"
            )

            print(
                "GPA:",
                semester["gpa"],
                "| CGPA:",
                semester["cgpa"]
            )

            for course in semester["courses"]:

                print(
                    course["course_code"],
                    "|",
                    course["course_name"],
                    "|",
                    course["credits"],
                    "|",
                    course["grade"],
                    "|",
                    course["grade_point"]
                )

        print("=========================================\n")

        # ==================================================
        # SUCCESS
        # ==================================================

        return jsonify({
            "success": True,
            "message": "Transcript extracted successfully.",
            "semesters": semesters
        })

    except Exception as e:

        print("Transcript extraction error:")
        print(type(e).__name__, ":", e)

        return jsonify({
            "success": False,
            "message": (
                "An error occurred while processing the transcript."
            )
        })

    finally:

        try:

            if os.path.exists(filepath):
                os.remove(filepath)

        except Exception as e:

            print(
                f"Failed to delete temporary file: {e}"
            )


def extract_transcript_data(all_words):
    
    semesters = []

    # ==========================================================
    # GROUP WORDS BY PAGE
    # ==========================================================

    pages = {}

    for word in all_words:
        page_no = word["page"]

        if page_no not in pages:
            pages[page_no] = []

        pages[page_no].append(word)

    # ==========================================================
    # HELPER FUNCTIONS
    # ==========================================================

    def is_course_code(text):
        """
        Example:
        GQS0046
        WIA3002
        GBX0009
        """

        return bool(
            re.fullmatch(
                r"[A-Z]{2,}\d{4}",
                text.strip()
            )
        )

    def is_grade(text):
        return text.strip().upper() in {
            "A+",
            "A",
            "A-",
            "B+",
            "B",
            "B-",
            "C+",
            "C",
            "C-",
            "D+",
            "D",
            "F"
        }

    def is_grade_point(text):
        return bool(
            re.fullmatch(
                r"\d+\.\d{2}",
                text.strip()
            )
        )

    def is_credit(text):
        return bool(
            re.fullmatch(
                r"\d+",
                text.strip()
            )
        )

    def is_semester_header(text):
        return bool(
            re.search(
                r"Examination\s+Result\s+for\s+Semester\s+\d+,\s+Session\s+\d{4}/\d{4}",
                text,
                re.I
            )
        )

    # ==========================================================
    # BUILD ROWS BASED ON Y POSITION
    #
    # We use a tolerance because GQS0046 has:
    #
    # y=787.5
    # y=792.3
    # y=797.1
    #
    # These are still one course record.
    # ==========================================================

    page_rows = {}

    for page_no, words in pages.items():

        sorted_words = sorted(
            words,
            key=lambda w: (w["y0"], w["x0"])
        )

        rows = []

        Y_TOLERANCE = 3.5

        for word in sorted_words:

            if not rows:
                rows.append({
                    "y": word["y0"],
                    "words": [word]
                })
                continue

            current_row = rows[-1]

            if abs(
                word["y0"] - current_row["y"]
            ) <= Y_TOLERANCE:

                current_row["words"].append(word)

            else:

                rows.append({
                    "y": word["y0"],
                    "words": [word]
                })

        # Sort each row from left to right
        for row in rows:
            row["words"].sort(
                key=lambda w: w["x0"]
            )

        page_rows[page_no] = rows

    # ==========================================================
    # PROCESS EACH PAGE
    # ==========================================================

    current_semester = None

    for page_no in sorted(page_rows.keys()):

        rows = page_rows[page_no]

        for row in rows:

            words = row["words"]

            if not words:
                continue

            row_text = " ".join(
                w["text"] for w in words
            ).strip()

            # ==================================================
            # CHECK FOR SEMESTER HEADER
            # ==================================================

            semester_match = re.search(
                r"Examination\s+Result\s+for\s+Semester\s+(\d+),\s+Session\s+(\d{4}/\d{4})",
                row_text,
                re.I
            )

            if semester_match:

                semester_no = int(
                    semester_match.group(1)
                )

                academic_session = semester_match.group(2)

                current_semester = {
                    "semester": row_text,
                    "semester_no": semester_no,
                    "academic_session": academic_session,
                    "gpa": "",
                    "cgpa": "",
                    "courses": []
                }

                semesters.append(current_semester)

                continue

            # ==================================================
            # IF NO SEMESTER YET, IGNORE
            # ==================================================

            if current_semester is None:
                continue

            # ==================================================
            # IGNORE NOTES / FOOTER
            # ==================================================

            if re.match(
                r"^(Notes|Important Reminder|Director|Academic Services Department|Universiti Malaya|This is a computer-generated document)",
                row_text,
                re.I
            ):
                continue

            # ==================================================
            # GPA
            # ==================================================

            gpa_match = re.search(
                r"\bGPA\s*:\s*([\d.]+)",
                row_text,
                re.I
            )

            if gpa_match:

                current_semester["gpa"] = (
                    gpa_match.group(1)
                )

                continue

            # ==================================================
            # CGPA
            # ==================================================

            cgpa_match = re.search(
                r"\bCGPA\s*:\s*([\d.]+)",
                row_text,
                re.I
            )

            if cgpa_match:

                current_semester["cgpa"] = (
                    cgpa_match.group(1)
                )

                continue

            # ==================================================
            # FIND COURSE CODE
            # ==================================================

            course_code_word = None
            course_code_index = None

            for index, word in enumerate(words):

                if is_course_code(word["text"]):

                    course_code_word = word
                    course_code_index = index

                    break

            if course_code_word is None:
                continue

            course_code = (
                course_code_word["text"].strip()
            )

            # ==================================================
            # FIND CREDIT / GRADE / GRADE POINT
            #
            # We DON'T depend on them being on the same Y.
            #
            # Instead, use their X positions.
            # ==================================================

            credits = None
            grade = None
            grade_point = None

            for word in words:

                text = word["text"].strip()

                x = word["x0"]

                # Credits column
                if 400 <= x <= 445:

                    if is_credit(text):

                        credits = text

                # Grade column
                elif 445 <= x < 490:

                    if is_grade(text):

                        grade = text

                # Grade point column
                elif x >= 490:

                    if is_grade_point(text):

                        grade_point = text

            # ==================================================
            # IF THIS ROW DOES NOT CONTAIN THE MARKS,
            # THEY MAY BE ON A SEPARATE Y LINE.
            #
            # This happens with GQS0046.
            #
            # We search nearby rows on the SAME PAGE.
            # ==================================================

            if (
                credits is None
                or grade is None
                or grade_point is None
            ):

                course_y = course_code_word["y0"]

                # Search nearby rows
                nearby_words = []

                for other_row in rows:

                    other_y = other_row["y"]

                    if (
                        other_y >= course_y - 1
                        and other_y <= course_y + 15
                    ):

                        nearby_words.extend(
                            other_row["words"]
                        )

                # Search marks again
                for word in nearby_words:

                    text = word["text"].strip()
                    x = word["x0"]

                    if credits is None:

                        if (
                            400 <= x <= 445
                            and is_credit(text)
                        ):
                            credits = text

                    if grade is None:

                        if (
                            445 <= x < 490
                            and is_grade(text)
                        ):
                            grade = text

                    if grade_point is None:

                        if (
                            x >= 490
                            and is_grade_point(text)
                        ):
                            grade_point = text

            # ==================================================
            # IF WE STILL DON'T HAVE COMPLETE COURSE DATA,
            # DON'T DROP THE COURSE — the student would have no
            # way to know it's missing. Keep it with blank
            # field(s) and flag it so the verification table can
            # highlight it for the student to fill in by hand.
            # ==================================================

            course_needs_review = (
                credits is None
                or grade is None
                or grade_point is None
            )

            if course_needs_review:
                print(
                    "Could not extract complete course:",
                    course_code,
                    row_text
                )

                if credits is None:
                    credits = ""

                if grade is None:
                    grade = ""

                if grade_point is None:
                    grade_point = ""

            # ==================================================
            # EXTRACT COURSE NAME
            #
            # IMPORTANT:
            #
            # We use X coordinates instead of line structure.
            #
            # Course name is approximately:
            #
            # x >= 130
            # x < 400
            #
            # This means:
            #
            # GQS0046 INTRODUCTION TO SCIENCE AND
            #         TECHNOLOGY POLICY AND
            #         MANAGEMENT
            #
            # will become:
            #
            # INTRODUCTION TO SCIENCE AND TECHNOLOGY
            # POLICY AND MANAGEMENT
            # ==================================================

            name_words = []

            # Search rows belonging to this course
            course_y = course_code_word["y0"]

            for other_row in rows:

                other_y = other_row["y"]

                # Some transcript layouts wrap a long course name
                # onto two lines that straddle the code/credit/
                # grade line (one line above it, one below), not
                # just below it. A 7pt look-back catches that
                # wrap line without reaching the previous course's
                # row (rows are normally ~12pt apart).
                if other_y < course_y - 7:
                    continue

                if other_y > course_y + 16:
                    break

                # A wrapped name continuation row never starts
                # a new course code. If it does, this row
                # belongs to a DIFFERENT course — skip it (if
                # before this course) or stop entirely (if after,
                # since rows are sorted and nothing further is ours).
                #
                # We compare by row identity, not by a y-distance
                # epsilon: the course's own row can legitimately
                # differ from course_code_word["y0"] by more than
                # a hair (the row's anchor "y" comes from whichever
                # word landed there first in sort order, e.g. a
                # grade/credit word on an inserted text block a
                # fraction of a point off from the code word), so
                # an epsilon check can misfire and wrongly treat a
                # course's own row as "a different course's row".
                if other_row is not row:

                    row_has_course_code = any(
                        is_course_code(w["text"].strip())
                        for w in other_row["words"]
                    )

                    if row_has_course_code:
                        if other_y < course_y:
                            continue
                        break

                for word in other_row["words"]:

                    x = word["x0"]

                    # Course name column
                    if 125 <= x < 400:

                        text = word["text"].strip()

                        # Don't accidentally include
                        # GPA / CGPA / other table text
                        if text:

                            name_words.append(
                                word
                            )

            # ==================================================
            # SORT NAME WORDS BY Y THEN X
            # ==================================================

            name_words.sort(
                key=lambda w: (
                    w["y0"],
                    w["x0"]
                )
            )

            course_name = " ".join(
                word["text"]
                for word in name_words
            )

            course_name = re.sub(
                r"\s+",
                " ",
                course_name
            ).strip()

            # ==================================================
            # REMOVE DUPLICATES
            # ==================================================

            if course_name:

                cleaned_words = []
                previous = None

                for word in course_name.split():

                    if word != previous:
                        cleaned_words.append(word)

                    previous = word

                course_name = " ".join(
                    cleaned_words
                )

            # ==================================================
            # ADD COURSE
            # ==================================================

            current_semester["courses"].append({

                "course_code": course_code,

                "course_name": course_name,

                "credits": credits,

                "grade": grade,

                "grade_point": grade_point,

                "needs_review": course_needs_review
            })

    # ==========================================================
    # DEBUG OUTPUT
    # ==========================================================

    print("\n" + "=" * 70)
    print("FINAL EXTRACTED TRANSCRIPT")
    print("=" * 70)

    for semester in semesters:

        print(
            f"\n{semester['semester']}"
        )

        print(
            f"GPA: {semester['gpa']} | "
            f"CGPA: {semester['cgpa']}"
        )

        for course in semester["courses"]:

            print(
                f"{course['course_code']} | "
                f"{course['course_name']} | "
                f"{course['credits']} | "
                f"{course['grade']} | "
                f"{course['grade_point']}"
            )

    print("=" * 70)

    return semesters

@transcript_bp.route("/save-transcript", methods=["POST"])
@login_required
def save_transcript():

    data = request.get_json()

    if not data or "semesters" not in data:
        return jsonify({
            "success": False,
            "message": "No transcript data received."
        })

    try:
        saved = []
        updated = []
        skipped = []

        # =====================================================
        # STEP 1: LOAD EXISTING DATA (NO DB WRITE YET)
        # =====================================================
        existing_semesters = (
            Semester.query
            .join(Transcript)
            .filter(Transcript.user_id == current_user.user_id)
            .all()
        )

        existing_map = {
            (s.semester_no, s.academic_session): s
            for s in existing_semesters
        }

        # =====================================================
        # STEP 2: DETECT CHANGES ONLY (NO DB WRITE)
        # =====================================================
        for sem in data["semesters"]:

            key = (sem["semester_no"], sem["academic_session"])

            uploaded_courses = {
                c["course_code"].strip().upper(): c
                for c in sem["courses"]
            }

            # -------------------------
            # NEW SEMESTER DETECTED
            # -------------------------
            if key not in existing_map:
                saved.append(
                    f"Sem {sem['semester_no']} {sem['academic_session']}"
                )
                continue

            # -------------------------
            # EXISTING SEMESTER
            # -------------------------
            semester = existing_map[key]

            existing_courses = Course.query.filter_by(
                semester_id=semester.semester_id
            ).all()

            existing_map_course = {
                c.course_code.strip().upper(): c
                for c in existing_courses
            }

            # -------------------------
            # DUPLICATE CHECK (check on course code, grade point and credit hour)
            # -------------------------
            is_exact_duplicate = True

            if len(existing_map_course) != len(uploaded_courses):
                is_exact_duplicate = False
            else:
                for code, c in uploaded_courses.items():

                    if code not in existing_map_course:
                        is_exact_duplicate = False
                        break

                    db_course = existing_map_course[code]

                    if (
                        str(db_course.grade).strip()
                        != str(c["grade"]).strip()
                        or float(db_course.grade_point or 0)
                        != float(c["grade_point"] or 0)
                    ):
                        is_exact_duplicate = False
                        break

            if is_exact_duplicate:
                skipped.append(
                    f"Sem {sem['semester_no']} {sem['academic_session']}"
                )
                continue

            updated.append(
                f"Sem {sem['semester_no']} {sem['academic_session']}"
            )

        # =====================================================
        # STEP 3: HANDLE DUPLICATE ONLY CASE (NO DB WRITE)
        # =====================================================
        if not saved and not updated:
            return jsonify({
                "success": True,
                "status": "DUPLICATE",
                "message": "No changes detected. Nothing was saved.",
                "saved": [],
                "updated": [],
                "skipped": skipped
            })

        # =====================================================
        # STEP 4: CREATE TRANSCRIPT LOG (ONLY IF CHANGES EXIST)
        # =====================================================
        transcript = Transcript(
            user_id=current_user.user_id,
            status="verified",
            uploaded_at=datetime.now(ZoneInfo("Asia/Kuala_Lumpur"))
        )

        db.session.add(transcript)
        db.session.flush()

        # =====================================================
        # STEP 5: SAVE DATA FOR REAL
        # =====================================================
        for sem in data["semesters"]:

            key = (sem["semester_no"], sem["academic_session"])

            uploaded_courses = {
                c["course_code"].strip().upper(): c
                for c in sem["courses"]
            }

            if key not in existing_map:

                semester = Semester(
                    transcript_id=transcript.transcript_id,
                    semester_no=sem["semester_no"],
                    academic_session=sem["academic_session"],
                    semester_gpa=compute_semester_gpa(sem["courses"]),
                   is_revised=False
                )

                db.session.add(semester)
                db.session.flush()

                for c in sem["courses"]:
                    db.session.add(Course(
                        semester_id=semester.semester_id,
                        course_code=c["course_code"],
                        course_name=c["course_name"],
                        credit_hour=float(c["credits"] or 0),
                        grade=c["grade"],
                        grade_point=float(c["grade_point"] or 0)
                    ))

                continue

            # -------------------------
            # APPEAL UPDATE
            # -------------------------
            semester = existing_map[key]
            semester.is_revised = True

            existing_courses = Course.query.filter_by(
                semester_id=semester.semester_id
            ).all()

            existing_map_course = {
                c.course_code.strip().upper(): c
                for c in existing_courses
            }

            newly_inserted_courses = []

            for code, c in uploaded_courses.items():

                if code in existing_map_course:

                    db_course = existing_map_course[code]
                    db_course.course_name = c["course_name"]
                    db_course.grade = c["grade"]
                    db_course.grade_point = float(c["grade_point"] or 0)

                else:

                    new_course = Course(
                        semester_id=semester.semester_id,
                        course_code=c["course_code"],
                        course_name=c["course_name"],
                        credit_hour=float(c["credits"] or 0),
                        grade=c["grade"],
                        grade_point=float(c["grade_point"] or 0)
                    )

                    db.session.add(new_course)
                    newly_inserted_courses.append(new_course)

            # existing_courses already reflects the in-place
            # updates above (same ORM objects, mutated) — combined
            # with newly_inserted_courses this is the FULL,
            # current set of courses for the semester, so the GPA
            # derived from it stays consistent even if this
            # upload only re-listed a subset of the semester.
            semester.semester_gpa = compute_semester_gpa(
                existing_courses + newly_inserted_courses
            )



        # =====================================================
        # STEP 6: RESPONSE TYPE
        # =====================================================
        if saved and updated:
            upload_type = "MIXED"
        elif updated:
            upload_type = "APPEAL"
        else:
            upload_type = "NEW"

        # =====================================================
        # STEP 7: CREATE TRANSCRIPT LOG META
        # =====================================================
        transcript.uploaded_type = upload_type

        if upload_type == "NEW":
            transcript.summary = (
                f"Added {len(saved)} new semester(s): "
                f"{', '.join(saved)}"
            )

        elif upload_type == "APPEAL":
            transcript.summary = (
                f"Updated transcript result for: "
                f"{', '.join(updated)}"
            )

        elif upload_type == "MIXED":
            transcript.summary = (
                f"Added: {', '.join(saved)}. "
                f"Updated: {', '.join(updated)}."
            )

        # =====================================================
        # STEP 8: FINAL COMMIT
        # =====================================================
        db.session.commit()

        return jsonify({
            "success": True,
            "status": upload_type,
            "saved": saved,
            "updated": updated,
            "skipped": skipped,
            "message": "Transcript processed successfully"
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({
            "success": False,
            "message": f"Failed: {str(e)}"
        })

@transcript_bp.route("/delete-transcript-data", methods=["POST"])
@login_required
def delete_transcript_data():


    try:

        transcripts = Transcript.query.filter_by(
            user_id=current_user.user_id
        ).all()

        if not transcripts:
            return jsonify({
                "success": False,
                "message": "No transcript data found to delete."
            })

        transcript_ids = [t.transcript_id for t in transcripts]

        semesters = Semester.query.filter(
            Semester.transcript_id.in_(transcript_ids)
        ).all()

        semester_ids = [
            s.semester_id
            for s in semesters
        ]
        
        # Delete courses
        Course.query.filter(
            Course.semester_id.in_(semester_ids)
        ).delete(
            synchronize_session=False
        )

        # Delete semesters
        Semester.query.filter(
            Semester.transcript_id.in_(transcript_ids)
        ).delete(
            synchronize_session=False
        )

        # Delete transcripts
        Transcript.query.filter_by(
            user_id=current_user.user_id
        ).delete(
            synchronize_session=False
        )

        #delete target cgpa
        TargetCGPA.query.filter_by(
            user_id=current_user.user_id
        ).delete(
            synchronize_session=False
        )


        db.session.commit()

        return jsonify({
            "success": True,
            "message":
            "All transcript data has been deleted successfully."
        })

    except Exception as e:

        db.session.rollback()

        return jsonify({
            "success": False,
            "message": str(e)
        })