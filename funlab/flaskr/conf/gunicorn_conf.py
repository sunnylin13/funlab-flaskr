# This configuration file is used by Gunicorn to start your application
import multiprocessing
# Gunicorn configuration
bind = "0.0.0.0:5000"  # IP address and port to bind Gunicorn server
# Use multiple workers for better concurrency
workers = multiprocessing.cpu_count() * 2 + 1
# Set the worker class based on your application's requirements
worker_class = "gevent"
# Configure the number of threads per worker
threads = 2
# Maximum number of simultaneous clients per worker
worker_connections = 1000
# Maximum time (in seconds) a worker can spend handling a request
timeout = 30
# Enable graceful handling of worker reloads/restarts
graceful_timeout = 10
# Maximum number of requests a worker will handle before it's restarted
max_requests = 1000
# Log configuration
# Log to stdout for easy integration with log aggregators (e.g., systemd, Docker)
accesslog = '-'
errorlog = '-'
# Set the log level to capture sufficient information for debugging and monitoring
loglevel = 'info'
# Application-specific configuration
# Additional environment variables or custom settings specific to your application
# Example: additional_env = {'MY_APP_SETTINGS': 'production'}
# env = {**env, **additional_env}
