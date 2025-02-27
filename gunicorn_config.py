# gunicorn_config.py
bind = "0.0.0.0:10000"
workers = 2
threads = 4
timeout = 300  # 5 minutos para operaciones de larga duración
max_requests = 1000
max_requests_jitter = 50