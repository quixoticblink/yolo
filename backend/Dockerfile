# Backend Dockerfile
FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    poppler-utils \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir pdf2image opencv-python-headless

# Pre-download EasyOCR models to cache them in the image
RUN python3 -c "import easyocr; easyocr.Reader(['en'], gpu=False)"

# Copy application code (including models filtered by .dockerignore)
COPY . .

# Create storage directories
RUN mkdir -p storage/documents storage/rendered storage/symbols models

# Environment
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
