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

# Copy the application code into the working directory
COPY ./main_agent ./main_agent
COPY ./mcp_config.py ./
COPY ./gunicorn.conf.py ./
COPY ./airavat-a3a10-firebase-adminsdk-fbsvc-7b24d935c3.json ./
COPY .env ./

# Expose the port Gunicorn will run on (Cloud Run will map this)
# Cloud Run provides the PORT env var, Gunicorn will use it by default if not specified in CMD.
EXPOSE 8080 

# Command to run the application using Gunicorn with our configuration
# The gunicorn.conf.py sets the proper PYTHONPATH and other settings
CMD gunicorn -c gunicorn.conf.py main_agent.main:app --bind 0.0.0.0:$PORT 