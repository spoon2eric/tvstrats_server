FROM python:3.10-slim

WORKDIR /usr/src/app

# Copy just the requirements.txt file and install the Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# If your application doesn't need SQLite3, you can remove the apt-get commands
# RUN apt-get update && \
#     apt-get install -y sqlite3 && \
#     rm -rf /var/lib/apt/lists/*

# Copy the rest of your application code
COPY . .

# Consider creating a user to run your application
# RUN useradd -m myuser
# USER myuser

CMD ["python", "./main.py"]
