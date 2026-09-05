from __future__ import annotations

import json
import os
import sqlite3
import tempfile
import pytest

from backend.message_protocol import chat_message, normalize_canonical_sender, normalize_ws_message
from backend.websocket.gateway import serialize_server_message
from database import add_message, get_connection, init_db


def test_utf8_portuguese_accents_and_currency_and_emojis():
    sample_text = "Cria uma aplicação simples para gerir tarefas. Guardar os dados localmente. Mostrar criação, edição e eliminação. Preço: 150€ 🚀 👑 🎯 🧠 📎"
    
    msg = chat_message("JARVIS", "Orquestrador", sample_text)
    serialized = serialize_server_message(msg)
    
    # Ensure raw UTF-8 characters are preserved without corruption
    assert "aplicação" in serialized
    assert "criação, edição e eliminação" in serialized
    assert "150€" in serialized
    assert "🚀" in serialized
    assert "👑" in serialized
    assert "ðŸ" not in serialized
    assert "Ã" not in serialized
    assert "â€" not in serialized
    
    deserialized = json.loads(serialized)
    assert deserialized["content"] == sample_text
    assert deserialized["sender"] == "JARVIS"


def test_sqlite_persistence_utf8_roundtrip(tmp_path, monkeypatch):
    test_db = str(tmp_path / "test_utf8.db")
    
    def fake_get_connection():
        conn = sqlite3.connect(test_db)
        return conn
        
    monkeypatch.setattr("database.get_connection", fake_get_connection)
    init_db()
    
    portuguese_content = "Configuração do sistema com módulos avançados e validação automática de acentuação: á é í ó ú ã õ ç € 🎯."
    add_message(1, "CLIENTE", "CEO", portuguese_content)
    add_message(1, "JARVIS", "Orquestrador", "Entendido. A iniciar orquestração do módulo de produção.")
    
    conn = fake_get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT sender, role, content FROM messages WHERE session_id = 1 ORDER BY id ASC")
    rows = cursor.fetchall()
    conn.close()
    
    assert len(rows) == 2
    assert rows[0][0] == "CLIENTE"
    assert rows[0][2] == portuguese_content
    assert rows[1][0] == "JARVIS"
    assert "orquestração" in rows[1][2]
