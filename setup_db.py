
import sqlite3
from datetime import datetime

DB_FILE = "ecommerce.db"

def obter_conexao():
    return sqlite3.connect(DB_FILE)

def inicializar_bd():
    conn = obter_conexao()
    cursor = conn.cursor()
    
    cursor.execute("PRAGMA foreign_keys = ON;")
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS utilizadores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            data_registo TEXT NOT NULL
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS produtos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome_produto TEXT NOT NULL,
            preco REAL NOT NULL,
            stock INTEGER NOT NULL
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS compras (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            utilizador_id INTEGER NOT NULL,
            produto_id INTEGER NOT NULL,
            quantidade INTEGER NOT NULL,
            data_compra TEXT NOT NULL,
            FOREIGN KEY (utilizador_id) REFERENCES utilizadores(id),
            FOREIGN KEY (produto_id) REFERENCES produtos(id)
        )
    """)
    
    conn.commit()
    conn.close()

def popular_bd():
    conn = obter_conexao()
    cursor = conn.cursor()

    # Inserir utilizadores
    utilizadores_data = [
        ("Ana Silva", "ana.silva@email.com", datetime.utcnow().isoformat()),
        ("Bruno Costa", "bruno.costa@email.com", datetime.utcnow().isoformat()),
        ("Carla Dias", "carla.dias@email.com", datetime.utcnow().isoformat()),
    ]
    cursor.executemany("INSERT OR IGNORE INTO utilizadores (nome, email, data_registo) VALUES (?, ?, ?)", utilizadores_data)
    
    # Inserir produtos
    produtos_data = [
        ("Smartphone X", 799.99, 50),
        ("Smartwatch Y", 199.99, 120),
        ("Headphones Z", 99.99, 200),
        ("Teclado Mecânico", 120.00, 80),
        ("Monitor Curvo", 350.00, 30),
    ]
    cursor.executemany("INSERT OR IGNORE INTO produtos (nome_produto, preco, stock) VALUES (?, ?, ?)", produtos_data)

    # Inserir compras
    # Assumindo que os IDs dos utilizadores e produtos são 1, 2, 3, etc.
    compras_data = [
        (1, 1, 1, datetime(2023, 1, 15).isoformat()), # Ana comprou Smartphone X
        (1, 2, 2, datetime(2023, 1, 20).isoformat()), # Ana comprou 2 Smartwatch Y
        (2, 1, 1, datetime(2023, 2, 10).isoformat()), # Bruno comprou Smartphone X
        (2, 3, 3, datetime(2023, 2, 12).isoformat()), # Bruno comprou 3 Headphones Z
        (3, 2, 1, datetime(2023, 3, 5).isoformat()),  # Carla comprou Smartwatch Y
        (1, 3, 1, datetime(2023, 3, 10).isoformat()), # Ana comprou Headphones Z
        (2, 4, 1, datetime(2023, 4, 1).isoformat()),  # Bruno comprou Teclado Mecânico
        (3, 5, 1, datetime(2023, 4, 5).isoformat()),  # Carla comprou Monitor Curvo
        (1, 1, 1, datetime(2023, 4, 10).isoformat()), # Ana comprou outro Smartphone X
    ]
    cursor.executemany("INSERT INTO compras (utilizador_id, produto_id, quantidade, data_compra) VALUES (?, ?, ?, ?)", compras_data)
    
    conn.commit()
    conn.close()

if __name__ == "__main__":
    inicializar_bd()
    popular_bd()
    print("Base de dados 'ecommerce.db' criada e populada com sucesso.")
