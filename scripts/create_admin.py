"""
Bootstrap script for administrator accounts. Admin accounts are
provisioned separately from the public /signup flow on purpose:
/signup always requires a @siswa.um.edu.my address and always
creates a student account (is_admin=False) -- there is no
self-service way for a student to become an admin. This script is
the only path that can ever set is_admin=True.

Usage:
    python scripts/create_admin.py <email>

Prompts for a username and password (hidden input, confirmed) --
never pass the password on the command line, it would end up in
shell history.

If the email already belongs to an existing user, that account is
promoted in place (is_admin=True, is_verified=True) instead of
failing on the email-uniqueness constraint. Otherwise a brand new
account is created with placeholder faculty/programme/batch values
("N/A") -- those columns are NOT NULL on User, but meaningless for
an admin who never touches the student-facing pages that read them
(transcript upload, benchmarking, dashboard).
"""
import sys
import os
import getpass

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from werkzeug.security import generate_password_hash
from extensions import db
from models.users import User
from app import create_app

if len(sys.argv) != 2:
    print("Usage: python scripts/create_admin.py <email>")
    sys.exit(1)

email = sys.argv[1]

app = create_app()

with app.app_context():
    user = User.query.filter_by(email=email).first()

    if user:
        user.is_admin = True
        user.is_verified = True
        db.session.commit()
        print(f"{email!r} already existed as a user -- promoted to admin.")
        sys.exit(0)

    username = input("Admin username: ").strip()

    password = getpass.getpass("Admin password: ")
    confirm = getpass.getpass("Confirm password: ")

    if not password:
        print("Password cannot be empty.")
        sys.exit(1)

    if password != confirm:
        print("Passwords do not match.")
        sys.exit(1)

    user = User(
        username=username,
        email=email,
        password=generate_password_hash(password),
        faculty="N/A",
        programme="N/A",
        batch="N/A",
        is_verified=True,
        is_admin=True,
    )
    db.session.add(user)
    db.session.commit()
    print(f"Created admin account: {email}")
