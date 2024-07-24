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

# Définir les variables d'environnement pour utiliser l'environnement virtuel
ENV PATH="/app/venv/bin:$PATH"

# Commande pour lancer l'application
CMD ["gunicorn", "-w", "2", "-k", "uvicorn.workers.UvicornWorker", "main:app", "--bind", "0.0.0.0:8000"]
