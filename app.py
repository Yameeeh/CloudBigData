from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import requests
from datetime import datetime, timedelta
import os
import time

app = Flask(__name__)
CORS(app)

# Firebase-Konfiguration
firestore_available = False
try:
    from google.cloud import firestore
    # Setze die Umgebungsvariable für den Service-Account-Schlüssel
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "firebase-key.json"
    db = firestore.Client()
    firestore_available = True
except Exception as e:
    print(f"Firestore ist nicht verfügbar: {e}. Die Anwendung wird ohne Firestore ausgeführt.")

def get_weather_from_api(latitude, longitude):
    """Holt stündliche Wetterdaten von der Open-Meteo API."""
    url = f"https://api.open-meteo.com/v1/forecast?latitude={latitude}&longitude={longitude}&hourly=apparent_temperature,rain&forecast_days=1"
    try:
        response = requests.get(url)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error fetching weather data from Open-Meteo: {e}")
        return None

def save_weather_to_firestore(latitude, longitude, weather_data):
    """Speichert Wetterdaten in Firestore und stellt sicher, dass sie gespeichert wurden, bevor sie abgerufen werden."""
    if firestore_available:
        doc_ref = db.collection('weather_cache').document(f"{latitude}_{longitude}")
        doc_ref.set({
            'latitude': latitude,
            'longitude': longitude,
            'hourly_data': weather_data['hourly_data'],
            'timestamp': datetime.utcnow()
        })

        # Ensure the write is finished before proceeding
        retries = 3
        for _ in range(retries):
            doc = doc_ref.get()
            if doc.exists:
                print(f"[INFO] Firestore data successfully saved for {latitude}, {longitude}")
                return
            print("[WARN] Firestore write not finished, retrying...")
        
        print("[ERROR] Firestore data did not save properly!")

def get_weather_from_firestore(latitude, longitude):
    """Holt Wetterdaten aus Firestore, falls verfügbar."""
    if firestore_available:
        doc_ref = db.collection('weather_cache').document(f"{latitude}_{longitude}")
        doc = doc_ref.get()
        if doc.exists:
            # Log the retrieved data to inspect its structure
            print(f"Retrieved data from Firestore: {doc.to_dict()}")
            return doc.to_dict()
    return None

def get_recommendation(hourly_data):
    """Generiert eine Kleidungsempfehlung basierend auf den stündlichen Wetterdaten."""
    if hourly_data is None:
        return "Fehler bei der Verarbeitung der Wetterdaten."

    try:
        apparent_temperatures = hourly_data['apparent_temperature']
        rain = hourly_data['rain']
        timestamps = hourly_data['time']

        # Betrachte die nächsten 12 Stunden
        relevant_temperatures = apparent_temperatures[:12]
        relevant_rain = rain[:12]

        avg_apparent_temperature = sum(relevant_temperatures) / len(relevant_temperatures)
        max_rain = max(relevant_rain)

        if avg_apparent_temperature < 10:
            temp_recommendation = "Ziehen Sie sich warm an."
        else:
            temp_recommendation = "Sie können sich leicht anziehen."

        if max_rain >= 2:
            rain_recommendation = "Nehmen Sie einen Regenschirm mit."
        elif 0 < max_rain < 2:
            rain_recommendation = "Leichter Regen unter 2mm. Regenschirm empfohlen."
        else:
            rain_recommendation = "Es regnet nicht, kein Schirm nötig."

        return f"{temp_recommendation} {rain_recommendation}"
    except Exception as e:
        print(f"Error generating recommendation: {e}")
        return "Fehler bei der Empfehlung. Überprüfen Sie die Daten."

@app.route('/')
def index():
    """Serve the homepage (index.html)."""
    return render_template('index.html')

@app.route('/recommendation', methods=['GET'])
def recommendation():
    """Hauptendpunkt für die Kleidungsempfehlung."""
    try:
        # Hol die Parameter und konvertiere sie in Float
        try:
            latitude = float(request.args.get('latitude'))
            longitude = float(request.args.get('longitude'))
        except (TypeError, ValueError):
            return jsonify({"error": "Breitengrad und Längengrad müssen gültige Zahlen sein."}), 400

        # Prüfe, ob die Daten bereits in Firestore sind
        cached_weather = get_weather_from_firestore(latitude, longitude)

        if cached_weather:
            print("[INFO] Using cached weather data.")
            weather_data = cached_weather
        else:
            print("[INFO] No cache found. Fetching from API.")
            weather_data = get_weather_from_api(latitude, longitude)

            if weather_data and "hourly" in weather_data:  # Fix für Open-Meteo API
                weather_data["hourly_data"] = weather_data["hourly"]  # Konsistenz
                save_weather_to_firestore(latitude, longitude, weather_data)
                time.sleep(1)  # Warten auf Firestore-Speicherung

                # Sicherstellen, dass Firestore die Daten gespeichert hat
                cached_weather = None
                for _ in range(3):  
                    cached_weather = get_weather_from_firestore(latitude, longitude)
                    if cached_weather:
                        print("[INFO] Successfully retrieved saved data from Firestore.")
                        weather_data = cached_weather
                        break
                    print("[WARN] Firestore write not finished, retrying...")
                    time.sleep(1)

                if not cached_weather:
                    print("[ERROR] Firestore did not save weather data properly.")
                    return jsonify({"error": "Fehler beim Speichern der Wetterdaten."}), 500
            else:
                print("[ERROR] Could not fetch weather data from API.")
                return jsonify({"error": "Wetterdaten konnten nicht abgerufen werden."}), 500

        # Prüfen, ob "hourly_data" existiert
        if "hourly_data" not in weather_data:
            print(f"[ERROR] Weather data missing 'hourly_data' key: {weather_data}")
            return jsonify({"error": "Ungültige Wetterdaten."}), 500

        # Generiere die Kleidungsempfehlung
        recommendation = get_recommendation(weather_data['hourly_data'])
        return jsonify({"recommendation": recommendation})

    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"[ERROR] Serverfehler: {e}\n{error_details}")
        return jsonify({"error": f"Serverfehler: {str(e)}"}), 500



if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)