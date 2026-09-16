import os
import datetime
from typing import List, Dict, Any, Optional
import psycopg2
from psycopg2.extras import DictCursor

def get_db_connection():
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise ValueError("DATABASE_URL environment variable is not set")
    return psycopg2.connect(db_url)

def init_db():
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id SERIAL PRIMARY KEY,
                title TEXT NOT NULL,
                description TEXT,
                status TEXT DEFAULT 'pending',
                deadline TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """)
            # Migrate: add deadline column if it doesn't exist yet
            cursor.execute("""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name='tasks' AND column_name='deadline'
                ) THEN
                    ALTER TABLE tasks ADD COLUMN deadline TEXT;
                END IF;
            END $$;
            """)
            
            # Memory and Context engine (Nia-like)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS memories (
                id SERIAL PRIMARY KEY,
                user_id TEXT NOT NULL,
                fact TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """)
            
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                id SERIAL PRIMARY KEY,
                chat_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """)
        conn.commit()

def add_task(title: str, description: str = "", deadline: Optional[str] = None) -> int:
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                "INSERT INTO tasks (title, description, deadline) VALUES (%s, %s, %s) RETURNING id",
                (title, description, deadline)
            )
            task_id = cursor.fetchone()[0]
        conn.commit()
        return task_id

def get_tasks() -> List[Dict[str, Any]]:
    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute("SELECT * FROM tasks ORDER BY created_at DESC")
            return [dict(row) for row in cursor.fetchall()]

def update_task_status(task_id: int, status: str):
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("UPDATE tasks SET status = %s WHERE id = %s", (status, task_id))
        conn.commit()

def delete_task(task_id: int):
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("DELETE FROM tasks WHERE id = %s", (task_id,))
        conn.commit()

# --- Memory Engine Functions ---

def add_memory(user_id: str, fact: str) -> int:
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                "INSERT INTO memories (user_id, fact) VALUES (%s, %s) RETURNING id",
                (str(user_id), fact)
            )
            mem_id = cursor.fetchone()[0]
        conn.commit()
        return mem_id

def get_memories(user_id: str) -> List[Dict[str, Any]]:
    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute("SELECT * FROM memories WHERE user_id = %s ORDER BY created_at ASC", (str(user_id),))
            return [dict(row) for row in cursor.fetchall()]

def add_conversation_message(chat_id: str, role: str, content: str):
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                "INSERT INTO conversations (chat_id, role, content) VALUES (%s, %s, %s)",
                (str(chat_id), role, content)
            )
        conn.commit()

def get_conversation_history(chat_id: str, limit: int = 20) -> List[Dict[str, Any]]:
    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute(
                "SELECT * FROM conversations WHERE chat_id = %s ORDER BY created_at DESC LIMIT %s", 
                (str(chat_id), limit)
            )
            rows = cursor.fetchall()
            # Return in chronological order
            return [dict(row) for row in reversed(rows)]

