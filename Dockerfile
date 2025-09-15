FROM python:3.11-slim

WORKDIR /app

# Instalar dependências básicas
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

# Copiar e instalar requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar código da aplicação
COPY . .

# Instalar gunicorn separadamente
RUN pip install gunicorn

# Definir PYTHONPATH
ENV PYTHONPATH=/app

# Expor porta
EXPOSE 5000

# Comando simples
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "backend.app:app"]



