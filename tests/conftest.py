"""
Configuração global do Pytest para o JARVIS OS.
Garante que módulos opcionais ou externos que não estejam instalados no ambiente de teste
possuam stubs para permitir a execução de testes unitários e de governança.
"""

import sys
from unittest.mock import MagicMock

for mod in [
    "jsonschema",
    "jsonschema.validators",
    "httpx",
    "psutil",
    "dotenv",
    "yaml",
    "aiohttp",
    "websockets",
    "cryptography",
    "PIL",
    "PIL.ImageGrab",
    "PIL.Image",
]:
    if mod not in sys.modules:
        sys.modules[mod] = MagicMock()
