#database.py

import sqlite3
from datetime import datetime

def init_db():
    conn = sqlite3.connect('transcriptions.db')
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS transcriptions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            source_type TEXT NOT NULL
        )
    ''')
    conn.commit()
    conn.close()

def save_transcription(filename, content, source_type):
    conn = sqlite3.connect('transcriptions.db')
    c = conn.cursor()
    
    # Ya no eliminamos las transcripciones anteriores
    # Guardamos la nueva transcripción
    c.execute('INSERT INTO transcriptions (filename, content, source_type) VALUES (?, ?, ?)',
              (filename, content, source_type))
    conn.commit()
    conn.close()

def get_all_transcriptions():
    conn = sqlite3.connect('transcriptions.db')
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute('SELECT * FROM transcriptions ORDER BY created_at DESC')
    transcriptions = c.fetchall()
    conn.close()
    return transcriptions

def get_transcription_by_id(transcription_id):
    try:
        conn = sqlite3.connect('transcriptions.db')
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute('SELECT * FROM transcriptions WHERE id = ?', (transcription_id,))
        transcription = c.fetchone()
        conn.close()
        return transcription
    except Exception as e:
        print(f"Error al obtener transcripción: {str(e)}")
        return None

def clear_all_transcriptions():
    try:
        conn = sqlite3.connect('transcriptions.db')
        c = conn.cursor()
        c.execute('DELETE FROM transcriptions')
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Error al limpiar transcripciones: {str(e)}")
        return False