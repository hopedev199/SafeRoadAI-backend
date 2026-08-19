import os
from pathlib import Path
import math
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / '.env')

from flask import Flask, jsonify, request
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
from models import (
    db,
    Incident,
    User,
    IncidentConfirmation,
    AuditLog,
    EmergencyContact,
    SOSEvent,
)
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_jwt_extended import (
    JWTManager,
    create_access_token,
    jwt_required,
    get_jwt_identity
)

def calculate_severity(incident_type):

    critical = [
        "Armed Robbery",
        "Kidnapping",
        "Terror Attack",
        "Active Shooting",
        "Security Threat",
    ]

    high = [
        "Accident",
        "Serious Accident",
        "Roadblock",
        "Flooding",
        "Fire Outbreak",
        "Bridge Collapse",
        "Landslide",
    ]

    medium = [
        "Traffic",
        "Heavy Traffic",
        "Broken Down Vehicle",
        "Vehicle Breakdown",
        "Protest",
        "Bad Weather",
    ]

    low = [
        "Pothole",
        "Bad Road",
        "Construction",
        "Speed Bump",
    ]

    if incident_type in critical:
        return "Critical"

    if incident_type in high:
        return "High"

    if incident_type in medium:
        return "Medium"

    if incident_type in low:
        return "Low"

    return "Medium"


from datetime import datetime


def incident_lifetime_hours(incident_type):

    lifetime = {
        "Traffic": 2,
        "Heavy Traffic": 2,

        "Accident": 24,
        "Serious Accident": 24,

        "Roadblock": 24,

        "Flooding": 48,
        "Fire Outbreak": 48,

        "Pothole": 2160,
        "Bad Road": 2160,

        "Security Threat": None,
        "Armed Robbery": None,
        "Kidnapping": None,
        "Active Shooting": None,
        "Terror Attack": None,
    }

    return lifetime.get(incident_type, 24)


def is_incident_expired(incident):

    lifetime = incident_lifetime_hours(
        incident.incident_type
    )

    if lifetime is None:
        return False

    age_hours = (
        datetime.utcnow() -
        incident.created_at
    ).total_seconds() / 3600

    return age_hours >= lifetime

def calculate_trust_score(incident):

    score = 20

    # Driver confirmations
    score += min(
        incident.verification_count * 10,
        50
    )

    # Severity bonus
    if incident.severity == "Critical":
        score += 20
    elif incident.severity == "High":
        score += 15
    elif incident.severity == "Medium":
        score += 10
    else:
        score += 5

    return min(score, 100)

from functools import wraps

from functools import wraps

def get_current_user():
    user_id = int(get_jwt_identity())

    user = User.query.get(user_id)

    if not user:
        return None, jsonify({
            "error": "User not found"
        }), 404

    if user.is_suspended:
        return None, jsonify({
            "error": "Account suspended"
        }), 403

    return user, None, None


def active_user_required(fn):
    @wraps(fn)
    @jwt_required()
    def wrapper(*args, **kwargs):

        user, error_response, status_code = get_current_user()

        if error_response:
            return error_response, status_code

        return fn(*args, **kwargs)

    return wrapper


def admin_required(fn):
    @wraps(fn)
    @jwt_required()
    def wrapper(*args, **kwargs):

        user, error_response, status_code = get_current_user()

        if error_response:
            return error_response, status_code

        if user.role != "ADMIN":
            return jsonify({
                "error": "Administrator access required"
            }), 403

        return fn(*args, **kwargs)

    return wrapper


def incident_resolver_required(fn):
    @wraps(fn)
    @jwt_required()
    def wrapper(*args, **kwargs):

        user, error_response, status_code = get_current_user()

        if error_response:
            return error_response, status_code

        allowed_roles = [
            "ROAD_OFFICER",
            "EMERGENCY",
            "ADMIN"
        ]

        if user.role not in allowed_roles:
            return jsonify({
                "error": "Incident resolution access required"
            }), 403

        return fn(*args, **kwargs)

    return wrapper

