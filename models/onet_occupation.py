from extensions import db

class OnetOccupation(db.Model):
    __tablename__ = 'onet_occupation'

    id            = db.Column(db.Integer, primary_key=True)
    onet_soc_code = db.Column(db.String(20), unique=True, nullable=False)
    title         = db.Column(db.String(200), nullable=False)
    description   = db.Column(db.Text)
