"""
JARVIS OS — Obsidian Knowledge Graph Autonomous Reconciler & Healer
Eliminates orphan nodes (0 links) by establishing bidirectional semantic wikilinks
between Lectures, ADRs, Lessons, and domain MOCs (Maps of Content).
"""

import os
import re
from pathlib import Path
from typing import Dict, Set, List, Tuple

VAULT_DIR = Path("obsidian_vault")
MOC_DIR = VAULT_DIR / "00 - MOC"

def build_lectures_moc() -> str:
    lectures_dir = VAULT_DIR / "10 - Lectures"
    gptsi_notes = sorted([f.stem for f in (lectures_dir / "GPTSI").glob("*.md")])
    ia_notes = sorted([f.stem for f in (lectures_dir / "Inteligência Artificial").glob("*.md")])
    metod_notes = sorted([f.stem for f in (lectures_dir / "Metodologia de Investigacao").glob("*.md")])

    content = [
        "---",
        "type: moc",
        "domain: academic",
        "tags:",
        "  - lectures",
        "  - academic",
        "  - moc",
        "  - study",
        "status: verified",
        "---",
        "",
        "# 🎓 Lectures & Academic Knowledge MOC",
        "",
        "Mapa de Conteúdo estruturado das unidades curriculares, transcrições e sínteses pedagógicas do **JARVIS OS**.",
        "",
        "---",
        "",
        "## 📚 Unidades Curriculares & Materiais de Estudo",
        "",
        "### 1. Gestão de Projetos e Tecnologias / Sistemas de Informação (GPTSI)",
        "- **Domínios Relacionados:** [[Software Engineering Index]] | [[Business Index]] | [[JARVIS Index]]",
    ]
    for n in gptsi_notes:
        content.append(f"- [[{n}]]")

    content.extend([
        "",
        "### 2. Inteligência Artificial (IA)",
        "- **Domínios Relacionados:** [[AI Index]] | [[Agent Systems Architecture]] | [[Agentic RAG, Query Decomposition and Cross-Encoder Reranking]]",
    ])
    for n in ia_notes:
        content.append(f"- [[{n}]]")

    content.extend([
        "",
        "### 3. Metodologia de Investigação",
        "- **Domínios Relacionados:** [[AI Index]] | [[Business Index]]",
    ])
    for n in metod_notes:
        content.append(f"- [[{n}]]")

    content.extend([
        "",
        "---",
        "",
        "## 🔗 Conexões ao Grafo Central",
        "- [[00 - Knowledge Index]] — Índice Geral do Cofre",
        "- [[AI Index]] — Modelos, RAG, Ingestão Multimodal",
        "- [[Software Engineering Index]] — Arquitetura de Software e Padrões",
        "- [[JARVIS Index]] — Subsistemas Internos e Motor de Estudo",
        ""
    ])
    return "\n".join(content)

def update_master_index():
    master_path = MOC_DIR / "00 - Knowledge Index.md"
    if not master_path.exists():
        return
    text = master_path.read_text(encoding="utf-8")
    if "[[Lectures Index]]" not in text:
        # Add to table
        row = "| **10. Lectures & Estudo** | [[Lectures Index]] | Aulas universitárias, transcrições com alinhamento temporal, Cornell Notes e sínteses |\n"
        target = "| **09. JARVIS Internal** | [[JARVIS Index]] | Arquitetura, Swarm, Persistência Durável de Missões (Fases 24–25), Motor Multimodal de Estudos, Voice/Gemini Live, Lessons, ADRs, Gaps |\n"
        if target in text:
            text = text.replace(target, target + row)
        else:
            text = text.replace("## 🏛️ Princípios", f"| **10. Lectures** | [[Lectures Index]] | Aulas e sínteses |\n\n## 🏛️ Princípios")
        master_path.write_text(text, encoding="utf-8")
        print("Updated 00 - Knowledge Index.md with Lectures Index.")

def update_jarvis_index():
    jarvis_idx = MOC_DIR / "JARVIS Index.md"
    if not jarvis_idx.exists():
        return
    text = jarvis_idx.read_text(encoding="utf-8")
    
    # Check for ADR-014 and ADR-015
    if "ADR-014" not in text:
        adrs_to_add = (
            "- [[ADR-014 - Automated Defense and Resilience for FINDING-02-NETWORK-RETRY-JITTER]] — Resiliência de rede e retry jitter.\n"
            "- [[ADR-014 - Automated Defense and Resilience for FINDING-03-WEBSOCKET-PATH-JAIL]] — Isolamento de rotas de WebSocket.\n"
            "- [[ADR-015 - AST Streaming Memory Optimization for FINDING-P8-AST-STREAMING-BUFFER]] — Otimização de streaming de buffers AST.\n"
        )
        text = text.replace(
            "- [[ADR-013 - Economic Evidence Provenance and Confidence Capping]] — Teto rígido de $0.20$ de confiança para dados sintéticos.\n",
            "- [[ADR-013 - Economic Evidence Provenance and Confidence Capping]] — Teto rígido de $0.20$ de confiança para dados sintéticos.\n" + adrs_to_add
        )
    if "Lesson - Synthetic Revenue Rejection" not in text:
        lesson_row = "- [[Lesson - Synthetic Revenue Rejection]] — Rejeição estrita de métricas sintéticas de receita.\n"
        text = text.replace("## 📋 Decisões Arquiteturais", lesson_row + "\n## 📋 Decisões Arquiteturais")

    jarvis_idx.write_text(text, encoding="utf-8")
    print("Updated JARVIS Index.md with missing ADRs and Lessons.")