def reputation_level(score):

    if score >= 95:
        return "🏆 Elite Road Guardian"

    elif score >= 85:
        return "🟣 Road Guardian"

    elif score >= 70:
        return "🔵 Verified Reporter"

    elif score >= 50:
        return "🟢 Trusted Driver"

    return "🚗 New Driver"
app = Flask(__name__)

app.config["JWT_SECRET_KEY"] = "SafeRoadAI_Very_Long_Secret_Key_2026_Change_Me"

jwt = JWTManager(app)

limiter = Limiter(
    key_func=get_remote_address,
    app=app,
    default_limits=["200 per day", "50 per hour"]
)

CORS(app)

app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db.init_app(app)

with app.app_context():
    db.create_all()

def create_audit_log(
    user_id,
    action,
    target_type=None,
    target_id=None,
    details=None
):
    log = AuditLog(
        user_id=user_id,
        action=action,
        target_type=target_type,
        target_id=target_id,
        details=details
    )

    db.session.add(log)
    db.session.commit()

def distance_km(lat1, lon1, lat2, lon2):
    """
    Accurate distance between two GPS coordinates.
    Returns kilometers.
    """

    R = 6371

    lat1 = math.radians(lat1)
    lat2 = math.radians(lat2)

    dlat = lat2 - lat1
    dlon = math.radians(lon2 - lon1)

    a = (
        math.sin(dlat / 2) ** 2
        +
        math.cos(lat1)
        * math.cos(lat2)
        * math.sin(dlon / 2) ** 2
    )

    c = 2 * math.atan2(
        math.sqrt(a),
        math.sqrt(1 - a)
    )

    return R * c

def alert_level(distance, severity):

    if severity == "Critical":
        if distance <= 0.3:
            return "🚨 EVACUATE OR TURN BACK IMMEDIATELY"
        elif distance <= 1:
            return "🚨 CRITICAL DANGER AHEAD"
        elif distance <= 2:
            return "⚠️ CRITICAL INCIDENT NEARBY"
        return "⚠️ CRITICAL WARNING"

    elif severity == "High":
        if distance <= 0.3:
            return "🔴 IMMEDIATE DANGER"
        elif distance <= 1:
            return "🟠 HIGH RISK AHEAD"
        elif distance <= 2:
            return "⚠️ HIGH RISK AREA"
        return "⚠️ HIGH RISK"

    elif severity == "Medium":
        if distance <= 0.5:
            return "🟡 DRIVE WITH CAUTION"
        elif distance <= 2:
            return "⚠️ INCIDENT AHEAD"
        return "⚠️ WARNING"

    elif severity == "Low":
        if distance <= 1:
            return "🟢 STAY ALERT"
        return "ℹ️ NOTICE"

    return "ℹ️ NOTICE"

@app.route("/admin/users")
@admin_required
def admin_users():

    users = User.query.all()

    return jsonify([
        user.to_dict() for user in users
    ])

@app.route("/admin/promote/<int:user_id>", methods=["POST"])
@admin_required
def promote_user(user_id):

    data = request.get_json()

    role = data.get("role")

    allowed_roles = [
        "DRIVER",
        "ROAD_OFFICER",
        "EMERGENCY",
        "ADMIN"
    ]

    if role not in allowed_roles:
        return jsonify({
            "error": "Invalid role"
        }), 400

    user = User.query.get(user_id)

    if not user:
        return jsonify({
            "error": "User not found"
        }), 404

    user.role = role

    db.session.commit()

    create_audit_log(
        user_id=get_jwt_identity(),
        action="PROMOTED_USER",
        target_type="USER",
        target_id=user.id,
        details=f"Changed role of {user.username} to {role}"
    )

    return jsonify({
        "message": "User promoted successfully",
        "user": user.to_dict()
    })

@app.route("/admin/suspend/<int:user_id>", methods=["POST"])
@admin_required
def suspend_user(user_id):

    user = User.query.get(user_id)

    if not user:
        return jsonify({
            "error": "User not found"
        }), 404

    if user.is_suspended:
        return jsonify({
            "message": "User is already suspended"
        }), 400

    # Prevent an admin from suspending themselves
    current_admin_id = int(get_jwt_identity())

    if user.id == current_admin_id:
        return jsonify({
            "error": "You cannot suspend your own account"
        }), 400

    user.is_suspended = True

    db.session.commit()

    create_audit_log(
        user_id=current_admin_id,
        action="SUSPENDED_USER",
        target_type="USER",
        target_id=user.id,
        details=f"Suspended user {user.username}"
    )

    return jsonify({
        "message": "User suspended successfully",
        "user": user.to_dict()
    })

