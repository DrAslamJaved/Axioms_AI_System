FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    AXIOMS_DATABASE_URL=sqlite:///data/axioms.sqlite3

WORKDIR /app
COPY pyproject.toml README.md ./
COPY axioms ./axioms
RUN pip install --no-cache-dir .
COPY streamlit_app.py ./
COPY docs ./docs
RUN mkdir -p /app/data

EXPOSE 8000
CMD ["uvicorn", "axioms.api:app", "--host", "0.0.0.0", "--port", "8000"]

