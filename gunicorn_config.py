import multiprocessing

# Gunicorn configuration
bind = "0.0.0.0:80"
workers = multiprocessing.cpu_count() * 2 + 1
worker_class = "sync"
worker_connections = 1000
timeout = 300
keepalive = 2

# SSL Configuration (if using SSL directly in Gunicorn)
# keyfile = "path/to/keyfile"
# certfile = "path/to/certfile"
# // if have cert file, Please change this code to your SSL Cert

# Security configurations
limit_request_line = 4096
limit_request_fields = 100
limit_request_field_size = 8190

# Logging
accesslog = "access.log"
errorlog = "error.log"
loglevel = "info"

# Process naming
proc_name = "email_backup"

# Server mechanics
daemon = False
pidfile = "email_backup.pid"
umask = 0
user = None
group = None
tmp_upload_dir = None

# SSL redirect
forwarded_allow_ips = "*"