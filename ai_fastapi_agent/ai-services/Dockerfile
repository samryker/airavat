# Use an official Python runtime as a parent image
FROM python:3.10-slim

# Set environment variables
# Prevents Python from writing pyc files to disc (equivalent to python -B)
ENV PYTHONDONTWRITEBYTECODE 1
# Prevents Python from buffering stdout and stderr (equivalent to python -u)
ENV PYTHONUNBUFFERED 1

# Set the working directory in the container
WORKDIR /app

# Install pip requirements
# Copy requirements first to leverage Docker cache
COPY requirements.txt ./
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code into the working directory
# This assumes your Dockerfile is in the 'ai-services' directory and your app code is in 'main_agent' subdir.
COPY ./main_agent ./main_agent
# If you have other necessary directories at the same level as main_agent (e.g., a shared 'common' lib), copy them too.
# COPY ./common ./common 

# Expose the port Gunicorn will run on (Cloud Run will map this)
# Cloud Run provides the PORT env var, Gunicorn will use it by default if not specified in CMD.
EXPOSE 8080 

# Command to run the application using Gunicorn
# The path to the app is main_agent.main:app because WORKDIR is /app
# We copied main_agent folder into /app, so it becomes /app/main_agent/main.py
# Gunicorn needs number of workers. A common practice is (2 x $cores) + 1.
# For Cloud Run, you can start with a reasonable number like 2-4 workers.
# UvicornWorker is specified for FastAPI.
# The PORT environment variable is automatically supplied by Cloud Run.
CMD gunicorn -w 2 -k uvicorn.workers.UvicornWorker main_agent.main:app --bind 0.0.0.0:$PORT 