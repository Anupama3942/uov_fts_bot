FROM python:3.10-slim

WORKDIR /app

# Prevent python from writing pyc to disk and buffering stdout
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Environment variables should be supplied at runtime (Docker run / Compose / Heroku / Render)
CMD ["python", "bot.py"]