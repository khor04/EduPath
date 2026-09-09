from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user, logout_user
from extensions import db
from werkzeug.security import check_password_hash, generate_password_hash
from models.users import User
from models.contact import ContactMessage
import cloudinary.uploader
import cloudinary
from utils.validators import is_valid_password, PASSWORD_REQUIREMENT_MESSAGE, is_um_email, UM_EMAIL_DOMAIN, validate_profile_picture
from routes.auth import issue_verification_code
from routes.transcript import delete_all_transcript_related_data
from datetime import datetime
from zoneinfo import ZoneInfo


profile_bp = Blueprint("profile", __name__)


@profile_bp.route("/upload-picture", methods=["POST"])
@login_required
def upload_picture():
    file = request.files.get("profile_picture")

    if not file or file.filename == "":
        flash("Please select an image.", "error")
        return redirect(url_for("profile.profile"))

    validation_error = validate_profile_picture(file)
    if validation_error:
        flash(validation_error, "error")
        return redirect(url_for("profile.profile"))

    try:
        upload_result = cloudinary.uploader.upload(
            file,
            folder="edupath/profile_pictures",
            public_id=f"user_{current_user.user_id}",
            overwrite=True,
            resource_type="image"
        )
    except Exception as e:
        print("Cloudinary upload failed:", type(e).__name__, ":", e)
        flash("Failed to upload profile picture. Please try again later.", "error")
        return redirect(url_for("profile.profile"))

    current_user.profile_picture = upload_result["secure_url"]
    db.session.commit()

    flash("Profile picture updated successfully.", "success")
    return redirect(url_for("profile.profile"))

@profile_bp.route("/profile", methods=["GET", "POST"])
@login_required
def profile():

    if request.method == "POST":
    
        username = request.form.get("username")
        new_email = request.form.get("email")

        if not username or not new_email:
            flash("Missing required fields.", "error")
            return redirect(url_for("profile.profile"))

        
        # Check duplicate username
        existing_username = User.query.filter(
        User.username == username,
        User.user_id != current_user.user_id
        ).first()

        if existing_username:
            flash("Username already exists.", "error")
            return redirect(url_for("profile.profile"))

        current_user.username = username

        # EMAIL CHANGED LOGIC
        if new_email != current_user.email:

            if not is_um_email(new_email):
                flash(f"Only @{UM_EMAIL_DOMAIN} email addresses are allowed.", "error")
                return redirect(url_for("profile.profile"))

            # Re-submitting the same email that's already pending on this
            # account (e.g. they navigated away from /verify-code and came
            # back through the profile form instead of the "Verify Email"
            # link) shouldn't spin up a brand new request/code -- just send
            # them back to the existing one. The verify page's own "Resend
            # Code" button (with its cooldown) already covers getting a
            # fresh code if theirs expired.
            if current_user.email_pending == new_email:
                flash("A verification code was already sent to this email. Enter it below, or resend a new one.", "success")
                return redirect(url_for("auth.verify_code_page", email=new_email))

            # check duplicate email
            existing_user = User.query.filter_by(email=new_email).first()
            if existing_user:
                if existing_user.is_verified:
                    flash("Email already registered.", "error")
                    return redirect(url_for("profile.profile"))

                expired = (
                    not existing_user.verification_expires_at
                    or datetime.utcnow() > existing_user.verification_expires_at
                )

                if expired:
                    db.session.delete(existing_user)
                    db.session.commit()
                else:
                    flash("That email is already pending verification on another account.", "error")
                    return redirect(url_for("profile.profile"))

            # check the email isn't ALREADY someone else's active pending
            # email-change request -- the check above only looks at the
            # primary `email` column, which a profile change never writes
            # to until verified (unlike signup, which writes there
            # immediately), so a concurrent change-in-progress would
            # otherwise slip past it entirely.
            pending_user = User.query.filter(
                User.email_pending == new_email,
                User.user_id != current_user.user_id,
            ).first()

            if pending_user:
                pending_expired = (
                    not pending_user.verification_expires_at
                    or datetime.utcnow() > pending_user.verification_expires_at
                )

                if pending_expired:
                    # Stale, abandoned change request -- this is a real
                    # account (unlike the deleted row above), so only the
                    # pending-change fields are cleared, never the account
                    # itself.
                    pending_user.email_pending = None
                    pending_user.verification_code_hash = None
                    pending_user.verification_expires_at = None
                    pending_user.verification_attempts = 0
                    db.session.commit()
                else:
                    flash("That email is already pending verification on another account.", "error")
                    return redirect(url_for("profile.profile"))

            # update email + mark unverified
            current_user.email_pending = new_email
            current_user.email_change_requested_at = datetime.now(ZoneInfo("Asia/Kuala_Lumpur"))

            db.session.commit()

            # send verification code to the new email
            issue_verification_code(current_user)

            # Deliberately NOT logging the user out here. The old email
            # stays the authoritative login email until the code is
            # verified (see the email_pending branch in
            # routes/auth.py:verify_code_page), so there's no reason to
            # interrupt their session just to prove ownership of the new
            # address -- and staying logged in means closing the verify
            # page isn't a dead end: the profile page shows a "verification
            # pending" banner they can return to at any time.
            flash("Verification code sent to your new email. Please verify to complete the change.", "success")

            return redirect(url_for("auth.verify_code_page", email=new_email))
        

        # no email change
        db.session.commit()
        flash("Profile updated successfully.", "success")
        return redirect(url_for("profile.profile"))
    
    return render_template("profile.html", user=current_user, active_page="profile")

