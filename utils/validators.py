import re

from PIL import Image

from services.cgpa_services import GRADE_POINTS

UM_EMAIL_DOMAIN = "siswa.um.edu.my"


def is_um_email(email):
    if not email:
        return False

    return email.strip().lower().endswith("@" + UM_EMAIL_DOMAIN)


PASSWORD_PATTERN = re.compile(
    r'^(?=.*\d)(?=.*[!@#$%^&*()_+\-=\[\]{};\'":\\|,.<>/?]).{8,}$'
)

PASSWORD_REQUIREMENT_MESSAGE = (
    "Password must be at least 8 characters long and contain "
    "at least 1 digit and 1 special character."
)


def is_valid_password(password):
    if not password:
        return False

    return bool(PASSWORD_PATTERN.match(password))


# Generous safety caps, not real academic policy limits -- just wide
# enough that no genuine UM course/semester ever hits them, so they
# only ever reject malformed or malicious payloads.
MAX_CREDIT_HOURS_PER_COURSE = 10
MAX_COURSES_PER_SEMESTER = 15


def validate_course_row(course):
    """
    Validates and normalizes one course row from a transcript
    save/appeal request (routes/transcript.py's /save-transcript).

    The server never trusts the client's submitted grade_point --
    only the grade is trusted (after validating it's a real grade),
    and grade_point is always re-derived here from
    GRADE_POINTS[grade] * credits. This closes the gap where a
    tampered or buggy client could submit a grade/grade_point pair
    that don't match (e.g. grade "F" with grade_point 16.0).

    Returns (cleaned_course_dict, None) on success, or
    (None, error_message) if the row is invalid -- callers should
    surface the message rather than silently dropping or "fixing"
    the row themselves.
    """
    course_code = (course.get("course_code") or "").strip().upper()
    course_name = (course.get("course_name") or "").strip()
    grade = (course.get("grade") or "").strip().upper()

    if not course_code:
        return None, "Course code is required."

    if not course_name:
        return None, f"{course_code}: course name is required."

    if grade not in GRADE_POINTS:
        return None, f"{course_code}: unrecognized grade '{grade}'."

    try:
        credits = float(course.get("credits"))
    except (TypeError, ValueError):
        return None, f"{course_code}: credit hour must be a number."

    if credits <= 0 or credits > MAX_CREDIT_HOURS_PER_COURSE:
        return None, (
            f"{course_code}: credit hour must be greater than 0 and at "
            f"most {MAX_CREDIT_HOURS_PER_COURSE}."
        )

    grade_point = round(GRADE_POINTS[grade] * credits, 2)

    return {
        "course_code": course_code,
        "course_name": course_name,
        "credits": credits,
        "grade": grade,
        "grade_point": grade_point,
    }, None


ALLOWED_PROFILE_PICTURE_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}
MAX_PROFILE_PICTURE_SIZE = 5 * 1024 * 1024  # 5 MB


def validate_profile_picture(file):
    """
    Validates an uploaded profile picture (routes/profile.py's
    /upload-picture) before it ever reaches Cloudinary.

    Checked cheapest-first: extension, then size, then actual image
    content -- a file named photo.jpg isn't necessarily a real JPEG,
    so the extension/size checks alone would let a spoofed or
    corrupted file through. Image.verify() is what actually confirms
    the bytes decode as a real image.

    Returns an error message string if invalid, or None if the file
    is safe to upload. Leaves the file's read position at 0 either
    way, since Image.verify() consumes the stream and Cloudinary
    needs to read it again from the start afterward.
    """
    filename = file.filename or ""
    extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

    if extension not in ALLOWED_PROFILE_PICTURE_EXTENSIONS:
        return "Unsupported file type. Please upload a PNG, JPG, GIF, or WEBP image."

    file.seek(0, 2)  # SEEK_END
    size = file.tell()
    file.seek(0)

    if size == 0:
        return "The selected file is empty."

    if size > MAX_PROFILE_PICTURE_SIZE:
        return "Image is too large. Maximum size is 5MB."

    try:
        Image.open(file).verify()
    except Exception:
        return "The uploaded file is not a valid image."
    finally:
        file.seek(0)

    return None
