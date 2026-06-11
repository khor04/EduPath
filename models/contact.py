from extensions import db

class ContactMessage(db.Model):

    __tablename__ = "contact_messages"

    contact_id = db.Column(db.Integer, primary_key=True)

    name = db.Column(db.String(100), nullable=False)

    email = db.Column(db.String(120), nullable=False)

    message = db.Column(db.Text, nullable=False)