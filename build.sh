#!/usr/bin/env bash
# Script de construcción para Render

# Salir en caso de error
set -o errexit

# Actualizar e instalar dependencias del sistema
apt-get update -y
apt-get install -y ffmpeg python3-dev

# Crear directorios necesarios
mkdir -p uploads
chmod -R 777 uploads

# Instalar dependencias de Python
pip install --upgrade pip
pip install -r requirements.txt

# Inicializar la base de datos
python -c "from database import init_db; init_db()"