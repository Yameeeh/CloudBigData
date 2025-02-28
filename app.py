from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
from datetime import datetime, timedelta
import os

app = Flask(__name__)
CORS(app)  # CORS aktivieren

# Firebase-Konfiguration
firestore_available = False
try:
    from google.cloud import firestore
    # Setze die Umgebungsvariable für den Service-Account-Schlüssel
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "firebase-key.json"  # Pfad zur JSON-Datei
    db = firestore.Client()
    firestore_available = True
except Exception as e:
    print(f"Firestore ist nicht verfügbar: {e}. Die Anwendung wird ohne Firestore ausgeführt.")

def get_weather_from_api(latitude, longitude):
    """Holt stündliche Wetterdaten von der Open-Meteo API."""
    url = f"https://api.open-meteo.com/v1/forecast?latitude={latitude}&longitude={longitude}&hourly=apparent_temperature,rain&forecast_days=1"
    response = requests.get(url)
    return response.json()

def save_weather_to_firestore(latitude, longitude, weather_data):
    """Speichert Wetterdaten in Firestore, falls verfügbar."""
    if firestore_available:
        doc_ref = db.collection('weather_cache').document(f"{latitude}_{longitude}")
        doc_ref.set({
            'latitude': latitude,
            'longitude': longitude,
            'hourly_data': weather_data['hourly'],
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

def get_recommendation(hourly_data):
    """Generiert eine Kleidungsempfehlung basierend auf den stündlichen Wetterdaten."""
    apparent_temperatures = hourly_data['apparent_temperature']
    rain = hourly_data['rain']
    timestamps = hourly_data['time']

    # Betrachte die nächsten 12 Stunden
    relevant_temperatures = apparent_temperatures[:12]
    relevant_rain = rain[:12]

    # Durchschnittliche gefühlte Temperatur und maximale Regenmenge in den nächsten 12 Stunden
    avg_apparent_temperature = sum(relevant_temperatures) / len(relevant_temperatures)
    max_rain = max(relevant_rain)

    # Empfehlung basierend auf der gefühlten Temperatur
    if avg_apparent_temperature < 10:
        temp_recommendation = "Ziehen Sie sich warm an."
    else:
        temp_recommendation = "Sie können sich leicht anziehen."

    # Empfehlung basierend auf Regen
    if max_rain >= 2:
        rain_recommendation = "Nehmen Sie einen Regenschirm mit."
    elif 0 < max_rain < 2:
        rain_recommendation = "Leichter Regen unter 2mm. Regenschirm empfohlen"
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

    # Überprüfe, ob die Daten bereits in Firestore gespeichert sind
    cached_weather = get_weather_from_firestore(latitude, longitude)

    if cached_weather:
        # Verwende die zwischengespeicherten Daten
        weather_data = cached_weather
    else:
        # Hole die Daten von der API und speichere sie in Firestore
        weather_data = get_weather_from_api(latitude, longitude)
        save_weather_to_firestore(latitude, longitude, weather_data)

    # Generiere die Kleidungsempfehlung
    recommendation = get_recommendation(weather_data['hourly'])
    return jsonify({"recommendation": recommendation})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)