import time
import requests

# Simulated route (driver moving closer)
route = [
    (6.5200, 3.3700),
    (6.5220, 3.3740),
    (6.5235, 3.3770),
    (6.5242, 3.3788),
    (6.5244, 3.3792),
]

SERVER = "http://127.0.0.1:5000"

print("🚗 SafeRoad AI Driver Simulator Started\n")

for lat, lon in route:

    print(f"Current Location: {lat}, {lon}")

    try:
        response = requests.get(
            f"{SERVER}/nearby",
            params={
                "lat": lat,
                "lon": lon,
                "radius": 2
            }
        )

        incidents = response.json()

        if len(incidents) == 0:
            print("✅ No nearby incidents.\n")

        else:
            for incident in incidents:
                print(f"🚨 {incident['alert']}")
                print(f"Type: {incident['incident_type']}")
                print(f"Distance: {incident['distance_km']} km")
                print(f"Severity: {incident['severity']}")
                print()

    except Exception as e:
        print("Error:", e)

    time.sleep(3)
