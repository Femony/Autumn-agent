# --- 1. Use Python image ---
FROM python:3.11-slim

# --- 2. Set working directory ---
WORKDIR /app

# --- 3. Copy dependency file and install ---
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# --- 4. Copy application files ---
COPY . .

# --- 5. Make start script executable ---
RUN chmod +x start.sh

# --- 6. Start the scheduler ---
CMD ["./start.sh"]