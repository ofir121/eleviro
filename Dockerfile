# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set the working directory in the container
WORKDIR /app

# Set environment variables
# Pythondontwritebytecode: Prevents Python from writing pyc files to disc
# Pythonunbuffered: Prevents Python from buffering stdout and stderr
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install system dependencies: Tesseract OCR for PDF parsing (scanned/image text)
RUN apt-get update && apt-get install -y --no-install-recommends tesseract-ocr && rm -rf /var/lib/apt/lists/*

# Copy the requirements file into the container
COPY requirements.txt .

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .

# Create the uploads directory
RUN mkdir -p uploads

# Expose the port that the app runs on
EXPOSE 8000

# Define the command to run the application
# Using $PORT environment variable for compatibility with platforms like Render/Heroku
CMD uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}
