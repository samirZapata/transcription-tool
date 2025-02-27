#transcription.py
import yt_dlp
import speech_recognition as sr
from pydub import AudioSegment
import os
import numpy as np
from pydub.effects import normalize
import time
import uuid
import random
import gc
import tempfile
import shutil
import sys
import traceback

# Función para actualizar progreso (esta será importada desde app.py)
update_progress = None

def set_progress_callback(callback_function):
    """Establece la función de callback para actualizar el progreso"""
    global update_progress
    update_progress = callback_function

def descargar_audio(url_video):
    """Descarga audio de YouTube con nombre único"""
    if update_progress:
        update_progress(5, "Iniciando descarga de YouTube", "Calculando...")
    
    # Crear un directorio temporal específico para esta descarga
    temp_dir = os.path.join('uploads', f'yt_{uuid.uuid4().hex}')
    os.makedirs(temp_dir, exist_ok=True)
    
    # Nombre aleatorio para evitar conflictos
    nombre_archivo = f"audio_{uuid.uuid4().hex}"
    
    opciones_yt = {
        'format': 'bestaudio/best',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'outtmpl': os.path.join(temp_dir, f'{nombre_archivo}'),
        'verbose': False,
        'quiet': True,
        'no_warnings': True,
        'ignoreerrors': False,
        'noplaylist': True,
    }
    
    try:
        with yt_dlp.YoutubeDL(opciones_yt) as ydl:
            if update_progress:
                update_progress(10, "Descargando audio", "Puede tomar unos minutos...")
            
            error_code = ydl.download([url_video])
            if error_code != 0:
                raise Exception("Error en la descarga del video")
            
            if update_progress:
                update_progress(15, "Descarga completada", "Procesando audio...")
        
        # Buscar el archivo descargado
        archivos = os.listdir(temp_dir)
        if not archivos:
            raise Exception("No se encontró el archivo descargado")
        
        # Devolver la ruta del archivo MP3
        for archivo in archivos:
            if archivo.endswith('.mp3'):
                return os.path.join(temp_dir, archivo), temp_dir
        
        raise Exception("No se encontró un archivo MP3 después de la descarga")
    except Exception as e:
        # Limpiar directorio en caso de error
        try:
            shutil.rmtree(temp_dir, ignore_errors=True)
        except:
            pass
        raise Exception(f"Error en la descarga: {str(e)}")

def mejorar_audio(segmento_audio):
    """Mejora la calidad del audio para transcripción"""
    try:
        audio_mejorado = normalize(segmento_audio)
        if len(audio_mejorado) > 10000:
            audio_mejorado = audio_mejorado.speedup(playback_speed=1.1)
        audio_mejorado = audio_mejorado.high_pass_filter(80)
        audio_mejorado = audio_mejorado + 3
        return audio_mejorado
    except Exception as e:
        print(f"Error al mejorar audio: {str(e)}")
        return segmento_audio  # Devolver el original si falla la mejora

def crear_directorio_seguro():
    """Crea un directorio temporal único"""
    directorio = os.path.join('uploads', f"temp_{uuid.uuid4().hex}")
    os.makedirs(directorio, exist_ok=True)
    return directorio

def limpiar_directorio(directorio):
    """Intenta limpiar un directorio de forma segura"""
    try:
        if os.path.exists(directorio):
            # Esperar un momento para asegurar que los archivos se liberen
            time.sleep(0.5)
            # Forzar liberación de recursos
            gc.collect()
            # Eliminar el directorio y su contenido
            shutil.rmtree(directorio, ignore_errors=True)
    except Exception as e:
        print(f"No se pudo limpiar completamente {directorio}: {str(e)}")

