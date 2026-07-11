import os
import json
from crewai import Agent, Task, Crew, LLM

try:
    from agents.swarm import CREW_TOOLS
except ImportError:
    CREW_TOOLS = []

import agents.globals as glb
from agents.providers.factory import build_crewai_llm

# Inicializa o modelo configurado em ORCHESTRATOR_MODE.
planner_llm = build_crewai_llm(LLM)

class PersistentPlanner:
    def __init__(self, workspace_root: str = "."):
        self.workspace_root = workspace_root
        self.plan_path = os.path.join(self.workspace_root, ".jarvis_plan.json")

    def load_plan(self):
        if os.path.exists(self.plan_path):
            with open(self.plan_path, "r", encoding="utf-8") as f:
                return json.load(f)
        return {"goal": "", "steps": [], "status": "NONE"}

    def save_plan(self, plan_data):
        with open(self.plan_path, "w", encoding="utf-8") as f:
            json.dump(plan_data, f, indent=4, ensure_ascii=False)

    def create_plan(self, goal: str) -> dict:
        """
        Usa um Agente de Arquitetura para dividir o pedido em passos discretos e persistentes.
        """
        print(f"\n[Planner] A gerar plano persistente para o objetivo: {goal}")
        
        planner_agent = Agent(
            role="Tech Lead Planner",
            goal="Dividir objetivos complexos em passos atómicos, técnicos e executáveis.",
            backstory="És um arquiteto de software brilhante. Respondes estritamente com JSON válido.",
            verbose=False,
            llm=planner_llm
        )
        
        plan_task = Task(
            description=f"Analisa o objetivo: '{goal}'. Cria um plano de execução passo a passo em formato JSON estrito.\n"
                        f"O formato OBRIGATÓRIO é:\n"
                        f"{{\n"
                        f'  "goal": "{goal}",\n'
                        f'  "steps": [\n'
                        f'    {{"id": 1, "action": "Ação concreta (ex: Criar ficheiro X)", "status": "PENDING"}}\n'
                        f'  ],\n'
                        f'  "status": "PENDING"\n'
                        f"}}\n"
                        f"Apenas responde com o JSON puro sem formatação markdown à volta.",
            expected_output="JSON estrito e válido",
            agent=planner_agent
        )
        
        crew = Crew(agents=[planner_agent], tasks=[plan_task])
        result = crew.kickoff()
        
        raw_text = str(result).strip()
        if raw_text.startswith("```json"):
            raw_text = raw_text.split("```json")[1].split("```")[0].strip()
        elif raw_text.startswith("```"):
            raw_text = raw_text.split("```")[1].split("```")[0].strip()
            
        try:
            plan_data = json.loads(raw_text)
            self.save_plan(plan_data)
            print("[Planner] Ficheiro .jarvis_plan.json gerado com sucesso!")
            return plan_data
        except Exception as e:
            print(f"[Planner] Erro ao parsear JSON do agente: {e}. A usar plano de Fallback.")
            fallback = {
                "goal": goal,
                "steps": [
                    {"id": 1, "action": "Investigar o contexto do pedido", "status": "PENDING"},
                    {"id": 2, "action": f"Executar e resolver o pedido: '{goal}'", "status": "PENDING"}
                ],
                "status": "PENDING"
            }
            self.save_plan(fallback)
            return fallback

    def execute_next_step(self) -> str:
        """
        Lê o plano, pega no próximo passo PENDING e orquestra um Agente para o executar.
        """
        plan = self.load_plan()
        
        if plan.get("status") == "DONE":
            return "[Planner] O plano atual já foi concluído na totalidade."
            
        pending_steps = [s for s in plan.get("steps", []) if s.get("status") == "PENDING"]
        
        if not pending_steps:
            plan["status"] = "DONE"
            self.save_plan(plan)
            return "[Planner] ✅ Todos os passos foram concluídos com sucesso!"
            
        step = pending_steps[0]
        step_id = step["id"]
        action = step["action"]
        
        print(f"\n[Planner] ---> A iniciar Passo {step_id}: {action} <---")
        
        executor = Agent(
            role="Autonomous Engineer",
            goal="Executar a tarefa isolada com máxima precisão recorrendo às ferramentas do Jarvis.",
            backstory="És um engenheiro robótico pragmático e direto. Usas a ferramenta apply_code_patch para alterar código sem partir o build.",
            verbose=True,
            llm=planner_llm,
            tools=CREW_TOOLS
        )
        
        exec_task = Task(
            description=f"Isto faz parte de um plano maior.\n"
                        f"Objetivo Global do utilizador: {plan['goal']}\n\n"
                        f"A TUA TAREFA AGORA: {action}\n\n"
                        f"Usa as tools que tens disponíveis (patch_engine, file read, command exec) para atingir este objetivo. Se não conseguires de imediato, reflete e tenta de outra forma.",
            expected_output="Relatório final sobre como a tarefa foi concluída ou porque falhou.",
            agent=executor
        )
        
        crew = Crew(agents=[executor], tasks=[exec_task])
        result = crew.kickoff()
        
        # Regista sucesso
        for s in plan["steps"]:
            if s["id"] == step_id:
                s["status"] = "DONE"
                s["result"] = str(result)
                break
                
        self.save_plan(plan)
        return f"[Planner] Passo {step_id} concluído.\nResumo do Agente: {result}"