@app.route("/admin/unsuspend/<int:user_id>", methods=["POST"])
@admin_required
def unsuspend_user(user_id):

    user = User.query.get(user_id)

    if not user:
        return jsonify({
            "error": "User not found"
        }), 404

    if not user.is_suspended:
        return jsonify({
            "message": "User is not suspended"
        }), 400

    current_admin_id = int(get_jwt_identity())

    user.is_suspended = False

    db.session.commit()

    create_audit_log(
        user_id=current_admin_id,
        action="UNSUSPENDED_USER",
        target_type="USER",
        target_id=user.id,
        details=f"Unsuspended user {user.username}"
    )

    return jsonify({
        "message": "User unsuspended successfully",
        "user": user.to_dict()
    }), 200

@app.route("/admin/audit-logs", methods=["GET"])
@admin_required
def get_audit_logs():

    try:
        page = int(request.args.get("page", 1))
        limit = int(request.args.get("limit", 50))
    except (TypeError, ValueError):
        return jsonify({
            "error": "Invalid page or limit"
        }), 400

    if page < 1:
        return jsonify({
            "error": "Page must be 1 or greater"
        }), 400

    # Keep each request bounded
    limit = max(1, min(limit, 100))

    query = AuditLog.query

    action = request.args.get("action")
    target_type = request.args.get("target_type")
    user_id = request.args.get("user_id")

    if action:
        query = query.filter(
            AuditLog.action == action
        )

    if target_type:
        query = query.filter(
            AuditLog.target_type == target_type
        )

    if user_id:
        try:
            user_id = int(user_id)
        except ValueError:
            return jsonify({
                "error": "Invalid user_id"
            }), 400

        query = query.filter(
            AuditLog.user_id == user_id
        )

    query = query.order_by(
            AuditLog.id.desc()
    )

    total = query.count()

    logs = query.offset(
        (page - 1) * limit
    ).limit(limit).all()

    return jsonify({
        "page": page,
        "limit": limit,
        "count": len(logs),
        "total": total,
        "total_pages": (
            (total + limit - 1) // limit
        ),
        "logs": [
            log.to_dict()
            for log in logs
        ]
    }), 200

@app.route("/")
def home():
    return jsonify({
        "project": "SafeRoad AI",
        "status": "Backend Running",
        "database": "Connected"
    })

@app.route("/report", methods=["POST"])
@active_user_required
@limiter.limit("10 per minute")
def report_incident():

    data = request.get_json()
    user_id = int(get_jwt_identity())

    incident = Incident(
        incident_type=data["incident_type"],
        description=data.get("description"),
        latitude=data["latitude"],
        longitude=data["longitude"],
        reporter=data.get("reporter"),
        user_id=user_id,
        severity=calculate_severity(
            data["incident_type"]
        ),
        active=True
    )

    db.session.add(incident)
    db.session.commit()

    return jsonify({
        "message": "Incident reported successfully",
        "incident": incident.to_dict()
    }), 201


@app.route("/resolve/<int:incident_id>", methods=["POST"])
@incident_resolver_required
def resolve_incident(incident_id):

    user_id = int(get_jwt_identity())

    incident = Incident.query.get(incident_id)

    if not incident:
        return jsonify({
            "error": "Incident not found"
        }), 404

    if incident.status == "RESOLVED":
        return jsonify({
            "error": "Incident already resolved"
        }), 400

    data = request.get_json() or {}

    resolution_note = data.get(
        "resolution_note",
        "Incident resolved by authorized personnel"
    )

    incident.status = "RESOLVED"
    incident.active = False
    incident.resolved_at = datetime.utcnow()
    incident.resolved_by = user_id
    incident.resolution_note = resolution_note

    audit = AuditLog(
        user_id=user_id,
        action="RESOLVED_INCIDENT",
        target_type="INCIDENT",
        target_id=incident.id,
        details=(
            "Incident resolved by authorized personnel. "
            f"Note: {resolution_note}"
        )
    )

    db.session.add(audit)
    db.session.commit()

    return jsonify({
        "message": "Incident resolved successfully",
        "incident": incident.to_dict()
    }), 200