def transcribir_segmento(reconocedor, segmento_audio, intentos_maximos=3):
    """Transcribe un segmento de audio usando directorios temporales"""
    texto = ""
    temp_dir = None
    
    try:
        # Crear directorio temporal para este segmento
        temp_dir = crear_directorio_seguro()
        archivo_wav = os.path.join(temp_dir, f"segment_{uuid.uuid4().hex}.wav")
        
        # Mejorar y exportar el audio
        segmento_mejorado = mejorar_audio(segmento_audio)
        segmento_mejorado.export(archivo_wav, format="wav")
        
        # Liberar memoria
        segmento_mejorado = None
        gc.collect()
        
        # Intentar la transcripción varias veces
        for intento in range(intentos_maximos):
            try:
                # Crear un nuevo reconocedor en cada intento
                reconocedor_local = sr.Recognizer()
                reconocedor_local.energy_threshold = 300 + (intento * 100)
                reconocedor_local.dynamic_energy_threshold = True
                
                with sr.AudioFile(archivo_wav) as fuente:
                    audio_data = reconocedor_local.record(fuente)
                    texto = reconocedor_local.recognize_google(
                        audio_data,
                        language='es-ES',
                        show_all=False
                    )
                    
                    if texto:
                        break
            except sr.UnknownValueError:
                # Audio no reconocido, continuar al siguiente intento
                time.sleep(0.5)
                continue
            except Exception as e:
                # Otro error, imprimir y continuar
                print(f"Error en intento {intento+1}: {str(e)}")
                time.sleep(0.5)
                continue
            finally:
                # Limpiar memoria en cada intento
                audio_data = None
                reconocedor_local = None
                gc.collect()
    
    except Exception as e:
        print(f"Error en transcribir_segmento: {str(e)}")
    finally:
        # Limpiar recursos
        try:
            if temp_dir and os.path.exists(temp_dir):
                limpiar_directorio(temp_dir)
        except:
            pass
    
    return texto

def transcribir_audio(archivo_audio, directorio_temp=None):
    """Transcribe un archivo de audio completo"""
    try:
        if update_progress:
            update_progress(20, "Cargando archivo de audio", "Procesando...")
        
        # Cargar el audio
        audio_completo = AudioSegment.from_mp3(archivo_audio)
        
        # Configurar el reconocedor
        reconocedor = sr.Recognizer()
        reconocedor.energy_threshold = 300
        reconocedor.dynamic_energy_threshold = True
        
        # Parámetros de segmentación
        duracion_segmento = 15 * 1000  # 15 segundos
        superposicion = 3 * 1000      # 3 segundos
        
        # Dividir en segmentos
        if update_progress:
            update_progress(30, "Dividiendo audio en segmentos", "Esto puede tomar un momento...")
        
        segmentos = []
        for i in range(0, len(audio_completo), duracion_segmento - superposicion):
            fin = min(i + duracion_segmento, len(audio_completo))
            segmento = audio_completo[i:fin]
            segmentos.append(segmento)
        
        total_segmentos = len(segmentos)
        texto_completo = []
        
        if update_progress:
            update_progress(40, "Iniciando transcripción", f"Procesando {total_segmentos} segmentos...")
        
        # Procesar cada segmento
        inicio_tiempo = time.time()
        for i, segmento in enumerate(segmentos, 1):
            if update_progress:
                # Actualizar progreso
                porcentaje = 40 + int((i / total_segmentos) * 50)
                
                # Estimar tiempo restante
                if i > 1:
                    tiempo_transcurrido = time.time() - inicio_tiempo
                    tiempo_por_segmento = tiempo_transcurrido / (i - 1)
                    tiempo_restante = tiempo_por_segmento * (total_segmentos - i + 1)
                    tiempo_restante_str = f"{int(tiempo_restante / 60)} min {int(tiempo_restante % 60)} seg"
                else:
                    tiempo_restante_str = "Calculando..."
                
                update_progress(
                    porcentaje, 
                    f"Segmento {i} de {total_segmentos}", 
                    tiempo_restante_str
                )
            
            # Transcribir este segmento
            texto_segmento = transcribir_segmento(reconocedor, segmento)
            if texto_segmento:
                texto_completo.append(texto_segmento)
            
            # Limpiar memoria
            segmento = None
            gc.collect()
        
        # Finalizar
        if update_progress:
            update_progress(95, "Finalizando transcripción", "Casi listo...")
        
        # Juntar todos los segmentos
        resultado = " ".join(texto_completo)
        
        # Limpiar memoria
        audio_completo = None
        segmentos = None
        texto_completo = None
        gc.collect()
        
        return resultado
        
    except Exception as e:
        print(f"Error en transcribir_audio: {traceback.format_exc()}")
        raise Exception(f"Error en transcripción: {str(e)}")
    finally:
        # Limpiar directorio temporal si existe
        if directorio_temp and os.path.exists(directorio_temp):
            limpiar_directorio(directorio_temp)

