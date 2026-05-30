bind = "0.0.0.0:80"
workers = 2
worker_class = "sync"
timeout = 120
max_requests = 1000
preload_app = True
errorlog = "/var/log/banaaiq/error.log"
accesslog = "/var/log/banaaiq/access.log"