@app.route("/incidents")
def incidents():

    all_incidents = Incident.query.all()

    return jsonify([i.to_dict() for i in all_incidents])

@app.route("/nearby")
def nearby():

    try:
        lat = float(request.args.get("lat"))
        lon = float(request.args.get("lon"))
        radius = float(request.args.get("radius", 2))
    except (TypeError, ValueError):
        return jsonify({"error": "Invalid or missing lat/lon"}), 400

    nearby_incidents = []

    for incident in Incident.query.filter_by(active=True).all():
        if is_incident_expired(incident):
            incident.active = False
            db.session.commit()
            continue

        d = distance_km(
            lat,
            lon,
            incident.latitude,
            incident.longitude
        )

        if d <= radius:
            item = incident.to_dict()
            item["distance_km"] = round(d, 2)
            item["alert"] = alert_level(d, incident.severity)
            item["trust_score"] = calculate_trust_score(incident)

            nearby_incidents.append(item)

    # Closest danger appears first
    nearby_incidents.sort(
        key=lambda x: x["distance_km"]
    )

    return jsonify(nearby_incidents)


@app.route("/register", methods=["POST"])
@limiter.limit("3 per minute")
def register():

    data = request.get_json()

    # Check if username already exists
    if User.query.filter_by(username=data["username"]).first():
        return jsonify({"error": "Username already exists"}), 400

    # Check if email already exists
    if User.query.filter_by(email=data["email"]).first():
        return jsonify({"error": "Email already exists"}), 400

    user = User(
        username=data["username"],
        email=data["email"],
        password=generate_password_hash(data["password"]),
        phone=data.get("phone")
    )

    db.session.add(user)
    db.session.commit()

    return jsonify({
        "message": "Registration successful",
        "user": user.to_dict()
    }), 201


@app.route("/login", methods=["POST"])
@limiter.limit("5 per minute")
def login():

    data = request.get_json()

    user = User.query.filter_by(username=data["username"]).first()

    if not user:
        app.logger.warning("LOGIN DEBUG: USER NOT FOUND")
        return jsonify({"error": "Invalid username or password"}), 401

    if not check_password_hash(user.password, data["password"]):
        app.logger.warning("LOGIN DEBUG: PASSWORD CHECK FAILED")
        return jsonify({"error": "Invalid username or password"}), 401

    app.logger.info("LOGIN DEBUG: PASSWORD CHECK PASSED") 

    if user.is_suspended:
        return jsonify({
            "error": "Account suspended"
        }), 403

    access_token = create_access_token(
        identity=str(user.id)
    )

    return jsonify({
        "message": "Login successful",
        "token": access_token,
        "user": user.to_dict()
    })

@app.route("/profile", methods=["PUT"])
@jwt_required()
def update_profile():

    user_id = int(get_jwt_identity())

    user = User.query.get(user_id)

    if not user:
        return jsonify({
            "error": "User not found"
        }), 404

    data = request.get_json()

    username = data.get("username")
    phone = data.get("phone")

    if username:
        existing_user = User.query.filter_by(
            username=username
        ).first()

        if existing_user and existing_user.id != user.id:
            return jsonify({
                "error": "Username already exists"
            }), 400

        user.username = username

    if phone:
        user.phone = phone

    db.session.commit()

    return jsonify({
        "message": "Profile updated successfully",
        "user": user.to_dict()
    }), 200

