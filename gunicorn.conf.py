# Configuração do Gunicorn para Render
import os

bind = f"0.0.0.0:{os.environ.get('PORT', '5000')}"
workers = 1  # Single worker to prevent duplicate message processing
worker_class = "sync"
timeout = 120
keepalive = 2
max_requests = 1000
max_requests_jitter = 100
preload_app = True
