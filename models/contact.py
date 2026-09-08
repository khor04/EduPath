from extensions import db
from datetime import datetime

class ContactMessage(db.Model):

    __tablename__ = "contact_messages"

    contact_id = db.Column(db.Integer, primary_key=True)

    name = db.Column(db.String(100), nullable=False)

    email = db.Column(db.String(120), nullable=False)

    message = db.Column(db.Text, nullable=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Only ever set from current_user when the submitter is actually
    # logged in (see routes/info.py) -- never inferred from the typed
    # email, which is free text an anonymous visitor could put
    # anything into. NULL means genuinely anonymous, not "unmatched".
    user_id = db.Column(db.Integer, db.ForeignKey("users.user_id"), nullable=True)

    user = db.relationship("User")