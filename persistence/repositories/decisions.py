def add_engineering_decision(decision: str, reason: str, impact: str):
    import database

    return database.add_engineering_decision(decision, reason, impact)


def get_engineering_decisions():
    import database

    return database.get_engineering_decisions()


def delete_engineering_decision(decision: str) -> bool:
    import database

    return database.delete_engineering_decision(decision)
