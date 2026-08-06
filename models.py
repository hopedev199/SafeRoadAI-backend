from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    username = db.Column(db.String(80), unique=True, nullable=False)

    email = db.Column(db.String(120), unique=True, nullable=False)

    password = db.Column(db.String(200), nullable=False)

    phone = db.Column(db.String(30))

    trust_score = db.Column(
        db.Integer,
        default=50
    )

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    incidents = db.relationship(
        "Incident",
        backref="user",
        lazy=True
    )

    def to_dict(self):
        return {
            "id": self.id,
            "username": self.username,
            "email": self.email,
            "phone": self.phone,
            "created_at": self.created_at.isoformat()
        }

class Incident(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    incident_type = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(300))
    latitude = db.Column(db.Float, nullable=False)
    longitude = db.Column(db.Float, nullable=False)
    reporter = db.Column(db.String(100))
    user_id = db.Column(
    db.Integer,
    db.ForeignKey("user.id")
)
    severity = db.Column(db.String(20), default="Medium")
    active = db.Column(db.Boolean, default=True)

    verification_count = db.Column(
        db.Integer,
        default=1
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )
    def to_dict(self):
        return {
            "id": self.id,
            "incident_type": self.incident_type,
            "description": self.description,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "reporter": self.reporter,
            "severity": self.severity,
            "verification_count": self.verification_count,
            "active": self.active,
            "created_at": self.created_at.isoformat()
        }

class IncidentConfirmation(db.Model):

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("user.id"),
        nullable=False
    )

    incident_id = db.Column(
        db.Integer,
        db.ForeignKey("incident.id"),
        nullable=False
    )

    confirmed_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )
