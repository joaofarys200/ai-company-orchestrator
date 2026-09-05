"""
JARVIS OS — UTF-8 & Mojibake Auto-Sanitizer
Corrige encoding e caracteres corrompidos em todos os ficheiros do projeto.
"""

import os

MOJIBAKE_MAP = {
    # Accented Latin characters
    'Ã£': 'ã', 'Ã§': 'ç', 'Ã©': 'é', 'Ã³': 'ó', 'Ã\xad': 'í', 'Ã­': 'í',
    'Ãº': 'ú', 'Ã¡': 'á', 'Ãµ': 'õ', 'Ãª': 'ê', 'Ã‰': 'É',
    'Ã€': 'À', 'Ã ': 'à', 'Ã¢': 'â', 'Ã²': 'ò', 'Ã¨': 'è',
    'Ã¬': 'ì', 'Ã¹': 'ù', 'Ã±': 'ñ', 'Ã¼': 'ü', 'Ã¶': 'ö',
    'Ã¤': 'ä', 'Ã\x81': 'Á', 'Ã\x93': 'Ó', 'Ã\x89': 'É', 'Ã\x9a': 'Ú',
    'Ã\x8d': 'Í', 'Ã\x80': 'À', 'Ã‡': 'Ç',
    # Double corrupted forms
    'ÃƒÂ£': 'ã', 'ÃƒÂ§': 'ç', 'ÃƒÂ©': 'é', 'ÃƒÂ³': 'ó', 'ÃƒÂ\xad': 'í', 'ÃƒÂ­': 'í',
    'ÃƒÂº': 'ú', 'ÃƒÂ¡': 'á', 'ÃƒÂµ': 'õ', 'ÃƒÂª': 'ê', 'ÃƒÂ‰': 'É',
    'ÃƒÂ ': 'à', 'ÃƒÂ¢': 'â', 'ÃƒÂ©': 'é',
    # Punctuation & symbols
    'â€”': '—', 'â†’': '→', 'â€œ': '“', 'â€\x9d': '”', 'â€\x9c': '“',
    'â€˜': '‘', 'â€™': '’', 'â‚¬': '€', 'â€¢': '•', 'â€¦': '…',
    'â”€': '─', 'â”‚': '│', 'â”œ': '├', 'â””': '└', 'â”': '┌',
    # Emojis corrupted from UTF-8 to CP1252 / Latin-1
    'ðŸ“Ž': '📎', 'ðŸ§\xa0': '🧠', 'ðŸ§ ': '🧠', 'ðŸ‘‘': '👑',
    'ðŸŽ¯': '🎯', 'ðŸ›\xa0ï¸ ': '🛠️', 'ðŸ›\xa0': '🛠️', 'ðŸ“–': '📖',
    'âš\xa0ï¸ ': '⚠️', 'âš\xa0': '⚠️', 'âœ…': '✅', 'ðŸ“‹': '📋',
    'ðŸ’°': '💰', 'ðŸ” ': '🔍', 'ðŸ’¹': '💹', 'ðŸ—„ï¸ ': '🗄️',
    'ðŸ—„': '🗄️', 'ðŸ ›ï¸ ': '🕸️', 'ðŸ ›': '🕸️', 'ðŸ’½': '💾',
    'ðŸ”„': '🔄', 'ðŸ“Š': '📊', 'ðŸ —ï¸ ': '🏗️', 'ðŸ —': '🏗️',
    'ðŸ›°ï¸ ': '🛰️', 'ðŸ›°': '🛰️', 'ðŸ“¡': '📡', 'ðŸ“ ': '📌',
    'ðŸ©¹': '🩹', 'ðŸ–¥ï¸ ': '🖥️', 'ðŸ–¥': '🖥️', 'ðŸš¨': '🚨',
    'ðŸ”´': '🔴', 'ðŸŸ¡': '🟡', 'ðŸŸ¢': '🟢', 'ðŸ™ˆ': '🙈',
    'ðŸ›¡ï¸ ': '🛡️', 'ðŸ›¡': '🛡️', 'ðŸ“Œ': '📍', 'ðŸ”’': '🔒',
    'ðŸ ³': '🐳', 'ðŸ”‘': '🔑', 'ðŸŒ ': '🌐', 'ðŸ’¥': '💥',
    'ðŸ °': '🏰', 'ðŸ¤–': '🤖', 'ðŸ   ': '🏛️', 'Ã¢Å“â€¦': '✅',
}

def clean_text(text: str) -> str:
    # Multiple passes to handle layered mojibake
    for _ in range(2):
        for bad, good in MOJIBAKE_MAP.items():
            text = text.replace(bad, good)
    return text

def main():
    cleaned_count = 0
    dirs = ['backend', 'agents', 'security', 'intelligence', 'frontend/src', 'services', 'obsidian_vault']
    single_files = ['gemini_live.py', 'server.py', 'database.py', 'websocket_schema.py']
    
    for sf in single_files:
        if os.path.exists(sf):
            try:
                with open(sf, 'r', encoding='utf-8', errors='replace') as fp:
                    content = fp.read()
                if any(k in content for k in MOJIBAKE_MAP.keys()):
                    new_content = clean_text(content)
                    with open(sf, 'w', encoding='utf-8') as fp:
                        fp.write(new_content)
                    cleaned_count += 1
                    print(f"Cleaned mojibake in: {sf}")
            except Exception as e:
                print(f"Error cleaning {sf}: {e}")

    for d in dirs:
        if not os.path.exists(d):
            continue
        for root, _, files in os.walk(d):
            for f in files:
                if f.endswith(('.py', '.json', '.ts', '.tsx', '.js', '.html', '.md')):
                    p = os.path.join(root, f)
                    try:
                        with open(p, 'r', encoding='utf-8', errors='replace') as fp:
                            content = fp.read()
                    except Exception:
                        continue

                    if any(k in content for k in MOJIBAKE_MAP.keys()):
                        new_content = clean_text(content)
                        with open(p, 'w', encoding='utf-8') as fp:
                            fp.write(new_content)
                        cleaned_count += 1
                        print(f"Cleaned mojibake in: {p}")

    print(f"\n[OK] Sanitized {cleaned_count} files.")

if __name__ == "__main__":
    main()