@app.route("/change-password", methods=["PUT"])
@jwt_required()
def change_password():

    user_id = int(get_jwt_identity())

    user = User.query.get(user_id)

    if not user:
        return jsonify({
            "error": "User not found"
        }), 404

    data = request.get_json() or {}

    current_password = data.get("current_password")
    new_password = data.get("new_password")

    if not current_password or not new_password:
        return jsonify({
            "error": "Current password and new password are required"
        }), 400

    if not check_password_hash(
        user.password,
        current_password
    ):
        return jsonify({
            "error": "Current password is incorrect"
        }), 401

    if len(new_password) < 8:
        return jsonify({
            "error": "New password must be at least 8 characters"
        }), 400

    if current_password == new_password:
        return jsonify({
            "error": "New password must be different from current password"
        }), 400

    user.password = generate_password_hash(
        new_password
    )

    db.session.commit()

    return jsonify({
        "message": "Password changed successfully"
    }), 200

@app.route("/confirm/<int:incident_id>", methods=["POST"])
@active_user_required
def confirm_incident(incident_id):

    user_id = int(get_jwt_identity())

    if not user_id:
        return jsonify({
            "message": "User ID is required."
        }), 400

    incident = Incident.query.get(incident_id)

    if incident is None:
        return jsonify({
            "message": "Incident not found."
        }), 404

    existing = IncidentConfirmation.query.filter_by(
        user_id=user_id,
        incident_id=incident_id
    ).first()

    if existing:
        return jsonify({
            "message": "You have already confirmed this incident."
        }), 400

    confirmation = IncidentConfirmation(
        user_id=user_id,
        incident_id=incident_id
    )

    db.session.add(confirmation)

    user = User.query.get(user_id)

    if user.role == "DRIVER":
        incident.verification_count += 1

    elif user.role == "ROAD_OFFICER":
        incident.verification_count += 5
        incident.officially_verified = True

        create_audit_log(
            user_id=user_id,
    action="OFFICIALLY_VERIFIED_INCIDENT",
            target_type="INCIDENT",
            target_id=incident.id,
            details="Incident officially verified by ROAD_OFFICER"
        )

    elif user.role == "ADMIN":
        incident.verification_count += 10
        incident.officially_verified = True

        create_audit_log(
            user_id=user_id,
    action="OFFICIALLY_VERIFIED_INCIDENT",
            target_type="INCIDENT",
            target_id=incident.id,
            details="Incident officially verified by ADMIN"
        )

    if incident.user:
        incident.user.trust_score = min(
            incident.user.trust_score + 2,
            100
        )

    db.session.commit()

    return jsonify({
        "message": "Incident confirmed.",
        "verification_count": incident.verification_count,
        "officially_verified": incident.officially_verified
    })

@app.route("/my-reports", methods=["GET"])
@jwt_required()
def my_reports():

    user_id = int(get_jwt_identity())

    reports = Incident.query.filter_by(
        user_id=user_id
    ).order_by(
        Incident.created_at.desc()
    ).all()

    return jsonify([
        report.to_dict()
        for report in reports
    ]), 200

@app.route("/user/<int:user_id>/reports", methods=["GET"])
def user_reports(user_id):

    user = User.query.get(user_id)

    if user is None:
        return jsonify({
            "error": "User not found"
        }), 404

    reports = Incident.query.filter_by(
        user_id=user_id
    ).order_by(
        Incident.created_at.desc()
    ).all()

    return jsonify([
        report.to_dict()
        for report in reports
    ]), 200

@app.route("/user/<int:user_id>/stats")
def user_stats(user_id):

    user = User.query.get(user_id)

    if user is None:
        return jsonify({
            "error": "User not found"
        }), 404

    reports = Incident.query.filter_by(
        user_id=user_id
    ).all()

    reports_submitted = len(reports)

    reports_confirmed = sum(
        report.verification_count - 1
        for report in reports
    )

    trust_score = user.trust_score

    people_helped = reports_confirmed * 5

    return jsonify({
        "reports_submitted": reports_submitted,
        "reports_confirmed": reports_confirmed,
        "trust_score": trust_score,
        "people_helped": people_helped,
        "reputation": reputation_level(trust_score),
    })

@app.route("/emergency-contacts", methods=["GET"])
@active_user_required
def get_emergency_contacts():
    user_id = int(get_jwt_identity())

    contacts = EmergencyContact.query.filter_by(
        user_id=user_id
    ).order_by(
        EmergencyContact.is_primary.desc(),
        EmergencyContact.id.asc()
    ).all()

    return jsonify([
        contact.to_dict()
        for contact in contacts
    ]), 200


