import sqlite3


def get_db_file() -> str:
    import database

    return database.DB_FILE


def get_connection():
    return sqlite3.connect(get_db_file())
