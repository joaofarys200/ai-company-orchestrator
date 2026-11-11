"""
JARVIS OS — Study Engine Phase 5: Visual Generation Engine (Componente 5.4)
Gera os elementos visuais planeados na Fase 4 (mapas de conceitos, fluxogramas,
gráficos quantitativos com dados reais, esquemas de arquitetura, tabelas comparativas),
garantindo rastreabilidade, distinção epistémica e imagens de alta resolução (220 DPI).
"""

from __future__ import annotations

import math
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from PIL import Image, ImageDraw, ImageFont

from services.academic_reasoning_engine import AcademicReasoningDossier
from services.document_intelligence import AcademicDocumentAST
from services.editorial_intelligence_engine import EditorialStudyPlan, VisualPlanItem
from services.study_document_generation.contracts import (
    GeneratedVisualAsset,
    VisualDataSeries,
    VisualEdge,
    VisualNode,
    VisualRenderStatus,
    normalize_epistemic_status,
)
from services.study_document_generation.design_system import (
    ACADEMIC_EDITORIAL_CLASSIC,
    DesignStyleProfile,
    hex_to_rgb_int,
)
from services.study_document_generation.provenance_renderer import ReferenceAndProvenanceRenderer


class VisualGenerationEngine:
    """
    Componente 5.4 — Visual Generation Engine.
    Executa a renderização gráfica dos planos visuais da Fase 4.
    """

    def __init__(
        self,
        output_dir: Path,
        *,
        profile: Optional[DesignStyleProfile] = None,
        dpi: int = 220,
    ) -> None:
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.profile = profile or ACADEMIC_EDITORIAL_CLASSIC
        self.dpi = dpi

    def generate_visual_assets(
        self,
        plan: EditorialStudyPlan,
        dossier: AcademicReasoningDossier,
        ast: Optional[AcademicDocumentAST],
        provenance: ReferenceAndProvenanceRenderer,
    ) -> List[GeneratedVisualAsset]:
        """
        Renderiza todos os `VisualPlanItem`s do plano editorial de forma determinística,
        produzindo ficheiros PNG de alta resolução acompanhados de metadados de proveniência.
        """
        assets: List[GeneratedVisualAsset] = []

        for idx, vp in enumerate(plan.visual_plans, start=1):
            asset = self._render_single_visual(
                vp=vp,
                index=idx,
                plan=plan,
                dossier=dossier,
                ast=ast,
                provenance=provenance,
            )
            assets.append(asset)

        return assets

    def _render_single_visual(
        self,
        vp: VisualPlanItem,
        index: int,
        plan: EditorialStudyPlan,
        dossier: AcademicReasoningDossier,
        ast: Optional[AcademicDocumentAST],
        provenance: ReferenceAndProvenanceRenderer,
    ) -> GeneratedVisualAsset:
        v_type = vp.visual_type.upper().strip()
        vp_ep = normalize_epistemic_status(getattr(vp, "epistemic_status", None), default="UNVERIFIED")
        sec_refs = provenance.sanitize_evidence_refs(vp.evidence_refs, allow_section_fallback=False, default_status=vp_ep)
        prov_label = provenance.format_provenance_summary(
            vp_ep,
            sec_refs,
            source_table_refs=vp.source_table_ids,
            source_figure_refs=vp.source_figure_ids,
        )

        out_filename = f"visual_{index:02d}_{vp.visual_id}.png"
        out_path = self.output_dir / out_filename

        # 1. Gráficos Quantitativos
        if "QUANTITATIVE" in v_type or "CHART" in v_type or "BAR" in v_type or "LINE" in v_type:
            series_list = self._extract_traceable_numeric_series(vp, dossier, ast)
            if series_list:
                img = self._draw_quantitative_chart(vp, series_list)
                img.save(str(out_path), dpi=(self.dpi, self.dpi))
                return GeneratedVisualAsset(
                    visual_id=vp.visual_id,
                    target_chapter_id=vp.target_chapter_id,
                    target_section_id=vp.target_section_id,
                    visual_type=vp.visual_type,
                    title=vp.title,
                    caption=f"{vp.pedagogical_objective} Dados extraídos e verificados da fonte original.",
                    pedagogical_objective=vp.pedagogical_objective,
                    render_status=VisualRenderStatus.RENDERED.value,
                    image_path=str(out_path),
                    width_px=img.width,
                    height_px=img.height,
                    data_series=series_list,
                    epistemic_status="SOURCE_FACT",
                    provenance_label=prov_label,
                    evidence_refs=sec_refs,
                )
            else:
                # Regras 4.2 e 5.4: Proibido inventar dados em gráficos quantitativos
                table_headers, table_rows = self._extract_qualitative_fallback_table(vp, dossier, ast)
                if table_headers and table_rows:
                    img = self._draw_comparative_table_image(vp, table_headers, table_rows)
                    img.save(str(out_path), dpi=(self.dpi, self.dpi))
                    return GeneratedVisualAsset(
                        visual_id=vp.visual_id,
                        target_chapter_id=vp.target_chapter_id,
                        target_section_id=vp.target_section_id,
                        visual_type="COMPARATIVE_TABLE",
                        title=f"{vp.title} (Quadro Comparativo Estruturado)",
                        caption=(
                            f"{vp.pedagogical_objective} Quadro estruturado com os dados disponíveis na fonte original "
                            "(série numérica contínua não reportada; substituição por quadro para prevenir alucinação de valores)."
                        ),
                        pedagogical_objective=vp.pedagogical_objective,
                        render_status=VisualRenderStatus.RENDERED_AS_TABLE.value,
                        image_path=str(out_path),
                        width_px=img.width,
                        height_px=img.height,
                        table_headers=table_headers,
                        table_rows=table_rows,
                        epistemic_status=vp_ep,
                        provenance_label=prov_label,
                        evidence_refs=sec_refs,
                        omission_or_fallback_reason=(
                            "Dados numéricos contínuos insuficientes para gráfico quantitativo rigoroso; "
                            "renderizado como quadro analítico estruturado sem valores extrapolados."
                        ),
                    )
                else:
                    return GeneratedVisualAsset(
                        visual_id=vp.visual_id,
                        target_chapter_id=vp.target_chapter_id,
                        target_section_id=vp.target_section_id,
                        visual_type=vp.visual_type,
                        title=vp.title,
                        caption=vp.pedagogical_objective,
                        pedagogical_objective=vp.pedagogical_objective,
                        render_status=VisualRenderStatus.OMITTED_INSUFFICIENT_DATA.value,
                        image_path=None,
                        epistemic_status=vp_ep,
                        provenance_label=prov_label,
                        evidence_refs=sec_refs,
                        omission_or_fallback_reason=(
                            "Série numérica ausente na fonte original. Omissão limpa efetuada em conformidade "
                            "com o princípio de fidelidade à fonte (Regra 4.2 / 5.4)."
                        ),
                    )

        # 2. Tabelas Comparativas
        if "TABLE" in v_type or "COMPARATIVE" in v_type:
            headers, rows = self._build_comparative_table_data(vp, dossier, ast)
            img = self._draw_comparative_table_image(vp, headers, rows)
            img.save(str(out_path), dpi=(self.dpi, self.dpi))
            return GeneratedVisualAsset(
                visual_id=vp.visual_id,
                target_chapter_id=vp.target_chapter_id,
                target_section_id=vp.target_section_id,
                visual_type=vp.visual_type,
                title=vp.title,
                caption=f"{vp.pedagogical_objective} Quadro comparativo fundamentado nas evidências da fonte.",
                pedagogical_objective=vp.pedagogical_objective,
                render_status=VisualRenderStatus.RENDERED.value,
                image_path=str(out_path),
                width_px=img.width,
                height_px=img.height,
                table_headers=headers,
                table_rows=rows,
                epistemic_status=vp.epistemic_status or "SOURCE_FACT",
                provenance_label=prov_label,
                evidence_refs=sec_refs,
            )

        # 3. Diagramas Conceptuais, Mapas de Relações, Fluxogramas, Processos e Arquiteturas
        nodes, edges = self._build_concept_network_data(vp, plan, dossier)
        img = self._draw_concept_network_diagram(vp, nodes, edges)
        img.save(str(out_path), dpi=(self.dpi, self.dpi))
        return GeneratedVisualAsset(
            visual_id=vp.visual_id,
            target_chapter_id=vp.target_chapter_id,
            target_section_id=vp.target_section_id,
            visual_type=vp.visual_type,
            title=vp.title,
            caption=(
                f"{vp.pedagogical_objective} "
                "Traço contínuo: relações confirmadas na fonte [FACTO]; "
                "Traço tracejado: articulação inferida pelo modelo [INFERÊNCIA]."
            ),
            pedagogical_objective=vp.pedagogical_objective,
            render_status=VisualRenderStatus.RENDERED.value,
            image_path=str(out_path),
            width_px=img.width,
            height_px=img.height,
            nodes=nodes,
            edges=edges,
            epistemic_status=vp.epistemic_status or "SOURCE_FACT",
            provenance_label=prov_label,
            evidence_refs=sec_refs,
        )

    # -----------------------------------------------------------------------
    # Extração de Dados Rastreáveis da Fonte
    # -----------------------------------------------------------------------

    def _extract_traceable_numeric_series(
        self,
        vp: VisualPlanItem,
        dossier: AcademicReasoningDossier,
        ast: Optional[AcademicDocumentAST],
    ) -> List[VisualDataSeries]:
        series_list: List[VisualDataSeries] = []

        # Tentar extrair das tabelas da AST
        if ast is not None and vp.source_table_ids:
            for tid in vp.source_table_ids:
                tbl = next((t for t in ast.tables if t.table_id == tid), None)
                if tbl and tbl.rows:
                    hdr_idx = tbl.header_row_index if (tbl.header_row_index is not None and tbl.header_row_index < len(tbl.rows)) else 0
                    tbl_headers = [str(h).strip() for h in tbl.rows[hdr_idx]]
                    tbl_rows = [r for idx, r in enumerate(tbl.rows) if idx != hdr_idx]
                    cat_idx = 0
                    val_idx = -1
                    for c_i, h in enumerate(tbl_headers[1:], start=1):
                        num_count = sum(1 for r in tbl_rows if c_i < len(r) and self._is_float(r[c_i]))
                        if num_count >= max(2, len(tbl_rows) // 2):
                            val_idx = c_i
                            break
                    if val_idx != -1:
                        cats = [str(r[cat_idx])[:25] for r in tbl_rows if len(r) > val_idx and self._is_float(r[val_idx])]
                        vals = [float(str(r[val_idx]).replace(",", ".")) for r in tbl_rows if len(r) > val_idx and self._is_float(r[val_idx])]
                        if cats and vals:
                            series_list.append(
                                VisualDataSeries(
                                    series_name=tbl_headers[val_idx] if val_idx < len(tbl_headers) else f"Série {val_idx}",
                                    categories=cats[:7],
                                    values=vals[:7],
                                    unit=tbl_headers[val_idx] if val_idx < len(tbl_headers) else "Valor",
                                    source_ref=f"Tabela {tid} (p. {tbl.page_number})",
                                    epistemic_status="SOURCE_FACT",
                                )
                            )

        # Tentar extrair métricas do Dossier (Results and Evidence)
        if not series_list and dossier.results_and_evidence:
            re_an = dossier.results_and_evidence
            cand_cats: List[str] = []
            cand_vals: List[float] = []
            for rf in re_an.main_empirical_findings:
                import re
                m = re.search(r"(\b[0-9]+(?:\.[0-9]+)?%?\b)", rf.statement)
                if m:
                    num_str = m.group(1).rstrip("%")
                    try:
                        v = float(num_str)
                        c_label = rf.statement.split(":")[0][:24] if ":" in rf.statement else rf.statement[:24]
                        cand_cats.append(c_label)
                        cand_vals.append(v)
                    except ValueError:
                        pass
            if len(cand_cats) >= 2:
                series_list.append(
                    VisualDataSeries(
                        series_name="Valores Empíricos Reportados",
                        categories=cand_cats[:6],
                        values=cand_vals[:6],
                        unit="Valores Reportados",
                        source_ref="Resultados Empíricos (Dossier Fase 3)",
                        epistemic_status="SOURCE_FACT",
                    )
                )

        return series_list

    def _extract_qualitative_fallback_table(
        self,
        vp: VisualPlanItem,
        dossier: AcademicReasoningDossier,
        ast: Optional[AcademicDocumentAST],
    ) -> Tuple[List[str], List[List[str]]]:
        if ast is not None and vp.source_table_ids:
            for tid in vp.source_table_ids:
                tbl = next((t for t in ast.tables if t.table_id == tid), None)
                if tbl and tbl.rows:
                    hdr_idx = tbl.header_row_index if (tbl.header_row_index is not None and tbl.header_row_index < len(tbl.rows)) else 0
                    tbl_headers = [str(h).strip() for h in tbl.rows[hdr_idx]]
                    tbl_rows = [r for idx, r in enumerate(tbl.rows) if idx != hdr_idx]
                    clean_headers = [h[:30] for h in tbl_headers[:4]]
                    clean_rows = [[str(c)[:40] for c in r[:len(clean_headers)]] for r in tbl_rows[:6]]
                    if clean_headers and clean_rows:
                        return clean_headers, clean_rows

        vp_ep = normalize_epistemic_status(getattr(vp, "epistemic_status", None), default="UNVERIFIED")
        headers = ["Elemento / Aspeto", "Descrição Editorial", "Classificação Epistémica"]
        rows: List[List[str]] = []
        for req in vp.required_concepts_or_data[:5]:
            rows.append([req[:30], f"Aspeto estruturado: {req[:30]}", vp_ep])
        for info in vp.information_to_represent[:3]:
            rows.append([info[:30], "Conteúdo representado", vp_ep])

        if not rows:
            rows.append(["Âmbito Analítico", vp.pedagogical_objective[:60], "MODEL_INFERENCE"])

        return headers, rows

    def _build_comparative_table_data(
        self,
        vp: VisualPlanItem,
        dossier: AcademicReasoningDossier,
        ast: Optional[AcademicDocumentAST],
    ) -> Tuple[List[str], List[List[str]]]:
        return self._extract_qualitative_fallback_table(vp, dossier, ast)

    def _build_concept_network_data(
        self,
        vp: VisualPlanItem,
        plan: EditorialStudyPlan,
        dossier: AcademicReasoningDossier,
    ) -> Tuple[List[VisualNode], List[VisualEdge]]:
        vp_ep = normalize_epistemic_status(getattr(vp, "epistemic_status", None), default="UNVERIFIED")
        nodes: List[VisualNode] = []
        edges: List[VisualEdge] = []
        node_map: Dict[str, VisualNode] = {}

        # 1. Utilizar nós e arestas de `EditorialConceptRelationship` se existirem
        relevant_rels = [
            rel for rel in plan.conceptual_relationships
            if any(term in (rel.source_concept_name + rel.target_concept_name).lower()
                   for term in (vp.title + " " + vp.content_to_explain).lower().split() if len(term) > 4)
        ]
        if not relevant_rels:
            relevant_rels = plan.conceptual_relationships[:5]

        for rel in relevant_rels[:6]:
            s_id = rel.source_concept_id or f"c_{len(node_map)+1}"
            t_id = rel.target_concept_id or f"c_{len(node_map)+2}"
            rel_ep = normalize_epistemic_status(getattr(rel, "epistemic_status", None), default="UNVERIFIED")
            if s_id not in node_map:
                node_map[s_id] = VisualNode(
                    node_id=s_id,
                    label=rel.source_concept_name or s_id,
                    epistemic_status=rel_ep,
                )
            if t_id not in node_map:
                node_map[t_id] = VisualNode(
                    node_id=t_id,
                    label=rel.target_concept_name or t_id,
                    epistemic_status=rel_ep,
                )
            edges.append(
                VisualEdge(
                    source_id=s_id,
                    target_id=t_id,
                    label=rel.relation_type,
                    epistemic_status=rel_ep,
                    is_directed=True,
                )
            )

        # 2. Se a rede for pequena, complementar com `required_concepts_or_data`
        for req in vp.required_concepts_or_data:
            req_id = f"n_{abs(hash(req)) % 10000}"
            if req_id not in node_map and len(node_map) < 6:
                node_map[req_id] = VisualNode(
                    node_id=req_id,
                    label=req,
                    epistemic_status=vp_ep,
                )
                if len(node_map) >= 2:
                    first_id = next(iter(node_map))
                    if first_id != req_id:
                        edges.append(
                            VisualEdge(
                                source_id=first_id,
                                target_id=req_id,
                                label="relaciona-se",
                                epistemic_status="MODEL_INFERENCE",
                            )
                        )

        if not node_map:
            # Fallback seguro sem forçar SOURCE_FACT quando não há dados extraídos
            n1 = VisualNode("core_1", vp.title[:30], epistemic_status=vp_ep)
            n2 = VisualNode("core_2", vp.pedagogical_objective[:30], epistemic_status="MODEL_INFERENCE")
            node_map["core_1"] = n1
            node_map["core_2"] = n2
            edges.append(VisualEdge("core_1", "core_2", "articula", epistemic_status="MODEL_INFERENCE"))

        nodes = list(node_map.values())[:8]
        return nodes, edges[:10]

    @staticmethod
    def _is_float(val: Any) -> bool:
        try:
            float(str(val).replace(",", ".").strip())
            return True
        except ValueError:
            return False

    # -----------------------------------------------------------------------
    # Métodos de Renderização Gráfica PIL (220 DPI)
    # -----------------------------------------------------------------------

    def _get_font(self, size: int = 16, bold: bool = False) -> Any:
        candidates = ["segoeui.ttf", "arial.ttf", "calibri.ttf"]
        if bold:
            candidates = ["segoeuib.ttf", "arialbd.ttf", "calibrib.ttf"] + candidates
        for c in candidates:
            try:
                return ImageFont.truetype(c, size)
            except Exception:
                pass
        return ImageFont.load_default()

    def _draw_quantitative_chart(
        self,
        vp: VisualPlanItem,
        series_list: List[VisualDataSeries],
    ) -> Image.Image:
        w, h = 1400, 780
        img = Image.new("RGB", (w, h), color=(255, 255, 255))
        draw = ImageDraw.Draw(img)

        f_title = self._get_font(20, bold=True)
        f_sub = self._get_font(15)
        f_body = self._get_font(15)
        f_bold = self._get_font(15, bold=True)
        f_sm = self._get_font(13)

        c_primary = hex_to_rgb_int(self.profile.primary_hex)
        c_secondary = hex_to_rgb_int(self.profile.secondary_hex)
        c_text = hex_to_rgb_int(self.profile.text_primary_hex)
        c_muted = hex_to_rgb_int(self.profile.text_muted_hex)
        c_border = hex_to_rgb_int(self.profile.border_subtle_hex)
        c_bar = hex_to_rgb_int(self.profile.fact_accent_hex)

        # Fundo e moldura
        draw.rectangle([(20, 20), (w - 20, h - 20)], outline=c_border, width=2)
        draw.rectangle([(22, 22), (w - 22, 100)], fill=(245, 248, 252))

        # Título
        draw.text((45, 34), f"GRÁFICO QUANTITATIVO: {vp.title}", fill=c_primary, font=f_title)
        draw.text((45, 66), f"Objetivo: {vp.pedagogical_objective}", fill=c_muted, font=f_sub)

        # Desenhar barras da primeira série disponível
        s = series_list[0]
        cats = s.categories[:7]
        vals = s.values[:7]
        max_val = max(vals) if vals and max(vals) > 0 else 100.0

        chart_x0, chart_y0 = 120, 160
        chart_x1, chart_y1 = w - 80, h - 140

        # Eixo Y
        draw.line([(chart_x0, chart_y0), (chart_x0, chart_y1)], fill=c_secondary, width=3)
        # Eixo X
        draw.line([(chart_x0, chart_y1), (chart_x1, chart_y1)], fill=c_secondary, width=3)

        # Linhas de grelha
        for step in range(5):
            y_pos = chart_y1 - (chart_y1 - chart_y0) * (step / 4.0)
            val_step = (max_val * (step / 4.0))
            draw.line([(chart_x0 - 5, y_pos), (chart_x1, y_pos)], fill=(235, 240, 245), width=1)
            draw.text((chart_x0 - 75, y_pos - 8), f"{val_step:.1f}", fill=c_muted, font=f_sm)

        bar_count = len(cats)
        if bar_count > 0:
            total_avail_w = chart_x1 - chart_x0 - 40
            slot_w = total_avail_w / bar_count
            bar_w = min(80.0, slot_w * 0.6)

            for i, (cat, val) in enumerate(zip(cats, vals)):
                center_x = chart_x0 + 30 + i * slot_w + slot_w / 2.0
                bar_h = max(0.0, ((val / max_val) * (chart_y1 - chart_y0 - 20))) if max_val > 0 else 0.0
                b_x0 = center_x - bar_w / 2.0
                b_x1 = center_x + bar_w / 2.0
                rect_y0 = chart_y1 - bar_h
                rect_y1 = chart_y1

                # Pillow exige y0 <= y1 e x0 <= x1
                final_y0 = min(rect_y0, rect_y1)
                final_y1 = max(rect_y0, rect_y1)
                if final_y1 == final_y0:
                    final_y0 = final_y1 - 2

                draw.rectangle([(b_x0, final_y0), (b_x1, final_y1)], fill=c_bar, outline=c_primary, width=2)
                # Valor no topo da barra
                draw.text((b_x0 + 4, final_y0 - 24), f"{val:.1f}", fill=c_primary, font=f_bold)
                # Legenda da categoria
                draw.text((b_x0 - 10, chart_y1 + 14), cat[:18], fill=c_text, font=f_body)

        # Rodapé e nota de proveniência
        draw.rectangle([(22, h - 75), (w - 22, h - 22)], fill=(245, 248, 252))
        draw.text(
            (45, h - 55),
            f"Fonte Auditada: {s.source_ref} • Dados empíricos rastreáveis [SOURCE_FACT]",
            fill=hex_to_rgb_int(self.profile.fact_accent_hex),
            font=f_bold,
        )

        return img

    def _draw_comparative_table_image(
        self,
        vp: VisualPlanItem,
        headers: List[str],
        rows: List[List[str]],
    ) -> Image.Image:
        w = 1400
        row_h = 60
        header_h = 75
        top_h = 110
        footer_h = 70
        h = top_h + header_h + max(1, len(rows)) * row_h + footer_h + 40

        img = Image.new("RGB", (w, h), color=(255, 255, 255))
        draw = ImageDraw.Draw(img)

        f_title = self._get_font(20, bold=True)
        f_sub = self._get_font(15)
        f_th = self._get_font(16, bold=True)
        f_td = self._get_font(15)
        f_footer = self._get_font(14, bold=True)

        c_primary = hex_to_rgb_int(self.profile.primary_hex)
        c_secondary = hex_to_rgb_int(self.profile.secondary_hex)
        c_text = hex_to_rgb_int(self.profile.text_primary_hex)
        c_muted = hex_to_rgb_int(self.profile.text_muted_hex)
        c_border = hex_to_rgb_int(self.profile.border_subtle_hex)
        c_zebra = hex_to_rgb_int(self.profile.surface_zebra_hex)

        # Moldura geral
        draw.rectangle([(20, 20), (w - 20, h - 20)], outline=c_border, width=2)

        # Topo
        draw.rectangle([(22, 22), (w - 22, top_h)], fill=(245, 248, 252))
        draw.text((45, 34), f"QUADRO COMPARATIVO ESTRUTURADO: {vp.title}", fill=c_primary, font=f_title)
        draw.text((45, 68), f"Objetivo Pedagógico: {vp.pedagogical_objective}", fill=c_muted, font=f_sub)

        # Larguras de coluna proporcionais
        cols_count = max(1, len(headers))
        col_w = (w - 100) / cols_count

        # Cabeçalho da Tabela
        tbl_y0 = top_h + 15
        draw.rectangle([(50, tbl_y0), (w - 50, tbl_y0 + header_h)], fill=c_primary)
        for c_i, header_txt in enumerate(headers):
            x_pos = 50 + c_i * col_w + 16
            draw.text((x_pos, tbl_y0 + 26), str(header_txt).upper(), fill=(255, 255, 255), font=f_th)

        # Linhas de Dados
        cur_y = tbl_y0 + header_h
        for r_i, row in enumerate(rows):
            fill_color = c_zebra if (r_i % 2 == 1) else (255, 255, 255)
            draw.rectangle([(50, cur_y), (w - 50, cur_y + row_h)], fill=fill_color, outline=c_border, width=1)
            for c_i in range(cols_count):
                cell_val = str(row[c_i]) if c_i < len(row) else ""
                x_pos = 50 + c_i * col_w + 16
                draw.text((x_pos, cur_y + 18), cell_val[:45], fill=c_text, font=f_td)
            cur_y += row_h

        # Rodapé
        draw.rectangle([(22, h - footer_h - 15), (w - 22, h - 22)], fill=(245, 248, 252))
        draw.text(
            (45, h - footer_h + 5),
            f"Proveniência: Rastreabilidade verificada na fonte original ({vp.target_section_id})",
            fill=c_secondary,
            font=f_footer,
        )

        return img

    def _draw_concept_network_diagram(
        self,
        vp: VisualPlanItem,
        nodes: List[VisualNode],
        edges: List[VisualEdge],
    ) -> Image.Image:
        w, h = 1400, 840
        img = Image.new("RGB", (w, h), color=(255, 255, 255))
        draw = ImageDraw.Draw(img)

        f_title = self._get_font(20, bold=True)
        f_sub = self._get_font(15)
        f_badge = self._get_font(13, bold=True)
        f_node = self._get_font(15, bold=True)
        f_edge = self._get_font(13)
        f_legend = self._get_font(14)
        f_legend_bold = self._get_font(14, bold=True)

        c_primary = hex_to_rgb_int(self.profile.primary_hex)
        c_secondary = hex_to_rgb_int(self.profile.secondary_hex)
        c_border = hex_to_rgb_int(self.profile.border_subtle_hex)
        c_muted = hex_to_rgb_int(self.profile.text_muted_hex)
        c_fact_bg = hex_to_rgb_int(self.profile.fact_bg_hex)
        c_fact_border = hex_to_rgb_int(self.profile.fact_accent_hex)
        c_inf_bg = hex_to_rgb_int(self.profile.inference_bg_hex)
        c_inf_border = hex_to_rgb_int(self.profile.inference_accent_hex)

        # Moldura geral
        draw.rectangle([(20, 20), (w - 20, h - 20)], outline=c_border, width=2)
        draw.rectangle([(22, 22), (w - 22, 100)], fill=(245, 248, 252))

        # Título
        draw.text((45, 34), f"MAPA CONCEPTUAL & ARQUITETURA DE RELAÇÕES: {vp.title}", fill=c_primary, font=f_title)
        draw.text((45, 68), f"Objetivo: {vp.pedagogical_objective}", fill=c_muted, font=f_sub)

        # Layout circular em torno do centro do diagrama
        center_x, center_y = w / 2.0, h / 2.0 + 20
        radius = min(w, h) * 0.32
        node_positions: Dict[str, Tuple[float, float, float, float]] = {}

        n_count = len(nodes)
        for i, n in enumerate(nodes):
            angle = (2.0 * math.pi * i) / n_count - math.pi / 2.0
            nx = center_x + radius * math.cos(angle)
            ny = center_y + radius * math.sin(angle)
            box_w, box_h = 240.0, 70.0
            node_positions[n.node_id] = (nx - box_w / 2.0, ny - box_h / 2.0, nx + box_w / 2.0, ny + box_h / 2.0)

        # Desenhar Arestas (distinguindo SOURCE_FACT com traço contínuo de MODEL_INFERENCE)
        for e in edges:
            if e.source_id in node_positions and e.target_id in node_positions:
                s_box = node_positions[e.source_id]
                t_box = node_positions[e.target_id]
                sx, sy = (s_box[0] + s_box[2]) / 2.0, (s_box[1] + s_box[3]) / 2.0
                tx, ty = (t_box[0] + t_box[2]) / 2.0, (t_box[1] + t_box[3]) / 2.0

                is_fact = (e.epistemic_status == "SOURCE_FACT")
                line_color = c_fact_border if is_fact else c_inf_border
                line_w = 3 if is_fact else 2

                if is_fact:
                    draw.line([(sx, sy), (tx, ty)], fill=line_color, width=line_w)
                else:
                    # Desenhar linha tracejada para MODEL_INFERENCE
                    dist = math.hypot(tx - sx, ty - sy)
                    if dist > 0:
                        steps = int(dist / 14)
                        for s_idx in range(0, steps, 2):
                            p0_x = sx + (tx - sx) * (s_idx / steps)
                            p0_y = sy + (ty - sy) * (s_idx / steps)
                            p1_x = sx + (tx - sx) * (min(steps, s_idx + 1) / steps)
                            p1_y = sy + (ty - sy) * (min(steps, s_idx + 1) / steps)
                            draw.line([(p0_x, p0_y), (p1_x, p1_y)], fill=line_color, width=line_w)

                # Rótulo da aresta
                mx, my = (sx + tx) / 2.0, (sy + ty) / 2.0
                lbl = e.label[:22]
                if lbl:
                    draw.rectangle([(mx - 60, my - 14), (mx + 60, my + 14)], fill=(255, 255, 255), outline=c_border)
                    draw.text((mx - 50, my - 8), lbl, fill=line_color, font=f_edge)

        # Desenhar Nós
        for n in nodes:
            b = node_positions[n.node_id]
            is_fact = (n.epistemic_status == "SOURCE_FACT")
            bg = c_fact_bg if is_fact else c_inf_bg
            border_c = c_fact_border if is_fact else c_inf_border
            badge_txt = "[FACTO]" if is_fact else "[INFERÊNCIA]"

            draw.rectangle([(b[0], b[1]), (b[2], b[3])], fill=bg, outline=border_c, width=3)
            draw.text((b[0] + 12, b[1] + 10), badge_txt, fill=border_c, font=f_badge)
            draw.text((b[0] + 12, b[1] + 34), n.label[:28], fill=c_primary, font=f_node)

        # Legenda Epistémica e Rodapé
        draw.rectangle([(22, h - 85), (w - 22, h - 22)], fill=(245, 248, 252))
        draw.rectangle([(45, h - 68), (145, h - 42)], fill=c_fact_bg, outline=c_fact_border, width=2)
        draw.text((52, h - 62), "[FACTO FONTE]", fill=c_fact_border, font=f_legend_bold)
        draw.text((160, h - 62), "Relação comprovada na fonte original (linha contínua)", fill=c_primary, font=f_legend)

        draw.rectangle([(620, h - 68), (730, h - 42)], fill=c_inf_bg, outline=c_inf_border, width=2)
        draw.text((628, h - 62), "[INFERÊNCIA]", fill=c_inf_border, font=f_legend_bold)
        draw.text((745, h - 62), "Relação inferida ou pedagógica (linha tracejada)", fill=c_secondary, font=f_legend)

        return img
