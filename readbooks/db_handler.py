import sqlite3
from datetime import datetime
from sqlite3 import Error
from typing import Optional, List, Dict
import threading

class DBHandler:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._lock = threading.Lock()
        self._init_db()
        
    def _init_db(self):
        """初始化数据库"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS interactions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        book_title TEXT NOT NULL,
                        question TEXT NOT NULL,
                        answer TEXT NOT NULL,
                        audio_path TEXT NOT NULL,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                # 创建索引
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_book_title ON interactions(book_title)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_created_at ON interactions(created_at)')
                conn.commit()
        except Error as e:
            raise Exception(f"数据库初始化失败: {str(e)}")
            
    def _get_connection(self):
        """获取数据库连接"""
        try:
            conn = sqlite3.connect(self.db_path, check_same_thread=False)
            conn.row_factory = sqlite3.Row  # 返回字典格式的结果
            return conn
        except Error as e:
            raise Exception(f"数据库连接失败: {str(e)}")
            
    def save_interaction(self, book_title: str, question: str, answer: str, audio_path: str) -> bool:
        """保存交互记录"""
        if not all([book_title, question, answer, audio_path]):
            raise ValueError("所有参数都不能为空")
            
        try:
            with self._lock:
                with self._get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute('''
                        INSERT INTO interactions 
                        (book_title, question, answer, audio_path)
                        VALUES (?, ?, ?, ?)
                    ''', (book_title, question, answer, audio_path))
                    conn.commit()
                    return True
        except Error as e:
            raise Exception(f"保存交互记录失败: {str(e)}")
            
    def get_interactions(self, book_title: Optional[str] = None, limit: int = 100) -> List[Dict]:
        """获取交互记录"""
        try:
            with self._lock:
                with self._get_connection() as conn:
                    cursor = conn.cursor()
                    if book_title:
                        cursor.execute('''
                            SELECT * FROM interactions
                            WHERE book_title = ?
                            ORDER BY created_at DESC
                            LIMIT ?
                        ''', (book_title, limit))
                    else:
                        cursor.execute('''
                            SELECT * FROM interactions
                            ORDER BY created_at DESC
                            LIMIT ?
                        ''', (limit,))
                    return [dict(row) for row in cursor.fetchall()]
        except Error as e:
            raise Exception(f"获取交互记录失败: {str(e)}")
            
    def delete_interaction(self, interaction_id: int) -> bool:
        """删除交互记录"""
        try:
            with self._lock:
                with self._get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute('DELETE FROM interactions WHERE id = ?', (interaction_id,))
                    conn.commit()
                    return cursor.rowcount > 0
        except Error as e:
            raise Exception(f"删除交互记录失败: {str(e)}")
