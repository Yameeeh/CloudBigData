FROM python:3.9-slim  
# Basis-Image mit Python 3.9

WORKDIR /app  
#Arbeitsverzeichnis im Container

# Kopiere den Service-Account-Schlüssel
COPY firebase-key.json .

# Kopiere die requirements.txt
COPY requirements.txt .
RUN pip install -r requirements.txt  
# Installiere die Abhängigkeiten

COPY . .  
# Kopiere den gesamten Code in das Arbeitsverzeichnis

# Setze die Umgebungsvariable für den Service-Account-Schlüssel
ENV GOOGLE_APPLICATION_CREDENTIALS="/app/firebase-key.json"

CMD ["python", "app.py"]  
# Starte das Backend