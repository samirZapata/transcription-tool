import os

port = os.environ.get("PORT", "5000")  # Si no está, usa 5000 por defecto
bind = f"0.0.0.0:{port}"

workers = 2
threads = 4
timeout = 300
max_requests = 1000
max_requests_jitter = 50
