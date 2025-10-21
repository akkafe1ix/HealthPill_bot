import sqlite3
import logging
import os
from datetime import datetime

logger = logging.getLogger(__name__)

class Database:
    def __init__(self, db_path='/app/data/medications.db'):
        # Создаем папку data если её нет
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.db_path = db_path
        self.create_tables()
    
    def get_connection(self):
        """Создает соединение с базой данных"""
        return sqlite3.connect(self.db_path)
    
    def create_tables(self):
        """Создает таблицы если они не существуют"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Таблица пользователей
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Таблица лекарств
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS medications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                dosage TEXT,
                schedule TEXT NOT NULL,
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
        ''')
        
        conn.commit()
        conn.close()
        logger.info("Таблицы базы данных созданы/проверены")
    
    def add_user(self, user_id, username, first_name, last_name):
        """Добавляет или обновляет пользователя"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO users (user_id, username, first_name, last_name)
            VALUES (?, ?, ?, ?)
        ''', (user_id, username, first_name, last_name))
        
        conn.commit()
        conn.close()
        logger.info(f"Добавлен/обновлен пользователь: {user_id}")
    
    def add_medication(self, user_id, name, dosage, schedule):
        """Добавляет новое лекарство"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO medications (user_id, name, dosage, schedule)
            VALUES (?, ?, ?, ?)
        ''', (user_id, name, dosage, schedule))
        
        medication_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        logger.info(f"Добавлено лекарство: {name} для пользователя {user_id}")
        return medication_id
    
    def get_user_medications(self, user_id):
        """Возвращает все активные лекарства пользователя"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, name, dosage, schedule 
            FROM medications 
            WHERE user_id = ? AND is_active = TRUE
            ORDER BY created_at DESC
        ''', (user_id,))
        
        medications = cursor.fetchall()
        conn.close()
        
        return medications
    
    def get_all_medications(self):
        """Возвращает все лекарства всех пользователей (для напоминаний)"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT user_id, name, dosage, schedule 
            FROM medications 
            WHERE is_active = TRUE
        ''')
        
        medications = cursor.fetchall()
        conn.close()
        
        return medications
    
    def get_medications_by_time(self, time_str):
        """Возвращает лекарства которые нужно принять в указанное время"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT user_id, name, dosage, schedule 
            FROM medications 
            WHERE is_active = TRUE AND schedule LIKE ?
        ''', (f'%{time_str}%',))
        
        medications = cursor.fetchall()
        conn.close()
        
        return medications
    
    def delete_medication(self, medication_id, user_id):
        """Удаляет лекарство пользователя"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            DELETE FROM medications 
            WHERE id = ? AND user_id = ?
        ''', (medication_id, user_id))
        
        deleted = cursor.rowcount > 0
        conn.commit()
        conn.close()
        
        logger.info(f"Удаление лекарства {medication_id}: {deleted}")
        return deleted
    
    def get_medication(self, medication_id, user_id):
        """Возвращает конкретное лекарство"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, name, dosage, schedule 
            FROM medications 
            WHERE id = ? AND user_id = ?
        ''', (medication_id, user_id))
        
        medication = cursor.fetchone()
        conn.close()
        
        return medication