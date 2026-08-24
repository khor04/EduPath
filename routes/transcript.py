from flask import Blueprint, render_template, request, jsonify,url_for, flash
from flask_login import login_required, current_user
import pdfplumber
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

import re


def extract_programme_from_transcript(text):
    """
    Extract programme from transcript line such as:
    Programme : BACHELOR OF COMPUTER SCIENCE (INFORMATION SYSTEMS)
    """

    match = re.search(
        r"Programme\s*:\s*(.+)",
        text,
        re.IGNORECASE
    )

    if match:
        return match.group(1).strip()

    return None


def normalize_programme(programme):
    """
    Normalize programme names for comparison.
    """

    if not programme:
        return ""

    return " ".join(programme.upper().split())

# @transcript_bp.route("/upload-transcript", methods=["POST"])
# @login_required
# def upload_transcript():
#     if "pdf" not in request.files:
#         return jsonify({"success": False, "message": "No file uploaded."})

#     #validate uploaded file type to ensure only PDF documents are accepted
#     file = request.files["pdf"]

#     if file.filename == "":
#         return jsonify({"success": False, "message": "Please select a PDF file."})

#     if not allowed_file(file.filename):
#         return jsonify({"success": False, "message": "Only PDF files are supported."})

#     os.makedirs(UPLOAD_FOLDER, exist_ok=True)

#     #handle overwriting another user's uplaod
#     filename = f"{uuid.uuid4()}.pdf"
#     filepath = os.path.join(UPLOAD_FOLDER, filename)
#     file.save(filepath)

#     try:
#         text = ""

#         #use pdfplumber to extract text content from the upload file
#         with pdfplumber.open(filepath) as pdf:
#             for page in pdf.pages:
#                 text += page.extract_text() or ""

#         # Check if PDF is image-based (no extractable text)
#         if len(text.strip()) < 20:  # threshold - adjust based on testing
#             return jsonify({
#                 "success": False,
#                 "message": "Unable to read this PDF. Please upload a text-based (not scanned/image) transcript PDF."
            
#             })
#         text_upper = text.upper()

#         has_exam_result = "EXAMINATION RESULT" in text_upper
#         has_exam_centre = "EXAMINATION AND GRADUATION CENTRE" in text_upper
#         has_fsktm = "BACHELOR OF COMPUTER SCIENCE" in text_upper


#         # Case 1: Looks like a UM transcript, but not FSKTM/CS program
#         if has_exam_result and has_exam_centre and not has_fsktm:
#             return jsonify({
#                 "success": False,
#                 "message": "Not UM FSKTM student. Only UM FSKTM Bachelor of Computer Science students can use this website."
#             })

#         # Case 2: Doesn't look like a UM transcript at all
#         if not (has_exam_result and has_exam_centre and has_fsktm):
#             return jsonify({
#                 "success": False,
#                 "message": "Invalid PDF. Only UM FSKTM Bachelor of Computer Science transcripts are supported."
#             })
        
#         semesters = extract_transcript_data(text)

#         return jsonify({
#             "success": True,
#             "message": "Transcript extracted successfully.",
#             "semesters": semesters
#         })
    
#     #remove saved file(Even not um transcript pdf) for privacy problem
#     finally:
#         try:
#             if os.path.exists(filepath):
#                 os.remove(filepath)
#         except Exception as e:
#             print(f"Failed to delete temporary file: {e}")

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

        text = ""

        with pdfplumber.open(filepath) as pdf:
            for page in pdf.pages:
                text += page.extract_text() or ""

        # Reject image-based/scanned PDFs
        if len(text.strip()) < 20:
            return jsonify({
                "success": False,
                "message": "Unable to read this PDF. Please upload a text-based (not scanned/image) transcript PDF."
            })

        text_upper = text.upper()

        # --------------------------------------------------
        # Verify that this is a UM transcript
        # --------------------------------------------------

        has_exam_result = "EXAMINATION RESULT" in text_upper
        has_exam_centre = "EXAMINATION AND GRADUATION CENTRE" in text_upper

        if not (has_exam_result and has_exam_centre):
            return jsonify({
                "success": False,
                "message": "Invalid Universiti Malaya transcript."
            })

        # --------------------------------------------------
        # Extract programme from transcript
        # --------------------------------------------------

        transcript_programme = extract_programme_from_transcript(text)

        if not transcript_programme:
            return jsonify({
                "success": False,
                "message": "Unable to identify programme from transcript."
            })

        # --------------------------------------------------
        # Compare against registered programme
        # --------------------------------------------------

        registered_programme = current_user.programme

        if (
            normalize_programme(transcript_programme)
            != normalize_programme(registered_programme)
        ):
            return jsonify({
                "success": False,
                "message":
                    f"Programme Mismatch:\n\n" 
                    f"Your account is registered under "
                    f"'{registered_programme}', "
                    f"but the uploaded transcript belongs to "
                    f"'{transcript_programme}'."
            })

        # --------------------------------------------------
        # Extract transcript data
        # --------------------------------------------------

        semesters = extract_transcript_data(text)

        return jsonify({
            "success": True,
            "message": "Transcript extracted successfully.",
            "semesters": semesters
        })

    finally:

        try:
            if os.path.exists(filepath):
                os.remove(filepath)
        except Exception as e:
            print(f"Failed to delete temporary file: {e}")
            
