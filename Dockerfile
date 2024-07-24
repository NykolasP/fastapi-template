FROM python:3.8-slim

# Créer un répertoire de travail
WORKDIR /app

# Copier le fichier requirements.txt
COPY requirements.txt .

# Installer les dépendances dans un environnement virtuel
RUN python -m venv /app/venv
RUN . /app/venv/bin/activate
RUN pip install --no-cache-dir -r requirements.txt
# Copier le reste du code de l'application
COPY . .


# Commande pour lancer l'application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
