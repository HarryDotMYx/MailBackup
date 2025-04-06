import multiprocessing
import os

# Server socket settings
bind = "127.0.0.1:8000"  # Changed to localhost for Windows
workers = multiprocessing.cpu_count() * 2 + 1
threads = 4
worker_class = "gthread"
worker_connections = 1000
backlog = 2048

# Timeout settings
timeout = 300
keepalive = 5
graceful_timeout = 120

# Logging
accesslog = os.path.join("logs", "access.log")  # Windows-compatible path
errorlog = os.path.join("logs", "error.log")    # Windows-compatible path
loglevel = "info"
access_log_format = '%({x-real-ip}i)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s"'
capture_output = True

# Process naming
proc_name = "email_backup"
pidfile = os.path.join("run", "email_backup.pid")  # Windows-compatible path

# Security
limit_request_line = 4096
limit_request_fields = 100
limit_request_field_size = 8190

# SSL Configuration (if using SSL)
# keyfile = "path/to/keyfile"
# certfile = "path/to/certfile"
# ca_certs = "path/to/ca_certs"
# ssl_version = "TLS"

# Server mechanics
daemon = False
raw_env = [
    'DJANGO_SETTINGS_MODULE=config.settings.production',
]
user = None
group = None
tmp_upload_dir = None
umask = 0o007

# Startup hooks
def on_starting(server):
    # Create required directories
    os.makedirs("logs", exist_ok=True)
    os.makedirs("run", exist_ok=True)

def post_fork(server, worker):
    server.log.info("Worker spawned (pid: %s)", worker.pid)

def pre_fork(server, worker):
    pass

def pre_exec(server):
    server.log.info("Forked child, re-executing.")

def when_ready(server):
    server.log.info("Server is ready. Spawning workers")

def worker_int(worker):
    worker.log.info("worker received INT or QUIT signal")

def worker_abort(worker):
    worker.log.info("worker received SIGABRT signal")