def normalize_course_lines(content):
    content = re.sub(
        r"(\d+\.\d{2})(\d+\.\s+[A-Z]{2,}\d{4})",
        r"\1\n\2",
        content
    )

    lines = [line.strip() for line in content.splitlines()]

    def is_course_line(line):
        return bool(re.match(r"^\d+\.\s+[A-Z]{2,}\d{4}", line))

    def is_summary_line(line):
        return bool(re.match(r"^(GPA|CGPA|Result|Credit|Notes)", line, re.I))

    def is_name_fragment(line):
        if not line:
            return False
        if is_course_line(line):
            return False
        if is_summary_line(line):
            return False
        if re.match(r"^No\s+Module", line, re.I):
            return False
        # A line that is ONLY digits/grade/gradepoint is data, not a name
        if re.match(r"^\d+\s+(A\+|A-|A|B\+|B-|B|C\+|C-|C|D\+|D|F)\s+\d+\.\d{2}$", line):
            return False
        # Exclude page headers and institutional text
        if re.match(r"^(STUDENT ACADEMIC PERFORMANCE RECORD|Name|Registration|NRIC|Programme|Faculty)", line, re.I):
            return False
        if len(line) > 80:
            return False
        if re.search(r'\b[a-z]{3,}\b', line):
            return False
        return True

    def has_complete_data(line):
        return bool(re.search(
            r"\s\d+\s+(A\+|A-|A|B\+|B-|B|C\+|C-|C|D\+|D|F)\s+\d+\.\d{2}",
            line
        ))

    def has_no_inline_name(line):
        stripped = re.sub(r"^\d+\.\s+", "", line)
        stripped = re.sub(r"^[A-Z]{2,}\d{4}\s*", "", stripped)
        return bool(re.match(r"^\d+\s+", stripped))

    def inject_name(line, full_name):
        return re.sub(
            r"^(\d+\.\s+[A-Z]{2,}\d{4})\s+",
            rf"\1 {full_name} ",
            line
        )

    def rebuild_course_line(course_no, course_code, name_parts, data_line):
        """Reconstruct a clean course line from scattered pieces."""
        full_name = " ".join(name_parts).strip()
        # data_line is something like "2 A 8.00" — prepend the course number and code
        return f"{course_no} {course_code} {full_name} {data_line}"

    result = []
    i = 0
    while i < len(lines):
        line = lines[i]

        if not line:
            i += 1
            continue

        if is_course_line(line):

            # Case 1: complete data + name already inline — pass through
            if has_complete_data(line) and not has_no_inline_name(line):
                result.append(line)
                i += 1
                continue

            # Case 2: complete data but NO inline name (single-sem style)
            # e.g. "1. GBX0009 2 A 8.00" — look back + ahead for name fragments
            if has_complete_data(line) and has_no_inline_name(line):
                pre_name = ""
                if result and is_name_fragment(result[-1]):
                    pre_name = result.pop()

                post_fragments = []
                j = i + 1
                while j < len(lines):
                    next_line = lines[j].strip()
                    if not next_line:
                        j += 1
                        continue
                    if is_name_fragment(next_line) and not is_course_line(next_line):
                        post_fragments.append(next_line)
                        j += 1
                    else:
                        break

                full_name = " ".join(filter(None, [pre_name] + post_fragments)).strip()
                if full_name:
                    line = inject_name(line, full_name)
                result.append(line)
                i = j
                continue

            # Case 3: incomplete line — name starts inline but data + more name fragments
            # are on subsequent lines
            # e.g. "1. GBX0009 INFORMATION SEEKING, WRITING, AND ACADEMIC"
            #       "2 A 8.00"
            #       "PUBLICATIONS"
            course_match = re.match(r"^(\d+\.\s+)([A-Z]{2,}\d{4})\s*(.*)", line)
            course_no = course_match.group(1).strip()
            course_code = course_match.group(2)
            inline_name = course_match.group(3).strip()

            name_parts = [inline_name] if inline_name else []
            data_line = ""

            j = i + 1
            while j < len(lines):
                next_line = lines[j].strip()
                if not next_line:
                    j += 1
                    continue

                if is_course_line(next_line) or is_summary_line(next_line):
                    break

                # Check if this line is purely the data (credit grade gradepoint)
                if re.match(r"^\d+\s+(A\+|A-|A|B\+|B-|B|C\+|C-|C|D\+|D|F)\s+\d+\.\d{2}$", next_line):
                    data_line = next_line
                    j += 1
                    # After finding data, keep consuming name fragments that follow
                    while j < len(lines):
                        after_line = lines[j].strip()
                        if not after_line:
                            j += 1
                            continue
                        if is_course_line(after_line) or is_summary_line(after_line):
                            break
                        if is_name_fragment(after_line):
                            name_parts.append(after_line)
                            j += 1
                        else:
                            break
                    break
                elif is_name_fragment(next_line):
                    name_parts.append(next_line)
                    j += 1
                else:
                    j += 1

            if data_line:
                rebuilt = rebuild_course_line(course_no, course_code, name_parts, data_line)
            else:
                # fallback: just join everything collected
                rebuilt = f"{course_no} {course_code} {' '.join(name_parts)}"

            result.append(rebuilt)
            i = j
            continue

        elif is_summary_line(line) or not is_name_fragment(line):
            result.append(line)
            i += 1
        else:
            result.append(line)
            i += 1

    return "\n".join(result)


