FROM python:3.10-slim

WORKDIR /usr/src/app

COPY requirements.txt .

# Use apt-get instead of apk for Debian-based images
RUN apt-get update && \
    apt-get install -y sqlite3 && \
    rm -rf /var/lib/apt/lists/* && \
    # Combine the pip install commands
    pip install --no-cache-dir -r requirements.txt watchdog==3.0.0

COPY . .

CMD ["python", "./main.py"]