@profile_bp.route("/change-password", methods=["POST"])
@login_required
def change_password():
    current_password = request.form.get("current_password")
    new_password = request.form.get("new_password")
    confirm_password = request.form.get("confirm_password")

    if not current_password or not new_password or not confirm_password:
        flash("Please fill in all password fields.", "error")
        return redirect(url_for("profile.profile", modal="password_error"))

    if not check_password_hash(current_user.password, current_password):
        flash("Current password is incorrect.", "error")
        return redirect(url_for("profile.profile", modal="password_error"))

    if not is_valid_password(new_password):
        flash(PASSWORD_REQUIREMENT_MESSAGE, "error")
        return redirect(url_for("profile.profile", modal = "password_error"))
    
    if current_password == new_password:
        flash("New password must be different from the current password.","error")
        return redirect(url_for("profile.profile", modal="password_error"))
    
    if new_password != confirm_password:
        flash("New password and confirm password do not match.", "error")
        return redirect(url_for("profile.profile", modal="password_error"))

    current_user.password = generate_password_hash(new_password)
    db.session.commit()

    flash("Password updated successfully.", "success")
    return redirect(url_for("profile.profile", modal="success"))


@profile_bp.route("/check-current-password", methods=["POST"])
@login_required
def check_current_password():
    data = request.get_json()

    if not data:
        return {"valid": False}

    current_password = data.get("current_password")

    if not current_password:
        return {"valid": False}

    is_correct = check_password_hash(current_user.password, current_password)

    return {"valid": is_correct}


@profile_bp.route("/delete-account", methods=["POST"])
@login_required
def delete_account():
    user_id = current_user.user_id

    try:
        delete_all_transcript_related_data(user_id)

        # Contact messages reference user_id via a foreign key that isn't
        # covered by delete_all_transcript_related_data (it's not
        # transcript-derived data). Deleting the user with these still
        # pointing at them fails the FK constraint -- orphan them to NULL
        # instead of deleting the messages themselves, matching the
        # model's own "NULL means anonymous" semantics (models/contact.py)
        # so support history survives account deletion.
        ContactMessage.query.filter_by(user_id=user_id).update(
            {"user_id": None}, synchronize_session=False
        )

        user = User.query.get(user_id)
        if user:
            db.session.delete(user)

        db.session.commit()

    except Exception as e:
        db.session.rollback()
        print("Account deletion failed:", type(e).__name__, ":", e)
        flash("Failed to delete account. Please try again.", "error")
        return redirect(url_for("profile.profile"))

    logout_user()

    flash("Account deleted successfully.", "success")
    return redirect(url_for("auth.register"))
