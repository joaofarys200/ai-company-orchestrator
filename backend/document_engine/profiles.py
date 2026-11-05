from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, List, Optional, Sequence, Tuple

from backend.document_engine.word_ast import WordDocumentAST


class DocumentProfileType(str, Enum):
    ACADEMIC = "ACADEMIC"
    TECHNICAL_SPEC = "TECHNICAL_SPEC"
    BUSINESS_PROPOSAL = "BUSINESS_PROPOSAL"
    EXECUTIVE_MEMO = "EXECUTIVE_MEMO"
    GENERIC = "GENERIC"


@dataclass(frozen=True)
class DocumentProfile:
    profile_type: DocumentProfileType
    display_name: str
    font_primary: str
    font_headings: str
    font_mono: str
    accent_color_hex: str  # e.g. "1B365D"
    secondary_color_hex: str  # e.g. "4A607A"
    text_color_hex: str  # e.g. "222222"
    line_spacing: float  # e.g. 1.5 or 1.15
    paragraph_space_after_pt: float  # e.g. 6.0
    paragraph_space_before_pt: float  # e.g. 0.0
    top_margin_cm: float
    bottom_margin_cm: float
    left_margin_cm: float
    right_margin_cm: float
    requires_toc: bool
    requires_abstract: bool
    requires_executive_summary: bool
    requires_page_numbers: bool
    requires_references: bool
    mandatory_sections: tuple[str, ...]
    recommended_sections: tuple[str, ...]

    def validate_ast_conformance(self, ast: WordDocumentAST) -> List[str]:
        """Validates that document conforms to this profile's structural requirements."""
        issues: List[str] = []
        headings_lower = [h.text.lower() for h in ast.headings]

        # Check mandatory sections
        for sec in self.mandatory_sections:
            sec_lower = sec.lower()
            matched = any(sec_lower in h for h in headings_lower)
            if not matched:
                issues.append(f"Secção obrigatória ausente no perfil {self.display_name}: '{sec}'")

        # Check references if required
        if self.requires_references:
            ref_found = any(
                term in h for h in headings_lower for term in ["referências", "bibliografia", "references"]
            )
            if not ref_found:
                issues.append(f"O perfil {self.display_name} exige secção de 'Referências' ou 'Bibliografia'.")

        # Check executive summary / abstract
        if self.requires_abstract:
            abs_found = any(term in h for h in headings_lower for term in ["resumo", "abstract"])
            if not abs_found:
                issues.append(f"O perfil {self.display_name} exige secção de 'Resumo' ou 'Abstract'.")

        if self.requires_executive_summary:
            exec_found = any(term in h for h in headings_lower for term in ["sumário executivo", "executive summary", "resumo executivo"])
            if not exec_found:
                issues.append(f"O perfil {self.display_name} exige 'Sumário Executivo'.")

        return issues


class AcademicProfile(DocumentProfile):
    def __init__(self) -> None:
        super().__init__(
            profile_type=DocumentProfileType.ACADEMIC,
            display_name="Trabalho Académico / Investigação",
            font_primary="Times New Roman",
            font_headings="Times New Roman",
            font_mono="Courier New",
            accent_color_hex="1B365D",
            secondary_color_hex="334D6E",
            text_color_hex="111111",
            line_spacing=1.5,
            paragraph_space_after_pt=6.0,
            paragraph_space_before_pt=0.0,
            top_margin_cm=2.5,
            bottom_margin_cm=2.5,
            left_margin_cm=3.0,  # 3 cm left margin standard
            right_margin_cm=2.0,  # 2 cm right margin standard
            requires_toc=True,
            requires_abstract=True,
            requires_executive_summary=False,
            requires_page_numbers=True,
            requires_references=True,
            mandatory_sections=("Introdução", "Metodologia", "Resultados", "Discussão", "Conclusão"),
            recommended_sections=("Resumo", "Enquadramento Teórico", "Trabalho Relacionado", "Referências"),
        )


class TechnicalSpecProfile(DocumentProfile):
    def __init__(self) -> None:
        super().__init__(
            profile_type=DocumentProfileType.TECHNICAL_SPEC,
            display_name="Especificação Técnica / Relatório de Engenharia",
            font_primary="Calibri",
            font_headings="Calibri Light",
            font_mono="Consolas",
            accent_color_hex="0E639C",
            secondary_color_hex="007ACC",
            text_color_hex="1E1E1E",
            line_spacing=1.15,
            paragraph_space_after_pt=5.0,
            paragraph_space_before_pt=2.0,
            top_margin_cm=2.5,
            bottom_margin_cm=2.5,
            left_margin_cm=2.5,
            right_margin_cm=2.5,
            requires_toc=True,
            requires_abstract=False,
            requires_executive_summary=True,
            requires_page_numbers=True,
            requires_references=False,
            mandatory_sections=("Introdução", "Arquitetura", "Especificação de Componentes", "Validação e Testes"),
            recommended_sections=("Sumário Executivo", "Requisitos do Sistema", "Segurança", "Histórico de Versões"),
        )


