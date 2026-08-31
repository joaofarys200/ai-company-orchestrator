"""
JARVIS OS — UTF-8 & Mojibake Auto-Sanitizer
Corrige encoding e caracteres corrompidos em todos os ficheiros do projeto.
"""

import os

MOJIBAKE_MAP = {
    'Ã£': 'ã', 'Ã§': 'ç', 'Ã©': 'é', 'Ã³': 'ó', 'Ã­': 'í',
    'Ãº': 'ú', 'Ã¡': 'á', 'Ãµ': 'õ', 'Ãª': 'ê', 'Ã‰': 'É',
    'Ã€': 'À', 'Ã ': 'à', 'Ã¢': 'â', 'Ã²': 'ò', 'Ã¨': 'è',
    'Ã¬': 'ì', 'Ã¹': 'ù', 'Ã±': 'ñ', 'Ã¼': 'ü', 'Ã¶': 'ö',
    'Ã¤': 'ä', 'â€”': '—', 'â†’': '→', 'â€œ': '“', 'â€\x9d': '”',
    'â€˜': '‘', 'â€™': '’', 'â‚¬': '€', 'Ã\x81': 'Á', 'Ã\x93': 'Ó',
    'Ã\x89': 'É', 'Ã\x9a': 'Ú', 'Ã\x8d': 'Í', 'Ã\x80': 'À'
}

def clean_text(text: str) -> str:
    for bad, good in MOJIBAKE_MAP.items():
        text = text.replace(bad, good)
    return text

def main():
    cleaned_count = 0
    dirs = ['backend', 'agents', 'security', 'intelligence', 'frontend/src', 'services']
    for d in dirs:
        if not os.path.exists(d):
            continue
        for root, _, files in os.walk(d):
            for f in files:
                if f.endswith(('.py', '.json', '.ts', '.tsx', '.js', '.html')):
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