@app.route("/emergency-contacts", methods=["POST"])
@active_user_required
def add_emergency_contact():
    user_id = int(get_jwt_identity())

    data = request.get_json() or {}

    name = data.get("name")
    phone = data.get("phone")
    relationship = data.get("relationship")
    is_primary = data.get("is_primary", False)

    if not name or not phone:
        return jsonify({
            "error": "Name and phone are required"
        }), 400

    # Allow only one primary contact per user.
    if is_primary:
        EmergencyContact.query.filter_by(
            user_id=user_id,
            is_primary=True
        ).update({
            "is_primary": False
        })

    contact = EmergencyContact(
        user_id=user_id,
        name=name,
        phone=phone,
        relationship=relationship,
        is_primary=bool(is_primary)
    )

    db.session.add(contact)
    db.session.commit()

    return jsonify({
        "message": "Emergency contact added successfully",
        "contact": contact.to_dict()
    }), 201


@app.route("/emergency-contacts/<int:contact_id>", methods=["PUT"])
@active_user_required
def update_emergency_contact(contact_id):
    user_id = int(get_jwt_identity())

    contact = EmergencyContact.query.filter_by(
        id=contact_id,
        user_id=user_id
    ).first()

    if not contact:
        return jsonify({
            "error": "Emergency contact not found"
        }), 404

    data = request.get_json() or {}

    name = data.get("name")
    phone = data.get("phone")
    relationship = data.get("relationship")

    if name is not None:
        name = str(name).strip()
        if not name:
            return jsonify({
                "error": "Name cannot be empty"
            }), 400
        contact.name = name

    if phone is not None:
        phone = str(phone).strip()
        if not phone:
            return jsonify({
                "error": "Phone cannot be empty"
            }), 400
        contact.phone = phone

    if relationship is not None:
        contact.relationship = relationship

    if "is_primary" in data:
        is_primary = bool(data["is_primary"])

        if is_primary:
            EmergencyContact.query.filter(
                EmergencyContact.user_id == user_id,
                EmergencyContact.id != contact.id,
                EmergencyContact.is_primary == True
            ).update({
                "is_primary": False
            })

        contact.is_primary = is_primary

    db.session.commit()

    return jsonify({
        "message": "Emergency contact updated successfully",
        "contact": contact.to_dict()
    }), 200


@app.route("/emergency-contacts/<int:contact_id>", methods=["DELETE"])
@active_user_required
def delete_emergency_contact(contact_id):
    user_id = int(get_jwt_identity())

    contact = EmergencyContact.query.filter_by(
        id=contact_id,
        user_id=user_id
    ).first()

    if not contact:
        return jsonify({
            "error": "Emergency contact not found"
        }), 404

    db.session.delete(contact)
    db.session.commit()

    return jsonify({
        "message": "Emergency contact deleted successfully"
    }), 200


# ============================================================
# SOS EMERGENCY SYSTEM
# ============================================================