def extract_transcript_data(text):
    semesters = []

    semester_blocks = re.split(
        r"(Examination Result\s+For?\s+Semester\s+\d+,\s+Session\s+\d{4}/\d{4})",
        text,
        flags=re.I
    )

    for i in range(1, len(semester_blocks), 2):
        semester_title = semester_blocks[i].strip()
        header_match = re.search(
            r"Semester\s+(\d+),\s+Session\s+(\d{4}/\d{4})",
            semester_title,
            re.I
        )

        semester_no = int(header_match.group(1)) if header_match else None
        academic_session = header_match.group(2) if header_match else None

        content = semester_blocks[i + 1]
        content = normalize_course_lines(content)

        gpa_match = re.search(r"GPA\s*:\s*([\d.]+)", content)
        cgpa_match = re.search(r"CGPA\s*:\s*([\d.]+)", content)

        semester_data = {
            "semester": semester_title,
            "semester_no": semester_no,
            "academic_session": academic_session,
            "gpa": gpa_match.group(1) if gpa_match else "",
            "cgpa": cgpa_match.group(1) if cgpa_match else "",
            "courses": []
        }
        #debug
        print("CONTENT FOR:", semester_title)
        for j, l in enumerate(content.splitlines()):
            print(f"  {j:02d}: {repr(l)}")

        course_section = re.split(r"(?:GPA\s*:|CGPA\s*:|Result\s*:)", content, flags=re.I)[0]
        lines = [line.strip() for line in course_section.splitlines() if line.strip()]

        for line in lines:
            if not re.match(r"^\d+\.\s+[A-Z]{2,}\d{4}", line):
                continue

            line = re.sub(r"^\d+\.\s+", "", line)
            line = " ".join(line.split())

            parts = line.split()
            if len(parts) < 5:
                continue

            course_code = parts[0]

            match = re.search(
                r"\s(\d+)\s+(A\+|A-|A|B\+|B-|B|C\+|C-|C|D\+|D|F)\s+(\d+\.\d{2})",
                line
            )

            if not match:
                continue

            credits = match.group(1)
            grade = match.group(2)
            grade_point = match.group(3)

            course_name = line[len(course_code):match.start()].strip()

            semester_data["courses"].append({
                "course_code": course_code,
                "course_name": course_name,
                "credits": credits,
                "grade": grade,
                "grade_point": grade_point
            })

        semesters.append(semester_data)

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
                    semester_gpa=float(sem.get("gpa") or 0),
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
            semester.semester_gpa = float(sem.get("gpa") or 0)

            existing_courses = Course.query.filter_by(
                semester_id=semester.semester_id
            ).all()

            existing_map_course = {
                c.course_code.strip().upper(): c
                for c in existing_courses
            }

            for code, c in uploaded_courses.items():

                if code in existing_map_course:

                    db_course = existing_map_course[code]
                    db_course.course_name = c["course_name"]
                    db_course.grade = c["grade"]
                    db_course.grade_point = float(c["grade_point"] or 0)

                else:

                    db.session.add(Course(
                        semester_id=semester.semester_id,
                        course_code=c["course_code"],
                        course_name=c["course_name"],
                        credit_hour=float(c["credits"] or 0),
                        grade=c["grade"],
                        grade_point=float(c["grade_point"] or 0)
                    ))



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