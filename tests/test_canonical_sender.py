from __future__ import annotations

import sqlite3
import pytest

from backend.message_protocol import chat_message, normalize_canonical_sender, normalize_ws_message
from database import add_message, get_connection, init_db


def test_normalize_canonical_sender():
    assert normalize_canonical_sender("OPENCLAW") == "JARVIS"
    assert normalize_canonical_sender("openclaw") == "JARVIS"
    assert normalize_canonical_sender("OpenClaw") == "JARVIS"
    assert normalize_canonical_sender("ASSISTANT") == "JARVIS"
    assert normalize_canonical_sender("AI") == "JARVIS"
    assert normalize_canonical_sender("ORCHESTRATOR") == "JARVIS"
    
    assert normalize_canonical_sender("CLIENTE") == "CLIENTE"
    assert normalize_canonical_sender("USER") == "CLIENTE"
    assert normalize_canonical_sender("CEO") == "CLIENTE"
    assert normalize_canonical_sender("utilizador") == "CLIENTE"
    
    assert normalize_canonical_sender("SISTEMA") == "SISTEMA"
    assert normalize_canonical_sender("SYSTEM") == "SISTEMA"
    
    assert normalize_canonical_sender("Devon") == "Devon"
    assert normalize_canonical_sender("Clara") == "Clara"
    assert normalize_canonical_sender("Alex") == "Alex"
    assert normalize_canonical_sender("Quinn") == "Quinn"


def test_normalize_ws_chat_message_strips_openclaw():
    raw = {
        "type": "chat",
        "sender": "OPENCLAW",
        "role": "Orquestrador",
        "content": "A aguardar instruções.",
    }
    normalized = normalize_ws_message(raw)
    assert normalized["sender"] == "JARVIS"
    assert normalized["role"] == "Orquestrador"
    assert normalized["content"] == "A aguardar instruções."


def test_database_openclaw_migration_and_normalization(tmp_path, monkeypatch):
    test_db = str(tmp_path / "test_migration.db")
    
    def fake_get_connection():
        return sqlite3.connect(test_db)
        
    monkeypatch.setattr("database.get_connection", fake_get_connection)
    
    # 1. First create DB with a legacy OPENCLAW entry
    conn = fake_get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            sender TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            timestamp TEXT NOT NULL
        )
    """)
    cursor.execute("""
        INSERT INTO messages (session_id, sender, role, content, timestamp)
        VALUES (1, 'OPENCLAW', 'Orquestrador', 'Mensagem antiga legado', '2026-09-01T10:00:00')
    """)
    conn.commit()
    conn.close()
    
    # 2. Run init_db which triggers automatic migration
    init_db()
    
    conn = fake_get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT sender, content FROM messages WHERE id = 1")
    row = cursor.fetchone()
    conn.close()
    
    assert row[0] == "JARVIS"
    
    # 3. Add message with OPENCLAW sender -> must be stored as JARVIS
    add_message(1, "openclaw", "Orquestrador", "Nova mensagem")
    
    conn = fake_get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT sender FROM messages WHERE id = 2")
    row2 = cursor.fetchone()
    conn.close()
    
    assert row2[0] == "JARVIS"
