from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    username = db.Column(db.String(80), unique=True, nullable=False)

    email = db.Column(db.String(120), unique=True, nullable=False)

    password = db.Column(db.String(200), nullable=False)

    phone = db.Column(db.String(30))

    role = db.Column(
        db.String(20),
        default="DRIVER"
    )

    trust_score = db.Column(
        db.Integer,
        default=50
    )

    is_suspended = db.Column(
        db.Boolean,
        default=False
    )

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    incidents = db.relationship(
        "Incident",
    foreign_keys="Incident.user_id",
        backref="user",
        lazy=True
    )

    def to_dict(self):
        return {
           "id": self.id,
           "username": self.username,
           "email": self.email,
           "phone": self.phone,
           "role": self.role,
           "trust_score": self.trust_score,
           "is_suspended": self.is_suspended,
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
    status = db.Column(
        db.String(20),
        default="ACTIVE"
    )

    resolved_at = db.Column(
        db.DateTime,
        nullable=True
    )

    resolved_by = db.Column(
        db.Integer,
        db.ForeignKey("user.id"),
        nullable=True
    )

    resolution_note = db.Column(
        db.String(500),
        nullable=True
    )

    verification_count = db.Column(
        db.Integer,
        default=1
    )

    officially_verified = db.Column(
        db.Boolean,
        default=False
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
            "officially_verified": self.officially_verified,
            "active": self.active,
            "status": self.status,
            "resolved_at": self.resolved_at.isoformat()
                if self.resolved_at else None,
            "resolved_by": self.resolved_by,
            "resolution_note": self.resolution_note,
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

class AuditLog(db.Model):

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("user.id"),
        nullable=False
    )

    action = db.Column(
        db.String(100),
        nullable=False
    )

    target_type = db.Column(
        db.String(50)
    )

    target_id = db.Column(
        db.Integer
    )

    details = db.Column(
        db.String(500)
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "action": self.action,
            "target_type": self.target_type,
            "target_id": self.target_id,
            "details": self.details,
            "created_at": self.created_at.isoformat()
        }

class EmergencyContact(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("user.id"),
        nullable=False
    )

    name = db.Column(
        db.String(100),
        nullable=False
    )

    phone = db.Column(
        db.String(30),
        nullable=False
    )

    relationship = db.Column(
        db.String(50),
        nullable=True
    )

    is_primary = db.Column(
        db.Boolean,
        default=False
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "name": self.name,
            "phone": self.phone,
            "relationship": self.relationship,
            "is_primary": self.is_primary,
            "created_at": (
                self.created_at.isoformat()
                if self.created_at else None
            )
        }


class SOSEvent(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("user.id"),
        nullable=False
    )

    latitude = db.Column(db.Float, nullable=False)
    longitude = db.Column(db.Float, nullable=False)

    emergency_type = db.Column(
        db.String(50),
        default="GENERAL"
    )

    message = db.Column(
        db.String(500),
        nullable=True
    )

    status = db.Column(
        db.String(20),
        default="ACTIVE"
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )

    cancelled_at = db.Column(
        db.DateTime,
        nullable=True
    )

    resolved_at = db.Column(
        db.DateTime,
        nullable=True
    )

    resolved_by = db.Column(
        db.Integer,
        db.ForeignKey("user.id"),
        nullable=True
    )

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "emergency_type": self.emergency_type,
            "message": self.message,
            "status": self.status,
            "created_at": (
                self.created_at.isoformat()
                if self.created_at else None
            ),
            "cancelled_at": (
                self.cancelled_at.isoformat()
                if self.cancelled_at else None
            ),
            "resolved_at": (
                self.resolved_at.isoformat()
                if self.resolved_at else None
            ),
            "resolved_by": self.resolved_by
        }
