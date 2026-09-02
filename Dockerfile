FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 APP_ENV=production
WORKDIR /app
RUN addgroup --system pcp && adduser --system --ingroup pcp pcp
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN mkdir -p /app/instance && chown -R pcp:pcp /app
USER pcp
EXPOSE 5000
CMD ["sh", "-c", "flask --app app db upgrade && flask --app app seed && gunicorn --bind 0.0.0.0:5000 --workers 2 --threads 4 app:app"]
