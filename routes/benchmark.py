from flask import Blueprint, render_template
from flask_login import login_required

benchmark_bp = Blueprint("benchmark", __name__)

@benchmark_bp.route("/benchmarking")
@login_required
def benchmark():
    return render_template("benchmarking.html",
                           active_page="benchmark"
                           )