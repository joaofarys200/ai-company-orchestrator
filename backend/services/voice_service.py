def normalize_voice_prompt(text: str) -> str:
    clean = text.strip()
    lower = clean.lower()

    replacements = [
        ("ok, abro o ", "abre o "),
        ("ok, abro a ", "abre a "),
        ("ok, abro um ", "abre um "),
        ("ok, abro uma ", "abre uma "),
        ("ok abro o ", "abre o "),
        ("ok abro a ", "abre a "),
        ("ok abro um ", "abre um "),
        ("ok abro uma ", "abre uma "),
        ("abro o ", "abre o "),
        ("abro a ", "abre a "),
        ("abro um ", "abre um "),
        ("abro uma ", "abre uma "),
        ("avas o ", "abras o "),
        ("avas um ", "abras um "),
        ("avas ", "abre "),
        ("avas o", "abre o"),
        ("que tu avas ", "que tu abras "),
    ]

    for old, new in replacements:
        if lower.startswith(old):
            clean = clean[len(old):]
            clean = new.capitalize() + clean
            break

    return clean
