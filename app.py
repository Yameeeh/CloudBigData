from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
from datetime import datetime

app = Flask(__name__)
CORS(app)  # CORS aktivieren

# Firestore-Client initialisieren (nur wenn Anmeldeinformationen verfügbar sind)
firestore_available = False
try:
    from google.cloud import firestore
    db = firestore.Client()
    firestore_available = True
except Exception as e:
    print(f"Firestore ist nicht verfügbar: {e}. Die Anwendung wird ohne Firestore ausgeführt.")

def get_weather_from_api(latitude, longitude):
    """Holt Wetterdaten von der Open-Meteo API."""
    url = f"https://api.open-meteo.com/v1/forecast?latitude={latitude}&longitude={longitude}&current_weather=true"
    response = requests.get(url)
    return response.json()

def save_weather_to_firestore(latitude, longitude, weather_data):
    """Speichert Wetterdaten in Firestore, falls verfügbar."""
    if firestore_available:
        doc_ref = db.collection('weather_cache').document(f"{latitude}_{longitude}")
        doc_ref.set({
            'latitude': latitude,
            'longitude': longitude,
            'temperature': weather_data['current_weather']['temperature'],
            'weathercode': weather_data['current_weather']['weathercode'],
            'timestamp': datetime.utcnow()  # Aktueller Zeitstempel
        })
    else:
        print("Firestore ist nicht verfügbar. Daten werden nicht gespeichert.")

def get_weather_from_firestore(latitude, longitude):
    """Holt Wetterdaten aus Firestore, falls verfügbar."""
    if firestore_available:
        doc_ref = db.collection('weather_cache').document(f"{latitude}_{longitude}")
        doc = doc_ref.get()
        if doc.exists:
            return doc.to_dict()
    return None

def get_recommendation(weather_data):
    """Generiert eine Kleidungsempfehlung basierend auf den Wetterdaten."""
    temperature = weather_data['temperature']
    weathercode = weather_data['weathercode']

    if temperature < 10:
        temp_recommendation = "Ziehen Sie sich warm an."
    else:
        temp_recommendation = "Sie können sich leicht anziehen."

    if weathercode in [61, 63, 65, 80, 81, 82]:
        rain_recommendation = "Nehmen Sie einen Regenschirm mit."
    else:
        rain_recommendation = "Es regnet nicht, kein Schirm nötig."

    return f"{temp_recommendation} {rain_recommendation}"

@app.route('/recommendation', methods=['GET'])
def recommendation():
    """Hauptendpunkt für die Kleidungsempfehlung."""
    latitude = request.args.get('latitude')
    longitude = request.args.get('longitude')

    if not latitude or not longitude:
        return jsonify({"error": "Breitengrad und Längengrad sind erforderlich."}), 400

    # Hole die Daten von der API
    weather_data = get_weather_from_api(latitude, longitude)

    # Speichere die Daten in Firestore, falls verfügbar
    save_weather_to_firestore(latitude, longitude, weather_data['current_weather'])

    # Generiere die Kleidungsempfehlung
    recommendation = get_recommendation(weather_data['current_weather'])
    return jsonify({"recommendation": recommendation})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)