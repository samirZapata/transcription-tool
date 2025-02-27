#!/bin/bash
set -e  # Salir inmediatamente si un comando sale con error no-cero

# Actualizar pip
python3 -m pip install --upgrade pip

# Crear directorios necesarios
mkdir -p uploads

# Instalar dependencias del sistema
sudo apt-get update -y
sudo apt-get install -y ffmpeg python3-dev

# Instalar dependencias de Python
pip install -r requirements.txt

# Inicializar la base de datos (opcional, si lo necesitas)
python3 -c "from database import init_db; init_db()"

# Mostrar información de verificación
echo "Construcción completada exitosamente"
