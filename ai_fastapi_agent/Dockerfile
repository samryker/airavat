FROM python:3.10-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=8080

# Set the working directory in the container
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first to leverage Docker cache
COPY ai-services/requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy the application code
COPY ai-services/ ./ai-services/
COPY ai-services/mcp_config.py ./

# Copy Firebase configuration
COPY firebase.json ./firebase.json

# Create a non-root user for security
RUN useradd --create-home --shell /bin/bash app && \
    chown -R app:app /app
USER app

# Expose the port
EXPOSE 8080

# Command to run the application
CMD ["uvicorn", "--app-dir", "ai-services", "main_agent.main:app", "--host", "0.0.0.0", "--port", "8080"] 