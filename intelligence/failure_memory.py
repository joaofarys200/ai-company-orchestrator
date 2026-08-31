"""
JARVIS OS — Failure Memory & Lesson Recorder (Fase 10: Coding Agent 2.0)
Registo estruturado de lições, causas raízes, evidências e correções no Obsidian Knowledge Vault.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
import datetime
import json
import os
import re
from typing import Any, Dict, List, Optional


@dataclass(slots=True)
class FailureLesson:
    """Registo canónico de lição aprendida a partir de uma falha real."""
    lesson_id: str
    title: str
    component: str
    issue_type: str
    failure_record: str
    evidence: str
    root_cause: str
    fix_applied: str
    test_verification: str
    tags: List[str] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_markdown(self) -> str:
        tags_str = " ".join([f"#{t}" for t in self.tags])
        return f"""# Lesson — {self.title}

- **ID**: `{self.lesson_id}`
- **Data**: `{self.timestamp}`
- **Componente**: `{self.component}`
- **Tipo de Problema**: `{self.issue_type}`
- **Tags**: {tags_str}

---

## 1. Registo da Falha (Failure Record)
{self.failure_record}

---

## 2. Evidência Observada (Evidence)
```text
{self.evidence}
```

---

## 3. Causa Raiz (Root Cause)
{self.root_cause}

---

## 4. Correção Aplicada (Fix)
{self.fix_applied}

---

## 5. Teste e Verificação (Test)
{self.test_verification}
"""


class FailureMemoryStore:
    """Gestor de armazenamento e consulta de lições no Obsidian Knowledge Vault."""

    def __init__(self, vault_dir: Optional[str] = None) -> None:
        if vault_dir:
            self.lessons_dir = os.path.join(vault_dir, "09 - JARVIS", "Lessons", "Autonomous Repair Lessons")
        else:
            # Padrão no workspace
            self.lessons_dir = os.path.join("obsidian_vault", "09 - JARVIS", "Lessons", "Autonomous Repair Lessons")
        os.makedirs(self.lessons_dir, exist_ok=True)

    def record_lesson(self, lesson: FailureLesson) -> str:
        """Persiste uma lição em formato Markdown no Obsidian Vault."""
        safe_title = re.sub(r'[^\w\s-]', '', lesson.title).strip().replace(' ', '_')
        filename = f"Lesson - {lesson.lesson_id} - {safe_title}.md"
        file_path = os.path.join(self.lessons_dir, filename)

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(lesson.to_markdown())

        return file_path

    def query_lessons(self, query: str, limit: int = 5) -> List[FailureLesson]:
        """Pesquisa lições relevantes por palavras-chave nos metadados ou conteúdo."""
        lessons: List[FailureLesson] = []
        if not os.path.exists(self.lessons_dir):
            return lessons

        query_terms = query.lower().split()

        for fname in os.listdir(self.lessons_dir):
            if fname.endswith(".md"):
                fpath = os.path.join(self.lessons_dir, fname)
                try:
                    with open(fpath, "r", encoding="utf-8", errors="replace") as f:
                        content = f.read()
                        lower_content = content.lower()
                        if any(term in lower_content for term in query_terms):
                            # Extrai dados básicos
                            lesson_id_match = re.search(r"\*\*ID\*\*:\s*`([^`]+)`", content)
                            title_match = re.search(r"# Lesson — ([^\n]+)", content)
                            lid = lesson_id_match.group(1) if lesson_id_match else fname
                            title = title_match.group(1) if title_match else fname

                            lessons.append(FailureLesson(
                                lesson_id=lid,
                                title=title,
                                component="Coding Agent",
                                issue_type="REPAIR_LESSON",
                                failure_record=content[:200],
                                evidence="",
                                root_cause="",
                                fix_applied="",
                                test_verification="",
                            ))
                except OSError:
                    continue

        return lessons[:limit]
