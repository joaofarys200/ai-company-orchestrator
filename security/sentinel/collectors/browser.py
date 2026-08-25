"""
JARVIS OS — Security Sentinel Browser Extensions Telemetry Collector
Inventário read-only de extensões instaladas no Chrome, Edge e Firefox.
"""

from __future__ import annotations

import glob
import json
import os
from typing import Dict, List, Optional

from security.sentinel.collectors.base import BaseCollector
from security.sentinel.contracts import BrowserExtensionItem, EventCategory, SecurityEvidence


class BrowserCollector(BaseCollector):
    """Coletor de extensões instaladas em navegadores suportados."""

    def __init__(self) -> None:
        super().__init__(name="browser_collector", category=EventCategory.BROWSER)

    def _resolve_manifest_name(self, manifest: Dict, ext_dir: str) -> str:
        """Resolve nomes localizados com formato __MSG_name__ no manifest."""
        name = manifest.get("name", "Unknown Extension")
        if not name.startswith("__MSG_"):
            return name

        msg_key = name.replace("__MSG_", "").rstrip("_")
        locales_dir = os.path.join(ext_dir, "_locales")
        candidate_locales = ["en", "en_US", "pt", "pt_PT", "pt_BR", "default"]

        for loc in candidate_locales:
            msg_path = os.path.join(locales_dir, loc, "messages.json")
            if os.path.isfile(msg_path):
                try:
                    with open(msg_path, "r", encoding="utf-8", errors="replace") as f:
                        msgs = json.load(f)
                        if msg_key in msgs and "message" in msgs[msg_key]:
                            return msgs[msg_key]["message"]
                except Exception:
                    pass

        return manifest.get("short_name") or name

    def _scan_chromium_extensions(self, base_user_data_path: str, browser_name: str) -> List[BrowserExtensionItem]:
        """Audita extensões de navegadores baseados em Chromium (Chrome, Edge)."""
        items: List[BrowserExtensionItem] = []
        if not os.path.isdir(base_user_data_path):
            return items

        # Procurar em Default, perfis Profile *, pasta direta Extensions ou diretório direto
        profile_patterns = [
            os.path.join(base_user_data_path, "Default", "Extensions", "*"),
            os.path.join(base_user_data_path, "Profile *", "Extensions", "*"),
            os.path.join(base_user_data_path, "Extensions", "*"),
            os.path.join(base_user_data_path, "*"),
        ]

        for pattern in profile_patterns:
            for ext_id_path in glob.glob(pattern):
                if not os.path.isdir(ext_id_path):
                    continue
                ext_id = os.path.basename(ext_id_path)
                # Dentro de cada ID há pastas de versão (e.g. 1.0.0_0)
                try:
                    version_dirs = os.listdir(ext_id_path)
                    for vdir in version_dirs:
                        manifest_path = os.path.join(ext_id_path, vdir, "manifest.json")
                        if os.path.isfile(manifest_path):
                            try:
                                with open(manifest_path, "r", encoding="utf-8", errors="replace") as f:
                                    manifest = json.load(f)

                                ext_dir = os.path.join(ext_id_path, vdir)
                                name = self._resolve_manifest_name(manifest, ext_dir)
                                version = manifest.get("version", vdir)
                                desc = manifest.get("description", "")
                                perms = manifest.get("permissions", [])
                                if not isinstance(perms, list):
                                    perms = []

                                items.append(
                                    BrowserExtensionItem(
                                        browser=browser_name,
                                        extension_id=ext_id,
                                        name=name,
                                        version=version,
                                        description=str(desc),
                                        permissions=[str(p) for p in perms],
                                        install_path=ext_dir,
                                        install_source="chromium_profile",
                                    )
                                )
                            except Exception:
                                continue
                except Exception:
                    continue

        return items

    def collect(self) -> List[SecurityEvidence]:
        """Recolhe a lista de extensões instaladas nos navegadores locais."""
        evidences: List[SecurityEvidence] = []
        items: List[BrowserExtensionItem] = []

        local_app_data = os.environ.get("LOCALAPPDATA", "")
        if local_app_data:
            # 1. Google Chrome
            chrome_path = os.path.join(local_app_data, "Google", "Chrome", "User Data")
            items.extend(self._scan_chromium_extensions(chrome_path, "CHROME"))

            # 2. Microsoft Edge
            edge_path = os.path.join(local_app_data, "Microsoft", "Edge", "User Data")
            items.extend(self._scan_chromium_extensions(edge_path, "EDGE"))

        for item in items:
            obs = f"Installed {item.browser} Extension: '{item.name}' (ID: {item.extension_id}, v{item.version}, Perms: {len(item.permissions)})"
            evidence = self.create_evidence(
                asset=f"extension:{item.browser.lower()}:{item.extension_id}",
                observation=obs,
                normalized_data=item.to_dict(),
                raw_reference=item.install_path,
                confidence=1.0,
                source=f"browser_manifest_{item.browser.lower()}",
            )
            evidences.append(evidence)

        return evidences