def enrich_lecture_notes():
    lectures_dir = VAULT_DIR / "10 - Lectures"
    for f in lectures_dir.rglob("*.md"):
        if f.name == "Index.md":
            continue
        text = f.read_text(encoding="utf-8")
        if "## 🔗 Grafo de Conhecimento" in text or "## 🔗 Referências" in text:
            continue
        
        # Determine parent subject
        subject = f.parent.name
        if "Inteligência Artificial" in subject:
            related = "- **MOC Central:** [[Lectures Index]] | [[AI Index]]\n- **Tópicos Relacionados:** [[Agent Systems Architecture]], [[Agentic RAG, Query Decomposition and Cross-Encoder Reranking]], [[Model Context Protocol (MCP) and Capability Discovery Architecture]]"
        elif "GPTSI" in subject:
            related = "- **MOC Central:** [[Lectures Index]] | [[Software Engineering Index]]\n- **Tópicos Relacionados:** [[API Contract Evolution, Backward Compatibility and Schema Versioning]], [[Business Index]]"
        else:
            related = "- **MOC Central:** [[Lectures Index]]\n- **Tópicos Relacionados:** [[AI Index]], [[Business Index]]"

        footer = f"\n\n---\n\n## 🔗 Grafo de Conhecimento & MOC\n{related}\n"
        f.write_text(text + footer, encoding="utf-8")
        print(f"Enriched: {f.name}")

def enrich_remaining_orphans():
    # Validation note
    val_note = VAULT_DIR / "09 - JARVIS" / "E2E_Validation_Note.md"
    if val_note.exists():
        t = val_note.read_text(encoding="utf-8")
        if "[[JARVIS Index]]" not in t:
            val_note.write_text(t + "\n\n---\n## 🔗 Referências\n- [[JARVIS Index]]\n- [[00 - Knowledge Index]]\n", encoding="utf-8")

def count_orphans() -> Tuple[int, List[str]]:
    md_files = list(VAULT_DIR.glob("**/*.md"))
    note_names = {f.stem.lower(): f for f in md_files}
    links = {f.stem: set() for f in md_files}
    backlinks = {f.stem: set() for f in md_files}
    link_pattern = re.compile(r'\[\[(.*?)\]\]')

    for f in md_files:
        text = f.read_text(encoding='utf-8', errors='ignore')
        found_links = link_pattern.findall(text)
        for raw in found_links:
            target = raw.split('|')[0].strip().replace('.md', '')
            target_name = target.split('#')[0].strip()
            if target_name.lower() in note_names:
                resolved_stem = note_names[target_name.lower()].stem
                if resolved_stem != f.stem:
                    links[f.stem].add(resolved_stem)
                    backlinks[resolved_stem].add(f.stem)

    orphans = []
    for f in md_files:
        stem = f.stem
        if len(links[stem]) + len(backlinks[stem]) == 0:
            orphans.append(str(f.relative_to(VAULT_DIR)))
    return len(orphans), orphans

def main():
    print("=== BEFORE RECONCILIATION ===")
    count_before, orphans_before = count_orphans()
    print(f"Orphan notes: {count_before} / 255")

    # 1. Create 00 - MOC/Lectures Index.md
    moc_content = build_lectures_moc()
    (MOC_DIR / "Lectures Index.md").write_text(moc_content, encoding="utf-8")
    print("Created 00 - MOC/Lectures Index.md")

    # Also update 10 - Lectures/Index.md to point to Lectures Index
    (VAULT_DIR / "10 - Lectures" / "Index.md").write_text(moc_content, encoding="utf-8")

    # 2. Update 00 - Knowledge Index.md
    update_master_index()

    # 3. Update JARVIS Index.md
    update_jarvis_index()

    # 4. Enrich lecture notes with bidirectional links
    enrich_lecture_notes()

    # 5. Enrich remaining orphans
    enrich_remaining_orphans()

    print("\n=== AFTER RECONCILIATION ===")
    count_after, orphans_after = count_orphans()
    print(f"Orphan notes: {count_after} / 256")
    if orphans_after:
        print("Remaining orphans:")
        for o in orphans_after:
            print(" -", o)
    else:
        print("SUCCESS: 0 orphan nodes! The entire Knowledge Graph is 100% interconnected!")

if __name__ == "__main__":
    main()

