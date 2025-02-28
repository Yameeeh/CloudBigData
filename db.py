from google.cloud import firestore

db = firestore.Client()

def save_weather_data(latitude, longitude, weather_data):
    doc_ref = db.collection('weather_data').document()
    doc_ref.set({
        'latitude': latitude,
        'longitude': longitude,
        'temperature': weather_data['current_weather']['temperature'],
        'weathercode': weather_data['current_weather']['weathercode'],
        'timestamp': firestore.SERVER_TIMESTAMP
    })