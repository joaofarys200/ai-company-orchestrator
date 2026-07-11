def add_message(session_id: int, sender: str, role: str, content: str):
    import database

    return database.add_message(session_id, sender, role, content)