def transcribir_video_youtube(url_video):
    """Transcribe audio desde un video de YouTube"""
    archivo_audio = None
    directorio_temp = None
    
    try:
        # Descargar el audio
        archivo_audio, directorio_temp = descargar_audio(url_video)
        
        # Transcribir el audio
        transcripcion = transcribir_audio(archivo_audio, directorio_temp)
        
        # Finalizar
        if update_progress:
            update_progress(100, "¡Transcripción completada!", "Listo")
            
        return transcripcion
    except Exception as e:
        raise Exception(f"Error en transcripción de YouTube: {str(e)}")
    finally:
        # Limpiar archivos temporales
        try:
            if directorio_temp and os.path.exists(directorio_temp):
                limpiar_directorio(directorio_temp)
        except:
            pass

def procesar_archivo_local(ruta_archivo):
    """Procesa un archivo de audio local"""
    directorio_temp = None
    
    try:
        if update_progress:
            update_progress(5, "Procesando archivo", "Iniciando...")
        
        # Detectar extensión
        extension = os.path.splitext(ruta_archivo)[1].lower()
        
        if extension != '.mp3':
            if update_progress:
                update_progress(10, "Convirtiendo formato", "Preparando audio...")
            
            # Crear directorio temporal
            directorio_temp = crear_directorio_seguro()
            archivo_mp3 = os.path.join(directorio_temp, f"temp_{uuid.uuid4().hex}.mp3")
            
            # Convertir a MP3
            audio = AudioSegment.from_file(ruta_archivo)
            audio.export(archivo_mp3, format="mp3")
            
            # Liberar memoria
            audio = None
            gc.collect()
            
            # Transcribir el MP3 generado
            transcripcion = transcribir_audio(archivo_mp3, directorio_temp)
        else:
            # Ya es MP3, transcribir directamente
            transcripcion = transcribir_audio(ruta_archivo)
        
        # Finalizar
        if update_progress:
            update_progress(100, "¡Transcripción completada!", "Listo")
            
        return transcripcion
    except Exception as e:
        raise Exception(f"Error en archivo local: {str(e)}")
    finally:
        # Limpiar directorio temporal
        try:
            if directorio_temp and os.path.exists(directorio_temp):
                limpiar_directorio(directorio_temp)
        except:
            pass

def limpiar_archivos_temporales():
    """Limpia todos los archivos temporales del directorio uploads"""
    try:
        if not os.path.exists('uploads'):
            os.makedirs('uploads', exist_ok=True)
            return
        
        print("Limpiando archivos temporales...")
        for item in os.listdir('uploads'):
            ruta = os.path.join('uploads', item)
            try:
                if os.path.isdir(ruta) and (item.startswith('temp_') or item.startswith('yt_')):
                    shutil.rmtree(ruta, ignore_errors=True)
                    print(f"  - Eliminado directorio: {item}")
                elif os.path.isfile(ruta) and (item.startswith('segment_') or 
                                             item.startswith('temp_') or 
                                             item.startswith('audio_')):
                    os.remove(ruta)
                    print(f"  - Eliminado archivo: {item}")
            except Exception as e:
                print(f"  - Error al eliminar {item}: {str(e)}")
    except Exception as e:
        print(f"Error al limpiar archivos temporales: {str(e)}")

# Ejecutar limpieza inicial
limpiar_archivos_temporales()