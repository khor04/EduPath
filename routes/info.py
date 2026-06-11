from flask import Blueprint, render_template, request, redirect, url_for, flash
from extensions import db
from models.contact import ContactMessage

info_bp = Blueprint("info", __name__)


@info_bp.route("/about")
def about():
    return render_template("about.html", active_page="about")


@info_bp.route("/contact", methods=["GET", "POST"])
def contact():

    if request.method == "POST":
        print("CONTACT ROUTE HIT")

        name = request.form.get("name")
        email = request.form.get("email")
        message = request.form.get("message")

        new_message = ContactMessage(
            name=name,
            email=email,
            message=message
        )

        db.session.add(new_message)
        db.session.commit()

        flash("Message sent successfully!", "success")

        return redirect(url_for("info.contact"))

    return render_template("contact.html", active_page="contact")


@info_bp.route("/privacy")
def privacy():
    return render_template("privacy.html", active_page="privacy")