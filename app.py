from flask import Flask, jsonify, request
from werkzeug.security import generate_password_hash, check_password_hash
from models import db, Incident, User

app = Flask(__name__)

app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///saferoad.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db.init_app(app)

with app.app_context():
    db.create_all()

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
        reporter=data.get("reporter")
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


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
