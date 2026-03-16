FROM python:3.11-slim

WORKDIR /app

# System deps needed by PyMuPDF
RUN apt-get update && apt-get install -y --no-install-recommends \
    libmupdf-dev \
    libfreetype6-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source
COPY backend/ ./
COPY frontend/ ./frontend/

# Create uploads dir
RUN mkdir -p uploads

EXPOSE 8000

CMD ["python", "main.py"]
