def add_compounding_rule(rule_key: str, description: str, correction: str):
    import database

    return database.add_compounding_rule(rule_key, description, correction)


def get_compounding_rules():
    import database

    return database.get_compounding_rules()


def delete_compounding_rule(rule_key: str) -> bool:
    import database

    return database.delete_compounding_rule(rule_key)
