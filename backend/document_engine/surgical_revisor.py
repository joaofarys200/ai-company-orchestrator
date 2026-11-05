from __future__ import annotations

import difflib
import hashlib
import os
import re
import shutil
import zipfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import docx
from docx import Document
from docx.text.paragraph import Paragraph

from backend.document_engine.word_ast import WordDocumentAST, extract_ast_from_docx


@dataclass(frozen=True)
class RevisionDirective:
    strategy: str  # "LINGUISTIC", "RESTRUCTURING", "ACADEMIC", "REFORMATTING", "SURGICAL_REPLACE", "ADD_SECTION", "FULL"
    target_heading: Optional[str] = None
    replacement_text: Optional[str] = None
    find_replace_pairs: Sequence[Tuple[str, str]] = ()
    new_sections: Sequence[Tuple[str, str, int]] = ()  # (heading_text, body_text, level)
    notes: str = ""


@dataclass(frozen=True)
class PreservationAuditResult:
    media_hashes_verified: bool
    media_files_count: int
    media_files_hashes: tuple[tuple[str, str], ...]  # (filename, sha256)
    omml_equations_count_before: int
    omml_equations_count_after: int
    omml_equations_preserved: bool
    merged_cells_count_before: int
    merged_cells_count_after: int
    merged_cells_preserved: bool
    anchored_drawings_before: int
    anchored_drawings_after: int
    anchored_drawings_preserved: bool
    inline_drawings_before: int
    inline_drawings_after: int
    inline_drawings_preserved: bool
    hyperlinks_count_before: int
    hyperlinks_count_after: int
    hyperlinks_preserved: bool
    sections_count_before: int
    sections_count_after: int
    sections_preserved: bool
    headers_footers_count_before: int
    headers_footers_count_after: int
    headers_footers_preserved: bool
    all_preservation_checks_passed: bool
    details: tuple[str, ...]


@dataclass(frozen=True)
class RevisionSummary:
    original_path: str
    backup_path: str
    revised_path: str
    strategy: str
    modified_sections: tuple[str, ...]
    added_sections: tuple[str, ...]
    deleted_sections: tuple[str, ...]
    preserved_images_count: int
    preserved_tables_count: int
    preserved_headers_footers: bool
    words_before: int
    words_after: int
    unified_diff: str
    success: bool
    notes: str = ""
    preservation_audit: Optional[PreservationAuditResult] = None


