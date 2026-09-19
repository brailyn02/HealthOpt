FROM python:3.11-slim

WORKDIR /app

COPY requirement.txt .
RUN python -m pip install --upgrade pip && pip install -r requirement.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000"]
