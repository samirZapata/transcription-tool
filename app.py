#app.py

from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, make_response
import os
import shutil
import traceback
from werkzeug.utils import secure_filename
from database import init_db, save_transcription, get_all_transcriptions, get_transcription_by_id, clear_all_transcriptions
from transcription import transcribir_video_youtube, procesar_archivo_local, set_progress_callback, limpiar_archivos_temporales
import time
import threading

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'your_secret_key')
app.config['UPLOAD_FOLDER'] = os.environ.get('UPLOAD_FOLDER', 'uploads')
app.config['MAX_CONTENT_LENGTH'] = 32 * 1024 * 1024  # 32 MB

ALLOWED_EXTENSIONS = {'mp3', 'wav', 'ogg', 'opus', 'm4a'}

if not os.path.exists(app.config['UPLOAD_FOLDER']):
   os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Variables globales para el seguimiento del progreso
progress_data = {
    'percentage': 0,
    'status': 'Iniciando',
    'time_remaining': 'Calculando...',
    'is_processing': False
}

# Semáforo para evitar transcripciones simultáneas
processing_lock = threading.Lock()

def update_progress(percentage, status, time_remaining):
    """Actualiza los datos de progreso de transcripción"""
    global progress_data
    progress_data['percentage'] = percentage
    progress_data['status'] = status
    progress_data['time_remaining'] = time_remaining

# Configurar la función de callback en el módulo de transcripción
set_progress_callback(update_progress)

def allowed_file(filename):
   """Verifica si un archivo tiene una extensión permitida"""
   return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/', methods=['GET', 'POST'])
def index():
    """Ruta principal - muestra la interfaz y maneja acciones especiales"""
    # Manejar la limpieza de transcripciones
    if request.method == 'POST' and request.args.get('clear') == 'true':
        clear_all_transcriptions()
        return redirect(url_for('index'))
        
    # Manejar descarga de transcripción
    if request.args.get('download'):
        transcription_id = request.args.get('download')
        transcription = get_transcription_by_id(transcription_id)
        
        if transcription:
            response = make_response(transcription['content'])
            response.headers['Content-Disposition'] = f'attachment; filename=transcripcion_{transcription_id}.txt'
            response.headers['Content-Type'] = 'text/plain; charset=utf-8'
            return response
            
    # Mostrar página principal
    transcriptions = get_all_transcriptions()
    return render_template('index.html', transcriptions=transcriptions)

@app.route('/upload', methods=['POST'])
def upload_file():
    """Maneja subida de archivos o URLs para transcripción"""
    global progress_data
    
    # Verificar si ya hay una transcripción en proceso
    if progress_data['is_processing'] and progress_data['percentage'] > 0 and progress_data['percentage'] < 100:
        return jsonify({
            'success': False,
            'message': 'Ya hay una transcripción en proceso. Por favor espere.'
        })
    
    # Adquirir el semáforo para evitar procesamiento simultáneo
    if not processing_lock.acquire(blocking=False):
        return jsonify({
            'success': False,
            'message': 'El servidor está ocupado procesando otra solicitud.'
        })
    
    try:
        # Marcar como en proceso y reiniciar progreso
        progress_data['is_processing'] = True
        update_progress(0, "Iniciando", "Calculando...")
        
        # Verificar datos de entrada
        if 'file' not in request.files and not request.form.get('youtube_url'):
            progress_data['is_processing'] = False
            return jsonify({
                'success': False,
                'message': 'Proporcione un archivo o URL'
            })

        resultado = None
        
        # Procesar archivo subido
        if 'file' in request.files:
            file = request.files['file']
            if file and file.filename and allowed_file(file.filename):
                # Crear un directorio temporal único para este archivo
                temp_dir = os.path.join(app.config['UPLOAD_FOLDER'], f"upload_{int(time.time())}")
                os.makedirs(temp_dir, exist_ok=True)
                
                # Guardar archivo con nombre seguro
                filename = secure_filename(file.filename)
                filepath = os.path.join(temp_dir, filename)
                file.save(filepath)
                
                try:
                    # Procesar el archivo
                    resultado = procesar_archivo_local(filepath)
                    if resultado:
                        save_transcription(filename, resultado, 'archivo')
                finally:
                    # Limpiar archivos temporales
                    try:
                        if os.path.exists(temp_dir):
                            shutil.rmtree(temp_dir, ignore_errors=True)
                    except Exception as e:
                        print(f"No se pudo eliminar directorio temporal: {str(e)}")
                   
        # Procesar URL de YouTube
        elif request.form.get('youtube_url'):
            url = request.form['youtube_url']
            if not url.strip():
                progress_data['is_processing'] = False
                return jsonify({
                    'success': False,
                    'message': 'URL de YouTube vacía'
                })
               
            resultado = transcribir_video_youtube(url)
            if resultado:
                save_transcription(url, resultado, 'youtube')

        # Finalizar y devolver resultado
        if resultado:
            update_progress(100, "Transcripción completada", "Finalizado")
            return jsonify({
                'success': True,
                'text': resultado,
                'message': 'Transcripción completada exitosamente'
            })
        
        # Error genérico
        progress_data['is_processing'] = False
        return jsonify({
            'success': False,
            'message': 'Error en la transcripción'
        })

    except Exception as e:
        # Capturar y reportar errores
        error_trace = traceback.format_exc()
        print(f"Error en upload_file: {error_trace}")
        update_progress(0, f"Error: {str(e)}", "Detenido")
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        })
    finally:
        # Liberar el semáforo y marcar como no procesando cuando termine
        progress_data['is_processing'] = False
        processing_lock.release()

@app.route('/progress')
def get_progress():
    """Devuelve información sobre el progreso actual"""
    # Agregar headers para evitar caché
    response = jsonify(progress_data)
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

@app.route('/status')
def get_status():
    """Verifica si el servidor está disponible"""
    return jsonify({'status': 'ok'})

def limpiar_archivos_anteriores():
    """Limpia archivos temporales al iniciar la aplicación"""
    try:
        limpiar_archivos_temporales()
    except Exception as e:
        print(f"Error al limpiar archivos: {str(e)}")

# Punto de entrada para ejecución directa
if __name__ == '__main__':
   # Inicializar la base de datos
   init_db()
   
   # Limpiar archivos temporales
   limpiar_archivos_anteriores()
   
   # Usar puerto de Render si está disponible
   port = int(os.environ.get('PORT', 5000))
   app.run(host='0.0.0.0', port=port, debug=False)