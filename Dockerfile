# 1. Use a lightweight Python image
FROM python:3.11-slim

# 2. Set the working directory inside the container
WORKDIR /app

# 3. Copy only the requirements file first (this caches dependencies to speed up future builds)
COPY requirements.txt .

# 4. Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# 5. Copy the rest of the application code
COPY . .

# 6. Expose the port Gunicorn will run on
EXPOSE 8000

# 7. Start Gunicorn (4 workers listening on port 8000)
CMD ["gunicorn", "-w", "1", "-b", "0.0.0.0:8000", "app:app"]
