from flask import Blueprint, render_template
from flask_login import login_required

career_bp = Blueprint("career", __name__)

@career_bp.route("/career")
@login_required
def career():
    return render_template("career.html",
                           active_page="career" 
                           )