class BusinessProposalProfile(DocumentProfile):
    def __init__(self) -> None:
        super().__init__(
            profile_type=DocumentProfileType.BUSINESS_PROPOSAL,
            display_name="Proposta Empresarial / Comercial",
            font_primary="Arial",
            font_headings="Arial",
            font_mono="Consolas",
            accent_color_hex="0F4C81",
            secondary_color_hex="2E75B6",
            text_color_hex="222222",
            line_spacing=1.2,
            paragraph_space_after_pt=6.0,
            paragraph_space_before_pt=0.0,
            top_margin_cm=2.5,
            bottom_margin_cm=2.5,
            left_margin_cm=2.5,
            right_margin_cm=2.5,
            requires_toc=False,
            requires_abstract=False,
            requires_executive_summary=True,
            requires_page_numbers=True,
            requires_references=False,
            mandatory_sections=("Contexto e Necessidade", "Proposta de Solução", "Entregáveis", "Investimento e Prazos"),
            recommended_sections=("Sumário Executivo", "Equipa e Competências", "Termos e Condições"),
        )


class ExecutiveMemoProfile(DocumentProfile):
    def __init__(self) -> None:
        super().__init__(
            profile_type=DocumentProfileType.EXECUTIVE_MEMO,
            display_name="Memorando Executivo",
            font_primary="Calibri",
            font_headings="Calibri",
            font_mono="Consolas",
            accent_color_hex="203764",
            secondary_color_hex="305496",
            text_color_hex="262626",
            line_spacing=1.15,
            paragraph_space_after_pt=4.0,
            paragraph_space_before_pt=2.0,
            top_margin_cm=2.5,
            bottom_margin_cm=2.5,
            left_margin_cm=2.5,
            right_margin_cm=2.5,
            requires_toc=False,
            requires_abstract=False,
            requires_executive_summary=False,
            requires_page_numbers=True,
            requires_references=False,
            mandatory_sections=("Contexto", "Análise", "Recomendações e Próximos Passos"),
            recommended_sections=("Decisões Solicitadas", "Impacto Orçamental"),
        )


class GenericProfile(DocumentProfile):
    def __init__(self) -> None:
        super().__init__(
            profile_type=DocumentProfileType.GENERIC,
            display_name="Documento Geral",
            font_primary="Calibri",
            font_headings="Calibri Light",
            font_mono="Consolas",
            accent_color_hex="1B365D",
            secondary_color_hex="4A607A",
            text_color_hex="222222",
            line_spacing=1.15,
            paragraph_space_after_pt=6.0,
            paragraph_space_before_pt=0.0,
            top_margin_cm=2.5,
            bottom_margin_cm=2.5,
            left_margin_cm=2.5,
            right_margin_cm=2.5,
            requires_toc=False,
            requires_abstract=False,
            requires_executive_summary=False,
            requires_page_numbers=True,
            requires_references=False,
            mandatory_sections=(),
            recommended_sections=(),
        )


PROFILES: dict[DocumentProfileType, DocumentProfile] = {
    DocumentProfileType.ACADEMIC: AcademicProfile(),
    DocumentProfileType.TECHNICAL_SPEC: TechnicalSpecProfile(),
    DocumentProfileType.BUSINESS_PROPOSAL: BusinessProposalProfile(),
    DocumentProfileType.EXECUTIVE_MEMO: ExecutiveMemoProfile(),
    DocumentProfileType.GENERIC: GenericProfile(),
}


def get_profile(profile_type_or_str: DocumentProfileType | str) -> DocumentProfile:
    """Returns corresponding DocumentProfile instance."""
    if isinstance(profile_type_or_str, DocumentProfileType):
        return PROFILES.get(profile_type_or_str, PROFILES[DocumentProfileType.GENERIC])
    key = str(profile_type_or_str).upper()
    for pt in DocumentProfileType:
        if pt.value == key or pt.name == key:
            return PROFILES[pt]
    if "ACADEM" in key or "ARTIGO" in key or "RELATÓRIO CIENT" in key or "TESE" in key:
        return PROFILES[DocumentProfileType.ACADEMIC]
    if "TECNIC" in key or "TECH" in key or "ENGENHARIA" in key or "SPEC" in key:
        return PROFILES[DocumentProfileType.TECHNICAL_SPEC]
    if "PROPOSTA" in key or "NEGOCIO" in key or "COMERCIAL" in key or "BUSINESS" in key:
        return PROFILES[DocumentProfileType.BUSINESS_PROPOSAL]
    if "MEMO" in key or "ADMINISTRAT" in key:
        return PROFILES[DocumentProfileType.EXECUTIVE_MEMO]
    return PROFILES[DocumentProfileType.GENERIC]
