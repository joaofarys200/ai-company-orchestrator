"""
JARVIS OS — Study Engine Phase 7: Grounded Academic Explainer
Produz explicações académicas, esclarecimentos de passagens e comparações
conceptuais usando exclusivamente artefactos reais (Fases 2–4) e inferência
local via Ollama (qwen3.5:9b), preservando classificação epistémica estrita.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
from typing import Any, Callable, Dict, List, Optional, Tuple

from services.study_integration.context_manager import normalize_match_text


VALID_EPISTEMIC = ("SOURCE_FACT", "MODEL_INFERENCE", "NOT_FOUND", "UNVERIFIED")
EPISTEMIC_LABELS_PT = {
    "SOURCE_FACT": "Facto da Fonte (SOURCE_FACT)",
    "MODEL_INFERENCE": "Inferência do Modelo (MODEL_INFERENCE)",
    "NOT_FOUND": "Não Encontrado na Fonte (NOT_FOUND)",
    "UNVERIFIED": "Não Verificado (UNVERIFIED)",
}


class OllamaUnavailableError(RuntimeError):
    """Lançado quando a inferência local Ollama (qwen3.5:9b) não está disponível."""


class StudyAcademicExplainer:
    """Sintetiza explicações e comparações fundamentadas no documento alvo."""

    def __init__(
        self,
        *,
        model_service: Any = None,
        llm_caller: Optional[Callable[..., Any]] = None,
    ) -> None:
        self.model_service = model_service
        self.llm_caller = llm_caller

    async def explain(
        self,
        study_service: Any,
        *,
        document_id: str,
        question: str,
        chapter_id: Optional[str] = None,
        section_id: Optional[str] = None,
        topic: Optional[str] = None,
        recent_concepts: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        doc = study_service.get_document(document_id)
        if not doc:
            raise ValueError(f"Documento '{document_id}' não encontrado.")

        evidence_bundle = self._gather_document_evidence(
            study_service,
            doc=doc,
            query=question,
            chapter_id=chapter_id,
            section_id=section_id,
            topic=topic or "",
            recent_concepts=recent_concepts or [],
        )

        if not evidence_bundle["passages"] and not evidence_bundle["concepts"]:
            return {
                "summary_markdown": (
                    f"Não encontrei evidência suficiente em **{doc.title}** para responder com rigor a essa questão.\n\n"
                    f"- Classificação: **NOT_FOUND**"
                ),
                "citations": [],
                "epistemic_breakdown": {
                    "primary_status": "NOT_FOUND",
                    "claims": [
                        {
                            "statement": "O documento não apresenta informação verificável para o pedido.",
                            "epistemic_status": "NOT_FOUND",
                            "citations": [],
                        }
                    ],
                },
                "concepts_used": [],
            }

        system_prompt = (
            "És o tutor académico do JARVIS OS. Responde em Português Europeu rigoroso, "
            "USANDO EXCLUSIVAMENTE as evidências fornecidas do documento abaixo. "
            "Nunca inventes números de página, secções ou factos externos.\n"
            "Classifica CADA afirmação usando estritamente um destes valores:\n"
            "- SOURCE_FACT: afirmado diretamente nas passagens citadas.\n"
            "- MODEL_INFERENCE: síntese pedagógica ou ligação razoável derivada das passagens.\n"
            "- NOT_FOUND: não consta no material fornecido.\n"
            "- UNVERIFIED: mencionado sem evidência conclusiva.\n\n"
            "Devolve APENAS JSON válido com a estrutura:\n"
            "{\n"
            '  "answer_intro": "síntese clara em 1-3 frases",\n'
            '  "claims": [\n'
            '    {"statement": "...", "epistemic_status": "SOURCE_FACT|MODEL_INFERENCE|NOT_FOUND|UNVERIFIED", "citations": ["p. X, § Y"]}\n'
            "  ],\n"
            '  "missing_information": "opcional: o que falta na fonte ou string vazia",\n'
            '  "concepts": ["conceito1", "conceito2"]\n'
            "}"
        )
        user_prompt = (
            f"Documento: {doc.title} (ID: {document_id})\n"
            f"Pergunta/Pedido: {question}\n"
            f"Capítulo/Secção alvo: {evidence_bundle.get('scope_label') or 'Geral'}\n\n"
            f"Conceitos & Estrutura Relevante:\n{evidence_bundle['structured_context']}\n\n"
            f"Passagens e Evidências da Fonte:\n{evidence_bundle['passages_text']}\n"
        )

        raw_parsed = await self._call_local_llm_json(
            operation="study_chat_explain",
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            document_id=document_id,
        )
        return self._format_grounded_response(
            doc_title=getattr(doc, "title", document_id),
            raw_parsed=raw_parsed,
            evidence_bundle=evidence_bundle,
        )

    async def compare_concepts(
        self,
        study_service: Any,
        *,
        document_id: str,
        concept_a: str,
        concept_b: str,
        question: str,
    ) -> Dict[str, Any]:
        doc = study_service.get_document(document_id)
        if not doc:
            raise ValueError(f"Documento '{document_id}' não encontrado.")

        combined_query = f"{concept_a} {concept_b} {question}".strip()
        bundle_a = self._gather_document_evidence(
            study_service, doc=doc, query=concept_a, topic=concept_a
        )
        bundle_b = self._gather_document_evidence(
            study_service, doc=doc, query=concept_b, topic=concept_b
        )
        merged_passages = list(
            {p["ref"]: p for p in [*bundle_a["passages"], *bundle_b["passages"]]}.values()
        )[:8]
        merged_concepts = list(dict.fromkeys([*bundle_a["concepts"], *bundle_b["concepts"]]))[:12]

        if not merged_passages and not bundle_a["concepts"] and not bundle_b["concepts"]:
            return {
                "summary_markdown": (
                    f"Não encontrei evidência sobre **{concept_a}** e **{concept_b}** em **{doc.title}**.\n\n"
                    "- Classificação: **NOT_FOUND**"
                ),
                "citations": [],
                "epistemic_breakdown": {
                    "primary_status": "NOT_FOUND",
                    "claims": [
                        {
                            "statement": f"Os conceitos '{concept_a}' e '{concept_b}' não têm suporte verificável neste documento.",
                            "epistemic_status": "NOT_FOUND",
                            "citations": [],
                        }
                    ],
                },
                "concepts_used": [],
            }

        combined_bundle = {
            "scope_label": f"Comparação: {concept_a} vs {concept_b}",
            "passages": merged_passages,
            "concepts": merged_concepts,
            "valid_citations": sorted({p["ref"] for p in merged_passages if p.get("ref")}),
            "structured_context": (
                f"Contexto A ({concept_a}):\n{bundle_a['structured_context']}\n\n"
                f"Contexto B ({concept_b}):\n{bundle_b['structured_context']}"
            ),
            "passages_text": "\n".join(
                f"[{p['ref']}] {p['text']}" for p in merged_passages
            ),
        }

        system_prompt = (
            "És o tutor académico do JARVIS OS. Compara rigorosamente os dois conceitos com base "
            "EXCLUSIVAMENTE nas evidências do documento. Se um dos conceitos não estiver no documento, "
            "declara explicitamente NOT_FOUND.\n"
            "Devolve APENAS JSON válido:\n"
            "{\n"
            '  "answer_intro": "visão comparativa objetiva",\n'
            '  "claims": [\n'
            '    {"statement": "...", "epistemic_status": "SOURCE_FACT|MODEL_INFERENCE|NOT_FOUND|UNVERIFIED", "citations": ["p. X, § Y"]}\n'
            "  ],\n"
            '  "missing_information": "o que o documento não compara explicitamente",\n'
            '  "concepts": ["..."]\n'
            "}"
        )
        user_prompt = (
            f"Documento: {doc.title}\nPedido: {combined_query}\n"
            f"Conceito A: {concept_a}\nConceito B: {concept_b}\n\n"
            f"{combined_bundle['structured_context']}\n\n"
            f"Passagens da Fonte:\n{combined_bundle['passages_text']}"
        )
        raw_parsed = await self._call_local_llm_json(
            operation="study_chat_compare",
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            document_id=document_id,
        )
        return self._format_grounded_response(
            doc_title=getattr(doc, "title", document_id),
            raw_parsed=raw_parsed,
            evidence_bundle=combined_bundle,
        )

    def _gather_document_evidence(
        self,
        study_service: Any,
        *,
        doc: Any,
        query: str,
        chapter_id: Optional[str] = None,
        section_id: Optional[str] = None,
        topic: str = "",
        recent_concepts: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        doc_id = doc.document_id
        ast_dict = study_service.get_document_ast(doc_id) if hasattr(study_service, "get_document_ast") else None
        dossier = (
            study_service.get_academic_reasoning_dossier(doc_id)
            if hasattr(study_service, "get_academic_reasoning_dossier")
            else None
        )
        plan = (
            study_service.get_editorial_study_plan(doc_id)
            if hasattr(study_service, "get_editorial_study_plan")
            else None
        )

        # Determinar secções permitidas quando um capítulo ou secção é alvo explícito
        allowed_sec_ids: set[str] = set()
        structured_lines: List[str] = []
        scope_label = ""

        if plan and chapter_id:
            for ch in plan.get("chapters") or []:
                if str(ch.get("chapter_id")) == chapter_id:
                    scope_label = str(ch.get("title") or chapter_id)
                    structured_lines.append(
                        f"Capítulo Editorial '{ch.get('title')}': objetivo='{ch.get('pedagogical_objective', '')}'"
                    )
                    for orig_cid in ch.get("original_section_ids") or []:
                        allowed_sec_ids.add(str(orig_cid))
                    for es in ch.get("sections") or []:
                        if es.get("section_id"):
                            allowed_sec_ids.add(str(es["section_id"]))
                        for orig in es.get("original_section_ids") or []:
                            allowed_sec_ids.add(str(orig))
                        expl = es.get("pedagogical_explanation") or es.get("summary") or ""
                        if expl:
                            structured_lines.append(f"- {es.get('title', 'Secção')}: {str(expl)[:320]}")
                    break
        if section_id:
            allowed_sec_ids.add(section_id)
            if not scope_label:
                scope_label = section_id

        # Recolher conceitos e relações relevantes do ReasoningDossier (Fase 3)
        matched_concepts: List[str] = []
        is_overview_query = bool(allowed_sec_ids) or any(
            kw in normalize_match_text(query)
            for kw in (
                "conceitos mais importantes", "principais conceitos", "resumo", "visao geral",
                "tese", "objetivo", "o que trata", "argumentos centrais", "explica o capitulo",
                "explica-me o capitulo", "segundo capitulo", "primeiro capitulo",
            )
        )
        if dossier:
            q_norm = normalize_match_text(f"{query} {topic}")
            concepts_src = dossier.get("conceptual_analysis") or dossier.get("concepts") or []
            for c in concepts_src:
                name = str(c.get("name") or c.get("term") or "").strip()
                defn = str(c.get("definition") or c.get("explanation") or "").strip()
                if not name:
                    continue
                n_norm = normalize_match_text(name)
                if (
                    n_norm in q_norm
                    or any(tok in n_norm or tok in normalize_match_text(defn) for tok in q_norm.split() if len(tok) > 3)
                    or not q_norm
                    or is_overview_query
                ):
                    matched_concepts.append(name)
                    structured_lines.append(f"Conceito '{name}': {defn[:240]}")
                if len(matched_concepts) >= 8:
                    break

            for sa in dossier.get("section_analyses") or []:
                sa_sid = str(sa.get("section_id") or "")
                if allowed_sec_ids and sa_sid not in allowed_sec_ids:
                    continue
                synth = str(sa.get("in_depth_synthesis") or "").strip()
                sa_hay = normalize_match_text(f"{sa.get('title', '')} {synth}")
                if synth and (is_overview_query or any(tok in sa_hay for tok in q_norm.split() if len(tok) > 3)):
                    structured_lines.append(f"Secção '{sa.get('title', sa_sid)}': {synth[:320]}")

            doc_analysis = dossier.get("document_analysis") or {}
            if doc_analysis.get("central_thesis") and is_overview_query and not allowed_sec_ids:
                structured_lines.append(f"Tese central: {str(doc_analysis['central_thesis'])[:280]}")

            meth = dossier.get("methodology_analysis") or {}
            if meth and ("metodolog" in q_norm or any(s in allowed_sec_ids for s in ["sec_02"])):
                methods_used = ", ".join(str(m) for m in (meth.get("methods_used") or [])[:4])
                sample = str(meth.get("sample_or_participants") or "")
                if methods_used or sample:
                    structured_lines.append(f"Metodologia ({meth.get('research_type', '')}): {methods_used} | Amostra: {sample}")

            if is_overview_query or any(w in q_norm for w in ("resultado", "resultados", "evidencia", "precisao", "latencia")):
                for res_item in (dossier.get("results_and_evidence") or [])[:4]:
                    if isinstance(res_item, dict) and res_item.get("statement"):
                        structured_lines.append(f"Resultado: {str(res_item['statement'])[:220]} ({res_item.get('evidence_data', '')})")

            synth_cross = (dossier.get("cross_section_synthesis") or {})
            if synth_cross.get("global_synthesis") and is_overview_query and not allowed_sec_ids:
                structured_lines.append(f"Síntese global: {str(synth_cross['global_synthesis'])[:280]}")

        # Recolher parágrafos reais da AST (paragraphs top-level por section_id + inline) ou StudyDocument
        raw_sections = list((ast_dict or {}).get("sections") or []) or list(getattr(doc, "sections", []) or [])
        sec_title_map: Dict[str, str] = {}
        sec_inline_paragraphs: Dict[str, List[Dict[str, Any]]] = {}
        for sec in raw_sections:
            sid = str(sec.get("section_id") or "")
            sec_title_map[sid] = str(sec.get("title") or "Secção")
            for p in sec.get("paragraphs") or []:
                sec_inline_paragraphs.setdefault(sid, []).append(p)

        top_paragraphs_by_sec: Dict[str, List[Dict[str, Any]]] = {}
        for p in (ast_dict or {}).get("paragraphs") or []:
            if isinstance(p, dict):
                sid = str(p.get("section_id") or "")
                top_paragraphs_by_sec.setdefault(sid, []).append(p)

        q_tokens = [
            t
            for t in re.findall(r"[a-z0-9]{3,}", normalize_match_text(f"{query} {topic}"))
            if t not in {
                "este", "esta", "esse", "documento", "artigo", "paper", "capitulo", "chapter",
                "explica", "quais", "qual", "como", "sobre", "para", "diferenca", "entre",
                "melhor", "parte", "quero", "saber", "conceitos", "principais", "mais",
                "importantes", "deste", "segundo", "primeiro",
            }
        ]
        # Se utilizador pede capítulo/secção específica sem outros tokens, dar prioridade direta a essas secções
        candidates: List[Tuple[int, Dict[str, Any]]] = []
        for sec in raw_sections:
            sid = str(sec.get("section_id") or "")
            stitle = sec_title_map.get(sid, "Secção")
            in_target_scope = not allowed_sec_ids or (sid in allowed_sec_ids)
            if allowed_sec_ids and not in_target_scope:
                continue
            paragraphs = top_paragraphs_by_sec.get(sid) or sec_inline_paragraphs.get(sid) or []
            for p in paragraphs:
                txt = str(p.get("text") or "").strip()
                if not txt:
                    continue
                pg = p.get("page_number") or sec.get("page_start") or sec.get("page_number") or 1
                ref = f"p. {pg}, § {stitle}"
                txt_norm = normalize_match_text(f"{stitle} {txt}")
                q_token_hits = sum(1 for tok in q_tokens if tok in txt_norm)
                score = q_token_hits * 3
                if in_target_scope and allowed_sec_ids and not q_tokens:
                    score += 5
                elif in_target_scope and allowed_sec_ids and q_token_hits > 0:
                    score += 5
                if recent_concepts and (not q_tokens or q_token_hits > 0):
                    for rc in recent_concepts[:4]:
                        if normalize_match_text(rc) in txt_norm:
                            score += 2
                if not q_tokens and not allowed_sec_ids:
                    score += 1
                if score > 0 or (in_target_scope and allowed_sec_ids and not q_tokens):
                    candidates.append(
                        (
                            score,
                            {
                                "section_id": sid,
                                "page_number": int(pg),
                                "ref": ref,
                                "text": txt[:550],
                            },
                        )
                    )

        candidates.sort(key=lambda item: item[0], reverse=True)
        top_passages = [item[1] for item in candidates[:6]]

        # Fallback: usar StudyService.ask_paper quando AST não devolver hits mas o texto tiver match
        if not top_passages and hasattr(study_service, "ask_paper"):
            ask_res = study_service.ask_paper(doc_id, query, section_id=section_id)
            if isinstance(ask_res, dict) and ask_res.get("evidence_status") != "INSUFFICIENT_EVIDENCE":
                for idx, src in enumerate(ask_res.get("sources") or []):
                    ev = str(ask_res.get("evidence") or ask_res.get("answer") or "")
                    top_passages.append(
                        {
                            "section_id": section_id or "",
                            "page_number": 1,
                            "ref": str(src),
                            "text": ev[:450] if idx == 0 else str(src),
                        }
                    )

        return {
            "scope_label": scope_label,
            "passages": top_passages,
            "concepts": matched_concepts,
            "valid_citations": sorted({p["ref"] for p in top_passages if p.get("ref")}),
            "structured_context": "\n".join(structured_lines[:12]) or "Sem síntese prévia adicional.",
            "passages_text": "\n".join(f"[{p['ref']}] {p['text']}" for p in top_passages),
        }

    async def _call_local_llm_json(
        self,
        *,
        operation: str,
        system_prompt: str,
        user_prompt: str,
        document_id: str,
    ) -> Dict[str, Any]:
        if self.llm_caller is not None:
            res = self.llm_caller(
                operation=operation,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                expect_json=True,
                document_id=document_id,
            )
            if asyncio.iscoroutine(res):
                res = await res
            if isinstance(res, dict):
                return res
            if isinstance(res, str):
                parsed = self._safe_parse_json(res)
                if parsed is not None:
                    return parsed
            raise ValueError("Resposta inválida do modelo local para explicação académica.")

        if self.model_service is not None:
            from backend.model_harness.contracts import OutputFormat

            model_name = os.getenv("OLLAMA_STUDY_MODEL", os.getenv("OLLAMA_MODEL", "qwen3.5:9b"))
            try:
                response = await self.model_service.execute(
                    provider="ollama",
                    model=model_name,
                    operation=operation,
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    output_format=OutputFormat.JSON,
                    temperature=0.1,
                    max_output_tokens=1600,
                    timeout_seconds=60.0,
                )
            except Exception as exc:
                raise OllamaUnavailableError(
                    f"Inferência local Ollama ({model_name}) indisponível: {exc}"
                ) from exc

            parsed = (
                response.structured_output
                if isinstance(response.structured_output, dict)
                else self._safe_parse_json(response.raw_text)
            )
            if isinstance(parsed, dict):
                return parsed
            raise ValueError("O modelo local devolveu JSON inválido durante a explicação.")

        from services.study_ai_engine import invoke_study_llm_observable

        parsed, telemetry = await asyncio.to_thread(
            invoke_study_llm_observable,
            operation=operation,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            expect_json=True,
            temperature=0.1,
            max_output_tokens=1600,
            timeout_seconds=60.0,
            document_id=document_id,
        )
        if isinstance(parsed, dict):
            return parsed
        err = telemetry.get("error") or "Modelo local Ollama indisponível ou resposta inválida."
        raise OllamaUnavailableError(str(err))

    @staticmethod
    def _safe_parse_json(raw: str) -> Optional[Dict[str, Any]]:
        txt = str(raw or "").strip()
        if not txt:
            return None
        match = re.search(r"\{.*\}", txt, re.DOTALL)
        candidate = match.group(0) if match else txt
        try:
            obj = json.loads(candidate)
            return obj if isinstance(obj, dict) else None
        except Exception:
            return None

    def _format_grounded_response(
        self,
        *,
        doc_title: str,
        raw_parsed: Dict[str, Any],
        evidence_bundle: Dict[str, Any],
    ) -> Dict[str, Any]:
        valid_cits = set(evidence_bundle.get("valid_citations") or [])
        claims_out: List[Dict[str, Any]] = []
        used_cits: List[str] = []

        for item in raw_parsed.get("claims") or []:
            if not isinstance(item, dict):
                continue
            stmt = str(item.get("statement") or "").strip()
            if not stmt:
                continue
            raw_status = str(item.get("epistemic_status") or "MODEL_INFERENCE").strip().upper()
            if raw_status not in VALID_EPISTEMIC:
                raw_status = "UNVERIFIED"
            raw_cits = [str(c).strip() for c in (item.get("citations") or []) if str(c).strip()]
            # Validação epistémica estrita: aceitar apenas citações reais ou degradar SOURCE_FACT sem âncora
            verified_cits = [
                c for c in raw_cits if (c in valid_cits or any(vc in c or c in vc for vc in valid_cits))
            ]
            if raw_status == "SOURCE_FACT" and not verified_cits:
                if valid_cits:
                    raw_status = "MODEL_INFERENCE"
                else:
                    raw_status = "UNVERIFIED"
            for vc in verified_cits:
                if vc not in used_cits:
                    used_cits.append(vc)
            claims_out.append(
                {
                    "statement": stmt,
                    "epistemic_status": raw_status,
                    "citations": verified_cits,
                }
            )

        intro = str(raw_parsed.get("answer_intro") or "").strip()
        missing = str(raw_parsed.get("missing_information") or "").strip()
        concepts_used = [str(c).strip() for c in (raw_parsed.get("concepts") or evidence_bundle.get("concepts") or []) if str(c).strip()][:8]

        if not used_cits and valid_cits and any(c["epistemic_status"] == "SOURCE_FACT" for c in claims_out):
            used_cits = sorted(valid_cits)[:3]

        statuses = [c["epistemic_status"] for c in claims_out]
        if "SOURCE_FACT" in statuses:
            primary_status = "SOURCE_FACT"
        elif "MODEL_INFERENCE" in statuses:
            primary_status = "MODEL_INFERENCE"
        elif "NOT_FOUND" in statuses:
            primary_status = "NOT_FOUND"
        else:
            primary_status = "UNVERIFIED"

        lines: List[str] = [f"### {doc_title}"]
        if evidence_bundle.get("scope_label"):
            lines.append(f"**Âmbito:** {evidence_bundle['scope_label']}\n")
        if intro:
            lines.append(intro)
        if claims_out:
            lines.append("")
            for cl in claims_out:
                badge = cl["epistemic_status"]
                cit_txt = f" — *{' | '.join(cl['citations'])}*" if cl["citations"] else ""
                lines.append(f"- **[{badge}]** {cl['statement']}{cit_txt}")
        if missing:
            lines.append(f"\n> **Limitação da fonte (NOT_FOUND):** {missing}")
        if used_cits:
            lines.append(f"\n**Fontes citadas:** {', '.join(used_cits)}")

        return {
            "summary_markdown": "\n".join(lines).strip(),
            "citations": used_cits or sorted(valid_cits)[:4],
            "epistemic_breakdown": {
                "primary_status": primary_status,
                "claims": claims_out,
            },
            "concepts_used": concepts_used,
        }
