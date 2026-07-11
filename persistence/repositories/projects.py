def save_project(session_id: int, name: str, description: str, html: str, css: str, js: str):
    import database

    return database.save_project(session_id, name, description, html, css, js)
