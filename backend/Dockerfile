FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt
COPY backend/ backend/
EXPOSE 8123
CMD ["sh", "-ec", "alembic -c backend/alembic.ini upgrade head && python -m backend.scripts.seed && exec uvicorn backend.app.main:create_app --factory --host 0.0.0.0 --port 8123"]
