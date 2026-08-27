from extensions import db

class OnetOccupationConcept(db.Model):
    __tablename__ = 'onet_occupation_concept'

    id                     = db.Column(db.Integer, primary_key=True)
    onet_soc_code          = db.Column(db.String(20), nullable=False)

    concept_type           = db.Column(db.String(10), nullable=False)   # 'skill' or 'knowledge'
    concept_name           = db.Column(db.String(100), nullable=False)

    importance_raw         = db.Column(db.Float, nullable=False)        # O*NET's own 1-5 scale, kept for FYP explainability
    importance_normalized  = db.Column(db.Float, nullable=False)        # (importance_raw - 1) / 4, scaled to 0-1

    __table_args__ = (
        db.Index('ix_onet_occupation_concept_soc_code', 'onet_soc_code'),
        db.UniqueConstraint(
            'onet_soc_code', 'concept_type', 'concept_name',
            name='unique_occupation_concept'
        ),
    )
