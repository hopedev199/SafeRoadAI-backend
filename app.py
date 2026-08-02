import math

from flask import Flask, jsonify, request
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
from models import db, Incident, User

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
app = Flask(__name__)

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
def report_incident():

    data = request.get_json()

    incident = Incident(
        incident_type=data["incident_type"],
        description=data.get("description"),
        latitude=data["latitude"],
        longitude=data["longitude"],
        reporter=data.get("reporter"),
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
def login():

    data = request.get_json()

    user = User.query.filter_by(username=data["username"]).first()

    if not user:
        return jsonify({"error": "Invalid username or password"}), 401

    if not check_password_hash(user.password, data["password"]):
        return jsonify({"error": "Invalid username or password"}), 401

    return jsonify({
        "message": "Login successful",
        "user": user.to_dict()
    })

@app.route("/confirm/<int:incident_id>", methods=["POST"])
def confirm_incident(incident_id):

    incident = Incident.query.get(incident_id)

    if incident is None:
        return jsonify({
            "message": "Incident not found."
        }), 404

    incident.verification_count += 1

    db.session.commit()

    return jsonify({
        "message": "Incident confirmed.",
        "verification_count": incident.verification_count
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
