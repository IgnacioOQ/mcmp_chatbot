# Build from the REPO ROOT so the image can COPY src/ and prompts/.
#   docker build -f firebase/backend/Dockerfile .
FROM python:3.11-slim
WORKDIR /app
COPY firebase/backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY src/ ./src/
COPY prompts/ ./prompts/
COPY firebase/backend/ .
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
