# Gunicorn configuration for api_cyber

bind = "0.0.0.0:6950"
workers = 4
worker_class = "uvicorn.workers.UvicornWorker"
timeout = 120
keepalive = 5
errorlog = "/var/log/api_cyber/gunicorn_error.log"
accesslog = "/var/log/api_cyber/gunicorn_access.log"
loglevel = "info"
