FROM python:3.12-slim

WORKDIR /app

COPY requirements-docker.txt .
RUN pip install --no-cache-dir -r requirements-docker.txt

COPY . .

ENV FLASK_APP=run.py
ENV DATABASE_URL=sqlite:///app.db
ENV SECRET_KEY=changeme

EXPOSE 5000

CMD ["flask", "run", "--host=0.0.0.0", "--port=5000"]