@app.route("/sos/trigger", methods=["POST"])
@active_user_required
def trigger_sos():
    user_id = int(get_jwt_identity())

    data = request.get_json() or {}

    latitude = data.get("latitude")
    longitude = data.get("longitude")
    emergency_type = data.get("emergency_type", "GENERAL")
    message = data.get("message")

    # Validate GPS coordinates
    try:
        latitude = float(latitude)
        longitude = float(longitude)
    except (TypeError, ValueError):
        return jsonify({
            "error": "Valid latitude and longitude are required"
        }), 400

    if not (-90 <= latitude <= 90):
        return jsonify({
            "error": "Latitude must be between -90 and 90"
        }), 400

    if not (-180 <= longitude <= 180):
        return jsonify({
            "error": "Longitude must be between -180 and 180"
        }), 400

    emergency_type = str(emergency_type).strip().upper()

    allowed_types = [
        "GENERAL",
        "ACCIDENT",
        "MEDICAL",
        "FIRE",
        "SECURITY",
        "BREAKDOWN"
    ]

    if emergency_type not in allowed_types:
        return jsonify({
            "error": "Invalid emergency type",
            "allowed_types": allowed_types
        }), 400

    if message is not None:
        message = str(message).strip()

        if len(message) > 500:
            return jsonify({
                "error": "Message cannot exceed 500 characters"
            }), 400

        if not message:
            message = None

    # Prevent accidental duplicate active SOS events
    existing_sos = SOSEvent.query.filter_by(
        user_id=user_id,
        status="ACTIVE"
    ).first()

    if existing_sos:
        return jsonify({
            "error": "You already have an active SOS",
            "sos": existing_sos.to_dict()
        }), 409

    sos = SOSEvent(
        user_id=user_id,
        latitude=latitude,
        longitude=longitude,
        emergency_type=emergency_type,
        message=message,
        status="ACTIVE"
    )

    db.session.add(sos)
    db.session.commit()

    create_audit_log(
        user_id=user_id,
        action="SOS_TRIGGERED",
        target_type="SOS",
        target_id=sos.id,
        details=f"SOS triggered: {emergency_type}"
    )

    return jsonify({
        "message": "SOS triggered successfully",
        "sos": sos.to_dict()
    }), 201

# ============================================================
# ACTIVE SOS STATUS
# ============================================================

@app.route("/sos/active", methods=["GET"])
@active_user_required
def get_active_sos():
    user_id = int(get_jwt_identity())

    sos = SOSEvent.query.filter_by(
        user_id=user_id,
        status="ACTIVE"
    ).order_by(SOSEvent.created_at.desc()).first()

    if not sos:
        return jsonify({
            "active": False,
            "sos": None
        }), 200

    return jsonify({
        "active": True,
        "sos": sos.to_dict()
    }), 200


# ============================================================
# SOS CANCELLATION
# ============================================================

@app.route("/sos/cancel/<int:sos_id>", methods=["POST"])
@active_user_required
def cancel_sos(sos_id):
    user_id = int(get_jwt_identity())

    sos = SOSEvent.query.filter_by(
        id=sos_id,
        user_id=user_id
    ).first()

    if not sos:
        return jsonify({
            "error": "SOS event not found"
        }), 404

    if sos.status != "ACTIVE":
        return jsonify({
            "error": "SOS is not active",
            "status": sos.status,
            "sos": sos.to_dict()
        }), 409

    sos.status = "CANCELLED"
    sos.cancelled_at = datetime.utcnow()

    db.session.commit()

    create_audit_log(
        user_id=user_id,
        action="SOS_CANCELLED",
        target_type="SOS",
        target_id=sos.id,
        details="SOS cancelled by user"
    )

    return jsonify({
        "message": "SOS cancelled successfully",
        "sos": sos.to_dict()
    }), 200


# ============================================================
# SOS RESOLUTION
# ============================================================

@app.route("/sos/resolve/<int:sos_id>", methods=["POST"])
@incident_resolver_required
def resolve_sos(sos_id):
    current_user_id = int(get_jwt_identity())

    sos = SOSEvent.query.get(sos_id)

    if not sos:
        return jsonify({
            "error": "SOS event not found"
        }), 404

    if sos.status != "ACTIVE":
        return jsonify({
            "error": "SOS is not active",
            "status": sos.status
        }), 409

    data = request.get_json() or {}
    resolution_note = data.get("resolution_note")

    if resolution_note is not None:
        resolution_note = str(resolution_note).strip()

        if len(resolution_note) > 500:
            return jsonify({
                "error": "Resolution note cannot exceed 500 characters"
            }), 400

        if not resolution_note:
            resolution_note = None

    sos.status = "RESOLVED"
    sos.resolved_at = datetime.utcnow()
    sos.resolved_by = current_user_id

    db.session.commit()

    create_audit_log(
        user_id=current_user_id,
        action="SOS_RESOLVED",
        target_type="SOS",
        target_id=sos.id,
        details="SOS resolved by authorized responder"
    )

    return jsonify({
        "message": "SOS resolved successfully",
        "sos": sos.to_dict()
    }), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
