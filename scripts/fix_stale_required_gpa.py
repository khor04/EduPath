"""
One-time data fix: caps any existing TargetCGPA.required_gpa values above
4.00 down to 4.00.

Before this fix, routes/analysis.py's /save-target-cgpa saved the raw,
uncapped required GPA (e.g. 4.02) for any plan that wasn't "Impossible" --
only ever a rounding artifact of the 2dp-consistent achievability check,
never a real "impossible" case (Impossible plans are rejected before the
save happens at all). That stale value is read directly by the Dashboard's
Performance Alert, the PDF/JSON report, and the AI chatbot's context
(services/cgpa_services.py, services/report_services.py,
services/chat_services.py), so a plan already marked "Achievable"
everywhere else could still show "requires an average GPA of 4.02" -- a
number above the actual 4.00 maximum.

New saves are already fixed at the source; this just corrects rows saved
before that fix. Safe to re-run: capping an already-capped value is a
no-op.

Usage:
    python scripts/fix_stale_required_gpa.py
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from extensions import db
from models.target_cgpa import TargetCGPA

app = create_app()

with app.app_context():
    stale = TargetCGPA.query.filter(TargetCGPA.required_gpa > 4.0).all()

    if not stale:
        print("Nothing to fix -- no TargetCGPA rows above 4.00.")
    else:
        for row in stale:
            print(f"user_id={row.user_id}: required_gpa {row.required_gpa} -> 4.00")
            row.required_gpa = 4.0

        db.session.commit()
        print(f"Fixed {len(stale)} row(s).")
