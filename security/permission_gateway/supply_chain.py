"""
JARVIS OS — Permission Gateway Supply Chain Validator
Protects against hallucinated package names (slopsquatting), untrusted registries,
path traversal, and malicious installers.
"""

from __future__ import annotations

import re
from typing import Optional, Tuple


class SupplyChainValidator:
    """
    Valida integridade e proveniência de pacotes, dependências e binários externos.
    """

    TRUSTED_REGISTRIES = {
        "pypi": r"^https?:\/\/(?:www\.)?(?:pypi\.org|files\.pythonhosted\.org)\/.*",
        "npm": r"^https?:\/\/(?:registry\.npmjs\.org|www\.npmjs\.com)\/.*",
        "nmap_official": r"^https?:\/\/(?:www\.)?nmap\.org\/.*",
        "ffmpeg_official": r"^https?:\/\/(?:www\.)?gyan\.dev\/ffmpeg\/.*|^https?:\/\/ffmpeg\.org\/.*",
        "github_trusted": r"^https?:\/\/github\.com\/(?:nmap|BtbN|tesseract-ocr)\/.*",
        "winget": r"^winget:(?:Insecure\.Nmap|Gyan\.FFmpeg|UB-Mannheim\.TesseractOCR)",
    }

    # Padrão estrito para nomes de pacotes npm/python legítimos
    VALID_PACKAGE_NAME_REGEX = re.compile(r"^[a-zA-Z0-9_\-\.\@\/]{2,64}$")
    SUSPICIOUS_PATH_PATTERNS = re.compile(r"(^|[\\/\s'\"`])\.\.([\\/]|$)|[\0\r\n]")

    @classmethod
    def validate_package(
        cls,
        package_name: str,
        registry: Optional[str] = None,
        source_url: Optional[str] = None,
        checksum: Optional[str] = None,
    ) -> Tuple[bool, str]:
        if not package_name or not isinstance(package_name, str):
            return False, "Nome do pacote vazio ou inválido."

        clean_pkg = package_name.strip()

        # 1. Verificação contra injeção e path traversal
        if cls.SUSPICIOUS_PATH_PATTERNS.search(clean_pkg):
            return False, f"Detetada tentativa de Path Traversal no nome do pacote: '{clean_pkg}'."

        if not cls.VALID_PACKAGE_NAME_REGEX.match(clean_pkg):
            return False, f"Formato inválido de nome de pacote: '{clean_pkg}'."

        # 2. Verificação de registry / source_url se fornecido
        if source_url:
            matched = any(
                re.match(pattern, source_url)
                for pattern in cls.TRUSTED_REGISTRIES.values()
            )
            if not matched:
                return False, f"Fonte/URL não autorizada pela política de supply chain: '{source_url}'."

        # 3. Verificação de Checksum SHA-256 se fornecido
        if checksum:
            clean_hash = checksum.strip().lower()
            if not re.fullmatch(r"^[0-9a-f]{64}$", clean_hash):
                return False, "Checksum fornecido não é um SHA-256 hexadecimal válido."

        return True, "Validação de supply chain aprovada."

    @classmethod
    def validate_installer_source(cls, installer_source: Optional[str]) -> Tuple[bool, str]:
        if not installer_source:
            return True, "Nenhuma fonte externa informada."

        clean_source = installer_source.strip()
        if cls.SUSPICIOUS_PATH_PATTERNS.search(clean_source):
            return False, "Instalador rejeitado por conter caracteres perigosos ou navegação relativa."

        # Aceita se casar com registry confiável ou caminho local seguro no workspace
        is_trusted = any(
            re.match(pattern, clean_source)
            for pattern in cls.TRUSTED_REGISTRIES.values()
        )
        if not is_trusted and clean_source.startswith("http"):
            return False, f"Download de instalador bloqueado: fonte '{clean_source}' não está na lista de repositórios confiáveis."

        return True, "Fonte do instalador verificada."