class OpenXMLPreservationAuditor:
    """
    Adversarial preservation auditor for OpenXML documents.
    Validates byte-for-byte SHA-256 preservation of word/media/* files,
    intact retention of OMML equations, merged cells, drawings, hyperlinks,
    sections, and headers/footers when surgical revisions occur.
    """

    OMML_NS = "{http://schemas.openxmlformats.org/officeDocument/2006/math}"
    W_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    WP_NS = "{http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing}"

    @classmethod
    def _inspect_docx_archive(cls, path: Path) -> Dict[str, Any]:
        data: Dict[str, Any] = {
            "media_hashes": {},
            "header_footer_parts": set(),
            "omml_equations": 0,
            "grid_spans": 0,
            "v_merges": 0,
            "anchored_drawings": 0,
            "inline_drawings": 0,
            "hyperlinks": 0,
            "sections": 0,
        }

        if not path.exists():
            return data

        with zipfile.ZipFile(path, "r") as z:
            namelist = z.namelist()

            # 1. Media files hashes
            for name in namelist:
                if name.startswith("word/media/"):
                    content = z.read(name)
                    data["media_hashes"][name] = hashlib.sha256(content).hexdigest()
                elif name.startswith("word/header") or name.startswith("word/footer"):
                    data["header_footer_parts"].add(name)

            # 2. Main document XML elements
            if "word/document.xml" in namelist:
                doc_xml = z.read("word/document.xml")
                root = ET.fromstring(doc_xml)

                # OMML equations
                equations = root.findall(f".//{cls.OMML_NS}oMath")
                data["omml_equations"] = len(equations)

                # Merged cells
                grid_spans = root.findall(f".//{cls.W_NS}gridSpan")
                v_merges = root.findall(f".//{cls.W_NS}vMerge")
                data["grid_spans"] = len(grid_spans)
                data["v_merges"] = len(v_merges)

                # Drawings
                anchors = root.findall(f".//{cls.WP_NS}anchor")
                inlines = root.findall(f".//{cls.WP_NS}inline")
                data["anchored_drawings"] = len(anchors)
                data["inline_drawings"] = len(inlines)

                # Hyperlinks
                hyperlinks = root.findall(f".//{cls.W_NS}hyperlink")
                data["hyperlinks"] = len(hyperlinks)

                # Sections
                sections = root.findall(f".//{cls.W_NS}sectPr")
                data["sections"] = len(sections)

        return data

    @classmethod
    def audit(cls, orig_path: str | Path, revised_path: str | Path) -> PreservationAuditResult:
        orig_p = Path(orig_path).resolve()
        rev_p = Path(revised_path).resolve()

        before = cls._inspect_docx_archive(orig_p)
        after = cls._inspect_docx_archive(rev_p)

        details: List[str] = []

        # 1. Check media hashes
        media_verified = True
        media_tuples: List[Tuple[str, str]] = []
        for name, sha_orig in before["media_hashes"].items():
            media_tuples.append((name, sha_orig))
            sha_rev = after["media_hashes"].get(name)
            if sha_rev is None:
                media_verified = False
                details.append(f"FALHA: Ficheiro de media '{name}' removido ou corrompido após revisão.")
            elif sha_rev != sha_orig:
                media_verified = False
                details.append(f"FALHA: Hash SHA-256 de '{name}' alterado de {sha_orig[:8]} para {sha_rev[:8]}.")
            else:
                details.append(f"OK: Media '{name}' preservado byte-a-byte (SHA-256: {sha_orig[:8]}...).")

        # 2. Check OMML equations
        eq_before = before["omml_equations"]
        eq_after = after["omml_equations"]
        eq_preserved = eq_after >= eq_before
        if not eq_preserved:
            details.append(f"FALHA: Equações OMML reduzidas de {eq_before} para {eq_after}.")
        elif eq_before > 0:
            details.append(f"OK: {eq_before} equações OMML integralmente preservadas.")

        # 3. Check merged cells
        merges_before = before["grid_spans"] + before["v_merges"]
        merges_after = after["grid_spans"] + after["v_merges"]
        merges_preserved = merges_after >= merges_before
        if not merges_preserved:
            details.append(f"FALHA: Células unidas (gridSpan/vMerge) reduzidas de {merges_before} para {merges_after}.")
        elif merges_before > 0:
            details.append(f"OK: {merges_before} fusões de células de tabela preservadas.")

        # 4. Check drawings
        anc_before = before["anchored_drawings"]
        anc_after = after["anchored_drawings"]
        anc_preserved = anc_after >= anc_before

        inl_before = before["inline_drawings"]
        inl_after = after["inline_drawings"]
        inl_preserved = inl_after >= inl_before

        if not anc_preserved:
            details.append(f"FALHA: Desenhos ancorados (wp:anchor) reduzidos de {anc_before} para {anc_after}.")
        if not inl_preserved:
            details.append(f"FALHA: Desenhos em linha (wp:inline) reduzidos de {inl_before} para {inl_after}.")

        # 5. Check hyperlinks
        hyp_before = before["hyperlinks"]
        hyp_after = after["hyperlinks"]
        hyp_preserved = hyp_after >= hyp_before
        if hyp_before > 0 and hyp_preserved:
            details.append(f"OK: {hyp_before} hiperligações mantidas.")

        # 6. Check sections
        sec_before = before["sections"]
        sec_after = after["sections"]
        sec_preserved = sec_after >= sec_before

        # 7. Check header/footer parts
        hf_before = len(before["header_footer_parts"])
        hf_after = len(after["header_footer_parts"])
        hf_preserved = hf_after >= hf_before
        if hf_before > 0 and hf_preserved:
            details.append(f"OK: Partes de cabeçalho e rodapé ({hf_before}) preservadas.")

        all_passed = (
            media_verified
            and eq_preserved
            and merges_preserved
            and anc_preserved
            and inl_preserved
            and hyp_preserved
            and sec_preserved
            and hf_preserved
        )

        return PreservationAuditResult(
            media_hashes_verified=media_verified,
            media_files_count=len(before["media_hashes"]),
            media_files_hashes=tuple(media_tuples),
            omml_equations_count_before=eq_before,
            omml_equations_count_after=eq_after,
            omml_equations_preserved=eq_preserved,
            merged_cells_count_before=merges_before,
            merged_cells_count_after=merges_after,
            merged_cells_preserved=merges_preserved,
            anchored_drawings_before=anc_before,
            anchored_drawings_after=anc_after,
            anchored_drawings_preserved=anc_preserved,
            inline_drawings_before=inl_before,
            inline_drawings_after=inl_after,
            inline_drawings_preserved=inl_preserved,
            hyperlinks_count_before=hyp_before,
            hyperlinks_count_after=hyp_after,
            hyperlinks_preserved=hyp_preserved,
            sections_count_before=sec_before,
            sections_count_after=sec_after,
            sections_preserved=sec_preserved,
            headers_footers_count_before=hf_before,
            headers_footers_count_after=hf_after,
            headers_footers_preserved=hf_preserved,
            all_preservation_checks_passed=all_passed,
            details=tuple(details),
        )


