import sys
import os
from pathlib import Path

# Add the current directory to Python path
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

# Gunicorn configuration
# Use PORT environment variable (Cloud Run provides this) or default to 8000
port = int(os.environ.get("PORT", 8000))
bind = f"0.0.0.0:{port}"
workers = 1  # Reduced for Cloud Run
worker_class = "uvicorn.workers.UvicornWorker"
worker_connections = 1000
timeout = 300
keepalive = 2
max_requests = 1000
max_requests_jitter = 50
preload_app = True

# Set environment variables for workers
raw_env = [
    f"PYTHONPATH={current_dir}",
]

def on_starting(server):
    """Called just after the server is started."""
    print(f"🚀 Starting Airavat Medical Agent API on {bind}")
    print(f"📁 Working directory: {os.getcwd()}")
    print(f"🐍 Python path: {current_dir}")
    print(f"🌐 Port: {port}")

def when_ready(server):
    """Called just after the server is started and all workers are spawned."""
    print("✅ Gunicorn server is ready to accept connections")

def worker_int(worker):
    """Called when a worker receives SIGINT or SIGQUIT."""
    print(f"🔄 Worker {worker.pid} received SIGINT/SIGQUIT")

def worker_abort(worker):
    """Called when a worker receives SIGABRT."""
    print(f"💥 Worker {worker.pid} received SIGABRT")

def post_worker_init(worker):
    """Called just after a worker has initialized the application."""
    print(f"🔧 Worker {worker.pid} initialized with PYTHONPATH: {os.environ.get('PYTHONPATH', 'not set')}")

def worker_exit(server, worker):
    """Called when a worker exits."""
    print(f"👋 Worker {worker.pid} exited") 