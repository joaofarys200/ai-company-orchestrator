"""
JARVIS OS — Study Engine Phase 5: Document Design System (Componente 5.6)
Define identidades visuais e tipográficas académicas consistentes, paletas cromáticas,
escala tipográfica, caixas pedagógicas semânticas, estilos de tabelas, diagramas e paginação.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple

from services.study_document_generation.contracts import CalloutBoxKind


def hex_to_rgb_float(hex_str: str) -> Tuple[float, float, float]:
    """Converte cor hexadecimal (#RRGGBB) para tuplo (r, g, b) em [0.0, 1.0] (PyMuPDF)."""
    clean = hex_str.lstrip("#").strip()
    if len(clean) == 3:
        clean = "".join(c * 2 for c in clean)
    if len(clean) != 6:
        clean = "1B365D"
    r = int(clean[0:2], 16) / 255.0
    g = int(clean[2:4], 16) / 255.0
    b = int(clean[4:6], 16) / 255.0
    return (round(r, 4), round(g, 4), round(b, 4))


def hex_to_rgb_int(hex_str: str) -> Tuple[int, int, int]:
    """Converte cor hexadecimal (#RRGGBB) para tuplo (R, G, B) em [0, 255] (Pillow / python-docx)."""
    clean = hex_str.lstrip("#").strip()
    if len(clean) == 3:
        clean = "".join(c * 2 for c in clean)
    if len(clean) != 6:
        clean = "1B365D"
    return (int(clean[0:2], 16), int(clean[2:4], 16), int(clean[4:6], 16))


@dataclass(frozen=True)
class CalloutBoxTheme:
    kind: str
    badge_label: str
    border_hex: str
    background_hex: str
    title_hex: str
    text_hex: str


@dataclass(frozen=True)
class TypographicScale:
    doc_title_pt: float = 21.0
    doc_subtitle_pt: float = 11.5
    chapter_kicker_pt: float = 9.0
    chapter_title_pt: float = 16.0
    section_title_pt: float = 13.0
    subsection_title_pt: float = 11.2
    body_pt: float = 10.2
    body_line_height_factor: float = 1.42
    callout_title_pt: float = 9.5
    callout_body_pt: float = 9.5
    table_header_pt: float = 9.2
    table_cell_pt: float = 9.0
    equation_pt: float = 10.5
    caption_pt: float = 8.8
    provenance_pt: float = 8.0
    toc_chapter_pt: float = 10.5
    toc_section_pt: float = 9.5
    header_footer_pt: float = 8.2


@dataclass(frozen=True)
class PageGeometrySpec:
    page_width_pt: float = 595.28   # A4 width (210 mm)
    page_height_pt: float = 841.89  # A4 height (297 mm)
    margin_top_pt: float = 62.0     # ~2.19 cm
    margin_bottom_pt: float = 60.0  # ~2.12 cm
    margin_left_pt: float = 62.0    # ~2.19 cm
    margin_right_pt: float = 54.0   # ~1.90 cm
    header_y_pt: float = 34.0
    footer_y_pt: float = 806.0
    paragraph_gap_pt: float = 6.5
    section_gap_before_pt: float = 14.0
    section_gap_after_pt: float = 6.0
    chapter_gap_before_pt: float = 18.0
    chapter_gap_after_pt: float = 10.0
    min_heading_follow_pt: float = 62.0  # keep-with-next protection threshold

    @property
    def content_width_pt(self) -> float:
        return self.page_width_pt - self.margin_left_pt - self.margin_right_pt

    @property
    def max_content_y_pt(self) -> float:
        return self.page_height_pt - self.margin_bottom_pt


@dataclass(frozen=True)
class DesignStyleProfile:
    profile_id: str
    display_name: str
    description: str
    # Fontes para DOCX / Windows TrueType
    docx_font_body: str
    docx_font_headings: str
    docx_font_mono: str
    ttf_regular_candidates: Tuple[str, ...]
    ttf_bold_candidates: Tuple[str, ...]
    ttf_italic_candidates: Tuple[str, ...]
    ttf_mono_candidates: Tuple[str, ...]
    # Paleta Cromática Académica
    primary_hex: str          # Cor principal (Capítulos, Cabeçalhos de tabela)
    secondary_hex: str        # Cor secundária (Secções, Subtítulos)
    accent_hex: str           # Destaques de navegação
    text_primary_hex: str     # Corpo de texto
    text_muted_hex: str       # Legendas, notas de proveniência, cabeçalhos/rodapés
    surface_light_hex: str    # Fundo suave de blocos
    surface_zebra_hex: str    # Linhas pares de tabela
    border_subtle_hex: str    # Bordas discretas de tabela e divisores
    # Cores Epistémicas (Fidelidade à Fonte)
    fact_accent_hex: str      # SOURCE_FACT (Verde/Esmeralda Académico)
    fact_bg_hex: str
    inference_accent_hex: str # MODEL_INFERENCE (Âmbar/Ocre Analítico)
    inference_bg_hex: str
    hypothetical_accent_hex: str  # HYPOTHETICAL_EXAMPLE (Roxo/Índigo Pedagógico)
    hypothetical_bg_hex: str
    limitation_accent_hex: str    # LIMITATION / WARNING (Carmesim Sóbrio)
    limitation_bg_hex: str
    # Geometria e Tipografia
    typography: TypographicScale = field(default_factory=TypographicScale)
    geometry: PageGeometrySpec = field(default_factory=PageGeometrySpec)
    callout_themes: Dict[str, CalloutBoxTheme] = field(default_factory=dict)

    @property
    def bg_subtle_hex(self) -> str:
        return self.surface_light_hex

    @property
    def accent_color_hex(self) -> str:
        return self.accent_hex

    def get_callout_theme(self, callout_kind: Optional[str]) -> CalloutBoxTheme:
        key = str(callout_kind or CalloutBoxKind.CONCEPT_BOX.value)
        if key in self.callout_themes:
            return self.callout_themes[key]
        return self.callout_themes[CalloutBoxKind.CONCEPT_BOX.value]

    def get_epistemic_style(
        self,
        epistemic_status: Optional[str],
        is_hypothetical_example: bool = False,
    ) -> Tuple[str, str, str]:
        """Devolve (etiqueta_pt, accent_hex, bg_hex) rigorosamente fiel à classificação epistémica."""
        if is_hypothetical_example:
            return ("EXEMPLO HIPOTÉTICO (MODEL_INFERENCE)", self.hypothetical_accent_hex, self.hypothetical_bg_hex)
        st = str(epistemic_status or "UNVERIFIED").upper().strip()
        if st == "SOURCE_FACT":
            return ("FACTO DA FONTE [SOURCE_FACT]", self.fact_accent_hex, self.fact_bg_hex)
        if st == "MODEL_INFERENCE":
            return ("INFERÊNCIA / PEDAGÓGICO [MODEL_INFERENCE]", self.inference_accent_hex, self.inference_bg_hex)
        if st == "NOT_FOUND":
            return ("AUSENTE NA FONTE [NOT_FOUND]", self.limitation_accent_hex, self.limitation_bg_hex)
        return ("NÃO VERIFICADO [UNVERIFIED]", self.limitation_accent_hex, "#F8FAFC")

    def resolve_font_path(self, variant: str = "regular") -> Optional[str]:
        """Resolve caminho para fonte TrueType instalada no sistema Windows, se disponível."""
        candidates = {
            "regular": self.ttf_regular_candidates,
            "bold": self.ttf_bold_candidates,
            "italic": self.ttf_italic_candidates,
            "mono": self.ttf_mono_candidates,
        }.get(variant, self.ttf_regular_candidates)
        for path in candidates:
            if os.path.exists(path):
                return path
        return None


def _build_default_callout_themes(
    primary_hex: str,
    secondary_hex: str,
    fact_hex: str,
    fact_bg: str,
    inference_hex: str,
    inference_bg: str,
    hypothetical_hex: str,
    hypothetical_bg: str,
    limitation_hex: str,
    limitation_bg: str,
) -> Dict[str, CalloutBoxTheme]:
    return {
        CalloutBoxKind.CONCEPT_BOX.value: CalloutBoxTheme(
            kind=CalloutBoxKind.CONCEPT_BOX.value,
            badge_label="CONCEITO FUNDAMENTAL",
            border_hex=primary_hex,
            background_hex="#F4F7FB",
            title_hex=primary_hex,
            text_hex="#1E293B",
        ),
        CalloutBoxKind.MECHANISM_BOX.value: CalloutBoxTheme(
            kind=CalloutBoxKind.MECHANISM_BOX.value,
            badge_label="MECANISMO & PROCESSO PASSO A PASSO",
            border_hex=secondary_hex,
            background_hex="#F1F5F9",
            title_hex=secondary_hex,
            text_hex="#1E293B",
        ),
        CalloutBoxKind.ATTENTION_BOX.value: CalloutBoxTheme(
            kind=CalloutBoxKind.ATTENTION_BOX.value,
            badge_label="NOTA DE RIGOR & DISTINÇÃO EPISTÉMICA",
            border_hex=inference_hex,
            background_hex=inference_bg,
            title_hex="#92400E",
            text_hex="#292524",
        ),
        CalloutBoxKind.HYPOTHETICAL_EXAMPLE_BOX.value: CalloutBoxTheme(
            kind=CalloutBoxKind.HYPOTHETICAL_EXAMPLE_BOX.value,
            badge_label="EXEMPLO ILUSTRATIVO HIPOTÉTICO (ELABORAÇÃO PEDAGÓGICA — NÃO É EVIDÊNCIA DA FONTE)",
            border_hex=hypothetical_hex,
            background_hex=hypothetical_bg,
            title_hex=hypothetical_hex,
            text_hex="#1E1B4B",
        ),
        CalloutBoxKind.LIMITATION_BOX.value: CalloutBoxTheme(
            kind=CalloutBoxKind.LIMITATION_BOX.value,
            badge_label="LIMITAÇÕES METODOLÓGICAS & FRONTEIRAS DE VALIDADE",
            border_hex=limitation_hex,
            background_hex=limitation_bg,
            title_hex=limitation_hex,
            text_hex="#3F1D24",
        ),
        CalloutBoxKind.SYNTHESIS_BOX.value: CalloutBoxTheme(
            kind=CalloutBoxKind.SYNTHESIS_BOX.value,
            badge_label="SÍNTESE PEDAGÓGICA & CONSOLIDAÇÃO (MODEL_INFERENCE)",
            border_hex=inference_hex,
            background_hex=inference_bg,
            title_hex=inference_hex,
            text_hex="#292524",
        ),
        CalloutBoxKind.METHODOLOGY_NOTE_BOX.value: CalloutBoxTheme(
            kind=CalloutBoxKind.METHODOLOGY_NOTE_BOX.value,
            badge_label="NOTA METODOLÓGICA & DESENHO EXPERIMENTAL",
            border_hex=secondary_hex,
            background_hex="#F1F5F9",
            title_hex=secondary_hex,
            text_hex="#1E293B",
        ),
    }


ACADEMIC_EDITORIAL_CLASSIC = DesignStyleProfile(
    profile_id="ACADEMIC_EDITORIAL_CLASSIC",
    display_name="Clássico Editorial Universitário",
    description=(
        "Identidade académica inspirada em manuais universitários e monografias científicas, "
        "com hierarquia tipográfica clara, tabelas académicas de três linhas e distinção epistémica rigorosa."
    ),
    docx_font_body="Calibri",
    docx_font_headings="Calibri",
    docx_font_mono="Consolas",
    ttf_regular_candidates=(
        "C:/Windows/Fonts/trebuc.ttf",
        "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/calibri.ttf",
        "C:/Windows/Fonts/segoeui.ttf",
    ),
    ttf_bold_candidates=(
        "C:/Windows/Fonts/trebucbd.ttf",
        "C:/Windows/Fonts/arialbd.ttf",
        "C:/Windows/Fonts/calibrib.ttf",
        "C:/Windows/Fonts/segoeuib.ttf",
    ),
    ttf_italic_candidates=(
        "C:/Windows/Fonts/trebucit.ttf",
        "C:/Windows/Fonts/ariali.ttf",
        "C:/Windows/Fonts/calibrii.ttf",
        "C:/Windows/Fonts/segoeuii.ttf",
    ),
    ttf_mono_candidates=(
        "C:/Windows/Fonts/consola.ttf",
        "C:/Windows/Fonts/cour.ttf",
    ),
    primary_hex="#16324F",
    secondary_hex="#2A4D69",
    accent_hex="#1D5B79",
    text_primary_hex="#1A202C",
    text_muted_hex="#4A5568",
    surface_light_hex="#F8FAFC",
    surface_zebra_hex="#F3F6FA",
    border_subtle_hex="#CBD5E1",
    fact_accent_hex="#0F766E",
    fact_bg_hex="#F0FDFA",
    inference_accent_hex="#B45309",
    inference_bg_hex="#FFFBEB",
    hypothetical_accent_hex="#4338CA",
    hypothetical_bg_hex="#EEF2FF",
    limitation_accent_hex="#9F1239",
    limitation_bg_hex="#FFF1F2",
    callout_themes=_build_default_callout_themes(
        primary_hex="#16324F",
        secondary_hex="#2A4D69",
        fact_hex="#0F766E",
        fact_bg="#F0FDFA",
        inference_hex="#B45309",
        inference_bg="#FFFBEB",
        hypothetical_hex="#4338CA",
        hypothetical_bg="#EEF2FF",
        limitation_hex="#9F1239",
        limitation_bg="#FFF1F2",
    ),
)


TECHNICAL_SCIENTIFIC_MODERN = DesignStyleProfile(
    profile_id="TECHNICAL_SCIENTIFIC_MODERN",
    display_name="Científico & Técnico Contemporâneo",
    description=(
        "Estilo editorial técnico de elevada densidade informativa para relatórios de engenharia, "
        "arquitetura de sistemas e artigos de ciência de computadores."
    ),
    docx_font_body="Segoe UI",
    docx_font_headings="Segoe UI",
    docx_font_mono="Consolas",
    ttf_regular_candidates=(
        "C:/Windows/Fonts/trebuc.ttf",
        "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/calibri.ttf",
        "C:/Windows/Fonts/segoeui.ttf",
    ),
    ttf_bold_candidates=(
        "C:/Windows/Fonts/trebucbd.ttf",
        "C:/Windows/Fonts/arialbd.ttf",
        "C:/Windows/Fonts/calibrib.ttf",
        "C:/Windows/Fonts/segoeuib.ttf",
    ),
    ttf_italic_candidates=(
        "C:/Windows/Fonts/trebucit.ttf",
        "C:/Windows/Fonts/ariali.ttf",
        "C:/Windows/Fonts/calibrii.ttf",
        "C:/Windows/Fonts/segoeuii.ttf",
    ),
    ttf_mono_candidates=(
        "C:/Windows/Fonts/consola.ttf",
    ),
    primary_hex="#0F2942",
    secondary_hex="#1E4E79",
    accent_hex="#0284C7",
    text_primary_hex="#111827",
    text_muted_hex="#4B5563",
    surface_light_hex="#F9FAFB",
    surface_zebra_hex="#F1F5F9",
    border_subtle_hex="#D1D5DB",
    fact_accent_hex="#047857",
    fact_bg_hex="#ECFDF5",
    inference_accent_hex="#B45309",
    inference_bg_hex="#FFFBEB",
    hypothetical_accent_hex="#4F46E5",
    hypothetical_bg_hex="#EEF2FF",
    limitation_accent_hex="#BE123C",
    limitation_bg_hex="#FFF1F2",
    callout_themes=_build_default_callout_themes(
        primary_hex="#0F2942",
        secondary_hex="#1E4E79",
        fact_hex="#047857",
        fact_bg="#ECFDF5",
        inference_hex="#B45309",
        inference_bg="#FFFBEB",
        hypothetical_hex="#4F46E5",
        hypothetical_bg="#EEF2FF",
        limitation_hex="#BE123C",
        limitation_bg="#FFF1F2",
    ),
)


DESIGN_PROFILES: Dict[str, DesignStyleProfile] = {
    ACADEMIC_EDITORIAL_CLASSIC.profile_id: ACADEMIC_EDITORIAL_CLASSIC,
    TECHNICAL_SCIENTIFIC_MODERN.profile_id: TECHNICAL_SCIENTIFIC_MODERN,
}


class AcademicDesignSystem:
    """Gestor do sistema de design documental da Fase 5."""

    @classmethod
    def get_profile(cls, profile_id: Optional[str] = None) -> DesignStyleProfile:
        if not profile_id:
            return ACADEMIC_EDITORIAL_CLASSIC
        key = str(profile_id).strip().upper()
        if key in DESIGN_PROFILES:
            return DESIGN_PROFILES[key]
        if "TECH" in key or "MODERN" in key or "SPEC" in key:
            return TECHNICAL_SCIENTIFIC_MODERN
        return ACADEMIC_EDITORIAL_CLASSIC

    @classmethod
    def sanitize_text_for_font(cls, text: str, font_obj: Optional[object] = None) -> str:
        """
        Normaliza caracteres tipográficos e substitui glifos não suportados pela fonte ativa,
        garantindo zero caracteres nulos (\\x00) ou símbolos ilegíveis (\\ufffd) no PDF final.
        """
        if not text:
            return ""
        cleaned = (
            str(text)
            .replace("\x00", "")
            .replace("\ufffd", "")
            .replace("\u00a0", " ")
            .replace("\u200b", "")
            .replace("\r\n", "\n")
            .replace("\r", "\n")
        )
        # Substituições seguras para símbolos matemáticos ou setas que possam faltar em fontes clássicas
        fallback_glyph_map = {
            "⟶": "->",
            "⟵": "<-",
            "⟷": "<->",
            "⇒": "=>",
            "⇐": "<=",
            "⇔": "<=>",
            "↦": "->",
            "↪": "->",
            "✓": "[OK]",
            "✔": "[OK]",
            "✗": "[X]",
            "✘": "[X]",
            "⚠": "[!]",
            "📌": "*",
            "🔹": "-",
            "▪": "-",
            "▸": ">",
            "➔": "->",
            "➜": "->",
        }
        for src_ch, repl in fallback_glyph_map.items():
            if src_ch in cleaned:
                cleaned = cleaned.replace(src_ch, repl)

        if font_obj is not None and hasattr(font_obj, "has_glyph"):
            out_chars = []
            for ch in cleaned:
                if ch in ("\n", "\t", " "):
                    out_chars.append(ch)
                    continue
                try:
                    if font_obj.has_glyph(ord(ch)):  # type: ignore[attr-defined]
                        out_chars.append(ch)
                    else:
                        # Fallback ASCII/Unicode seguro
                        secondary_map = {
                            "→": "->",
                            "←": "<-",
                            "↔": "<->",
                            "≤": "<=",
                            "≥": ">=",
                            "≠": "!=",
                            "≈": "~=",
                            "∑": "Sum",
                            "∏": "Prod",
                            "√": "sqrt",
                            "∞": "inf",
                            "α": "alpha",
                            "β": "beta",
                            "γ": "gamma",
                            "δ": "delta",
                            "ε": "epsilon",
                            "λ": "lambda",
                            "μ": "mu",
                            "σ": "sigma",
                            "τ": "tau",
                            "ω": "omega",
                            "Δ": "Delta",
                            "Ω": "Omega",
                        }
                        out_chars.append(secondary_map.get(ch, ""))
                except Exception:
                    out_chars.append(ch)
            cleaned = "".join(out_chars)
        return cleaned

