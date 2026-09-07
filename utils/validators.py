import re

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
