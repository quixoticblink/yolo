# Backend Dockerfile
FROM python:3.11-slim

# Install system dependencies including curl for model download
RUN apt-get update && apt-get install -y \
    poppler-utils \
    libgl1 \
    libglib2.0-0 \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir pdf2image opencv-python-headless

# Pre-download EasyOCR models to cache them in the image
RUN python3 -c "import easyocr; easyocr.Reader(['en'], gpu=False)"

# Copy model download script first (separate layer for caching)
COPY download_models.sh .
RUN chmod +x download_models.sh

# Download P&ID detection models from AWS GitHub releases
# This avoids storing large model files (~1.4GB) in git
RUN ./download_models.sh /app/models

# Copy application code (models are .dockerignore'd, we downloaded them above)
COPY . .

# Create storage directories
RUN mkdir -p storage/documents storage/rendered storage/symbols

# Environment
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
