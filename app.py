import math

from flask import Flask, jsonify, request
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
from models import (
    db,
    Incident,
    User,
    IncidentConfirmation,
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

app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///saferoad.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db.init_app(app)

with app.app_context():
    db.create_all()

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

@app.route("/")
def home():
    return jsonify({
        "project": "SafeRoad AI",
        "status": "Backend Running",
        "database": "Connected"
    })

@app.route("/report", methods=["POST"])
@jwt_required()
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
        return jsonify({"error": "Invalid username or password"}), 401

    if not check_password_hash(user.password, data["password"]):
        return jsonify({"error": "Invalid username or password"}), 401

    access_token = create_access_token(
        identity=str(user.id)
    )

    return jsonify({
        "message": "Login successful",
        "token": access_token,
        "user": user.to_dict()
    })

@app.route("/confirm/<int:incident_id>", methods=["POST"])
@jwt_required()
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

    incident.verification_count += 1

    if incident.user:
        incident.user.trust_score = min(
            incident.user.trust_score + 2,
            100
        )

    db.session.commit()

    return jsonify({
        "message": "Incident confirmed.",
        "verification_count": incident.verification_count
    })

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

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