class SurgicalRevisor:
    """
    Performs surgical, in-place revisions on existing Microsoft Word documents.
    Preserves untouched tables, images, hyperlinks, headers, footers, and styles.
    Never replaces an existing document with a crude plain text conversion.
    """

    @classmethod
    def revise(
        cls,
        docx_path: str | Path,
        directive: RevisionDirective,
        output_path: Optional[str | Path] = None,
    ) -> Tuple[str, RevisionSummary]:
        orig_p = Path(docx_path).resolve()
        if not orig_p.exists():
            raise FileNotFoundError(f"Documento original não encontrado: {orig_p}")

        # 1. Create safe backup before modification
        backup_p = orig_p.with_name(f"{orig_p.stem}_backup_{orig_p.suffix}")
        shutil.copy2(orig_p, backup_p)

        target_out = Path(output_path).resolve() if output_path else orig_p.with_name(f"{orig_p.stem}_revised{orig_p.suffix}")

        # 2. Extract initial AST for baseline comparison and preservation audit
        ast_before = extract_ast_from_docx(orig_p)
        images_count_before = len(ast_before.images)
        tables_count_before = len(ast_before.tables)

        # 3. Open document directly with python-docx to operate in-place
        doc = Document(str(orig_p))

        modified_sections: List[str] = []
        added_sections: List[str] = []
        deleted_sections: List[str] = []

        # 4. Execute Revision Strategy
        strat = directive.strategy.upper()

        if strat == "FIND_REPLACE" or directive.find_replace_pairs:
            # Linguistic / Find-and-replace across body text
            for find_str, repl_str in directive.find_replace_pairs:
                for p in doc.paragraphs:
                    if find_str in p.text:
                        # Replace in runs where possible to keep styling
                        replaced = False
                        for run in p.runs:
                            if find_str in run.text:
                                run.text = run.text.replace(find_str, repl_str)
                                replaced = True
                        if not replaced:
                            p.text = p.text.replace(find_str, repl_str)
                        modified_sections.append(f"Substituição: '{find_str}' -> '{repl_str}'")

        elif strat in {"SURGICAL_REPLACE", "RESTRUCTURING", "ACADEMIC"} and directive.target_heading:
            # Locate targeted heading and replace only its underlying text
            target_norm = directive.target_heading.strip().lower()
            start_p_idx = -1
            end_p_idx = -1
            target_level = 1

            for idx, p in enumerate(doc.paragraphs):
                p_text_norm = p.text.strip().lower()
                is_heading = (p.style and "heading" in p.style.name.lower()) or (p.style and "título" in p.style.name.lower())
                if is_heading and target_norm in p_text_norm:
                    start_p_idx = idx
                    target_level = int(p.style.name.split()[-1]) if p.style.name.split()[-1].isdigit() else 1
                    break

            if start_p_idx != -1:
                # Find boundary of this section (next heading with level <= target_level)
                for idx in range(start_p_idx + 1, len(doc.paragraphs)):
                    p = doc.paragraphs[idx]
                    is_heading = (p.style and "heading" in p.style.name.lower()) or (p.style and "título" in p.style.name.lower())
                    if is_heading:
                        lvl = int(p.style.name.split()[-1]) if p.style.name.split()[-1].isdigit() else 1
                        if lvl <= target_level:
                            end_p_idx = idx
                            break

                if end_p_idx == -1:
                    end_p_idx = len(doc.paragraphs)

                # Now replace content between start_p_idx and end_p_idx
                first_body_idx = start_p_idx + 1
                new_paragraphs = [p_txt for p_txt in (directive.replacement_text or "").split("\n\n") if p_txt.strip()]

                if first_body_idx < end_p_idx and new_paragraphs:
                    doc.paragraphs[first_body_idx].text = new_paragraphs[0]
                    # Clear remaining paragraphs in the section range
                    for extra_idx in range(first_body_idx + 1, end_p_idx):
                        doc.paragraphs[extra_idx].text = ""

                    # If multiple new paragraphs, insert them after first_body_idx
                    curr_p = doc.paragraphs[first_body_idx]
                    for extra_para in new_paragraphs[1:]:
                        curr_p = curr_p.insert_paragraph_before(extra_para)
                elif new_paragraphs:
                    h_p = doc.paragraphs[start_p_idx]
                    for p_txt in reversed(new_paragraphs):
                        h_p.insert_paragraph_before(p_txt)

                modified_sections.append(directive.target_heading)

        elif strat == "ADD_SECTION" or directive.new_sections:
            # Append new sections
            for h_text, body_text, lvl in directive.new_sections:
                style_name = f"Heading {min(6, max(1, lvl))}"
                h = doc.add_paragraph(h_text, style=style_name)
                h.paragraph_format.keep_with_next = True
                for b_para in body_text.split("\n\n"):
                    if b_para.strip():
                        doc.add_paragraph(b_para.strip())
                added_sections.append(h_text)

        # 5. Save revised document
        target_out.parent.mkdir(parents=True, exist_ok=True)
        doc.save(str(target_out))

        # 6. Extract AST after revision to verify structural integrity
        ast_after = extract_ast_from_docx(target_out)
        images_count_after = len(ast_after.images)
        tables_count_after = len(ast_after.tables)

        # Verify preservation guarantees via OpenXMLPreservationAuditor
        preservation_audit = OpenXMLPreservationAuditor.audit(orig_p, target_out)

        images_preserved = images_count_after >= images_count_before
        tables_preserved = tables_count_after >= tables_count_before
        headers_footers_preserved = len(ast_after.sections) >= len(ast_before.sections)

        # 7. Generate unified diff
        before_lines = ast_before.raw_text.splitlines(keepends=True)
        after_lines = ast_after.raw_text.splitlines(keepends=True)
        diff_lines = list(
            difflib.unified_diff(
                before_lines,
                after_lines,
                fromfile=f"a/{orig_p.name}",
                tofile=f"b/{target_out.name}",
                n=3,
            )
        )
        unified_diff_str = "".join(diff_lines)

        overall_success = preservation_audit.all_preservation_checks_passed

        summary = RevisionSummary(
            original_path=str(orig_p),
            backup_path=str(backup_p),
            revised_path=str(target_out),
            strategy=strat,
            modified_sections=tuple(modified_sections),
            added_sections=tuple(added_sections),
            deleted_sections=tuple(deleted_sections),
            preserved_images_count=images_count_after,
            preserved_tables_count=tables_count_after,
            preserved_headers_footers=headers_footers_preserved,
            words_before=ast_before.metadata.total_words,
            words_after=ast_after.metadata.total_words,
            unified_diff=unified_diff_str,
            success=overall_success,
            notes=directive.notes or "Revisão cirúrgica concluída com sucesso.",
            preservation_audit=preservation_audit,
        )

        return str(target_out), summary
