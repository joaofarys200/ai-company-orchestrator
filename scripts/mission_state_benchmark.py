from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import time
from pathlib import Path
from typing import Callable

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from agents.mission_state import MissionStateError, MissionStateStore, StaleVersionError


Benchmark = Callable[[MissionStateStore, Path], dict]


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def prepare(root: Path, *project_ids: str) -> MissionStateStore:
    for project_id in project_ids:
        (root / "workspace" / "projects" / project_id).mkdir(parents=True, exist_ok=True)
    return MissionStateStore(str(root))


def wp(snapshot: dict, item_id: str) -> dict:
    return next(item for item in snapshot["work_packages"] if item["work_package_id"] == item_id)


def deliverable(snapshot: dict, item_id: str) -> dict:
    return next(item for item in snapshot["deliverables"] if item["deliverable_id"] == item_id)


def criterion(snapshot: dict, item_id: str) -> dict:
    return next(item for item in snapshot["acceptance_criteria"] if item["criterion_id"] == item_id)


def satisfy_wp(store: MissionStateStore, snapshot: dict, mission_id: str, work_package_id: str, suffix: str) -> dict:
    criterion_id = f"criterion-{suffix}"
    evidence_id = f"evidence-{suffix}"
    snapshot = store.create_criterion(
        "project", mission_id, "WORK_PACKAGE", work_package_id,
        "Evidencia verificada", ["VALIDATION"], criterion_id=criterion_id,
    )
    snapshot = store.attach_evidence(
        "project", mission_id, work_package_id, "VALIDATION", f"validation:{suffix}", evidence_id=evidence_id,
    )
    return store.set_criterion_status(
        "project", mission_id, criterion_id, "SATISFIED", criterion(snapshot, criterion_id)["version"], [evidence_id]
    )


def m001(store: MissionStateStore, root: Path) -> dict:
    snapshot = store.create_mission("project", "Persistencia", "Persistir estado", mission_id="m001")
    loaded = MissionStateStore(str(root)).load_mission("project", "m001")
    require(loaded["mission"] == snapshot["mission"], "Mission nao sobreviveu a reload.")
    return {"mission_path": "workspace/.jarvis/projects/project/missions/m001/mission.json"}


def m002(store: MissionStateStore, _root: Path) -> dict:
    store.create_mission("project", "DAG", "Validar DAG", mission_id="m002")
    store.create_work_package("project", "m002", "A", work_package_id="a")
    snapshot = store.create_work_package("project", "m002", "B", dependencies=["a"], work_package_id="b")
    require(wp(snapshot, "b")["dependencies"] == ["a"], "Aresta do DAG nao persistiu.")
    return {"edges": 1}


def m003(store: MissionStateStore, _root: Path) -> dict:
    store.create_mission("project", "Ciclos", "Bloquear ciclos", mission_id="m003")
    snapshot = store.create_work_package("project", "m003", "A", work_package_id="a")
    snapshot = store.create_work_package("project", "m003", "B", dependencies=["a"], work_package_id="b")
    try:
        store.add_dependency("project", "m003", "a", "b", wp(snapshot, "a")["version"])
    except MissionStateError as exc:
        require("ciclo" in str(exc).lower(), "Falha nao identificou o ciclo.")
        return {"blocked": True}
    raise AssertionError("Ciclo direto nao foi bloqueado.")


def m004(store: MissionStateStore, _root: Path) -> dict:
    store.create_mission("project", "READY", "Derivar elegibilidade", mission_id="m004")
    snapshot = store.create_work_package("project", "m004", "Dataset", work_package_id="dataset")
    snapshot = store.create_work_package("project", "m004", "Baseline", dependencies=["dataset"], work_package_id="baseline")
    require(wp(snapshot, "dataset")["status"] == "READY", "Raiz do DAG nao esta READY.")
    require(wp(snapshot, "baseline")["status"] == "PENDING", "Dependente devia estar PENDING.")
    snapshot = store.set_work_package_status("project", "m004", "dataset", "IN_PROGRESS", wp(snapshot, "dataset")["version"])
    snapshot = satisfy_wp(store, snapshot, "m004", "dataset", "m004-dataset")
    snapshot = store.set_work_package_status("project", "m004", "dataset", "COMPLETED", wp(snapshot, "dataset")["version"])
    require(wp(snapshot, "baseline")["status"] == "READY", "Dependente nao ficou READY.")
    return {"eligible": snapshot["eligible_work_packages"]}


def m005(store: MissionStateStore, _root: Path) -> dict:
    store.create_mission("project", "Deliverable", "Exigir deliverable", mission_id="m005")
    snapshot = store.create_work_package("project", "m005", "Relatorio", work_package_id="wp")
    snapshot = store.create_deliverable("project", "m005", "wp", "Relatorio", required=True, deliverable_id="report")
    snapshot = store.set_work_package_status("project", "m005", "wp", "IN_PROGRESS", wp(snapshot, "wp")["version"])
    snapshot = satisfy_wp(store, snapshot, "m005", "wp", "m005-wp")
    try:
        store.set_work_package_status("project", "m005", "wp", "COMPLETED", wp(snapshot, "wp")["version"])
    except MissionStateError:
        snapshot = store.set_deliverable_status("project", "m005", "report", "ACCEPTED", deliverable(snapshot, "report")["version"])
        snapshot = store.set_work_package_status("project", "m005", "wp", "COMPLETED", wp(snapshot, "wp")["version"])
        require(wp(snapshot, "wp")["status"] == "COMPLETED", "WP nao concluiu depois de aceitar deliverable.")
        return {"mandatory_deliverable_enforced": True}
    raise AssertionError("WP concluiu com deliverable obrigatorio nao aceite.")


def m006(store: MissionStateStore, _root: Path) -> dict:
    store.create_mission("project", "Evidence", "Exigir Evidence", mission_id="m006")
    snapshot = store.create_work_package("project", "m006", "Validar", work_package_id="wp")
    snapshot = store.create_criterion(
        "project", "m006", "WORK_PACKAGE", "wp", "Teste passou", ["VALIDATION"], criterion_id="criterion"
    )
    try:
        store.set_criterion_status("project", "m006", "criterion", "SATISFIED", criterion(snapshot, "criterion")["version"], [])
    except MissionStateError:
        snapshot = store.attach_evidence(
            "project", "m006", "wp", "VALIDATION", "validation:benchmark-m006", evidence_id="proof"
        )
        snapshot = store.set_criterion_status(
            "project", "m006", "criterion", "SATISFIED", criterion(snapshot, "criterion")["version"], ["proof"]
        )
        require(criterion(snapshot, "criterion")["status"] == "SATISFIED", "Criterion nao foi satisfeito.")
        return {"evidence_required": True}
    raise AssertionError("Criterion foi satisfeito sem Evidence.")


def m007(store: MissionStateStore, _root: Path) -> dict:
    snapshot = store.create_mission("project", "Prematura", "Bloquear conclusao", mission_id="m007")
    snapshot = store.create_work_package("project", "m007", "Pendente", work_package_id="wp")
    snapshot = store.set_mission_status("project", "m007", "READY", snapshot["mission"]["version"])
    snapshot = store.set_mission_status("project", "m007", "ACTIVE", snapshot["mission"]["version"])
    try:
        store.set_mission_status("project", "m007", "COMPLETED", snapshot["mission"]["version"])
    except MissionStateError:
        return {"premature_completion_blocked": True}
    raise AssertionError("Mission concluiu prematuramente.")


def m008(store: MissionStateStore, _root: Path) -> dict:
    snapshot = store.create_mission("project", "Lock", "Optimistic locking", mission_id="m008")
    stale = snapshot["mission"]["version"]
    store.update_mission("project", "m008", stale, {"current_phase": "A"})
    try:
        store.update_mission("project", "m008", stale, {"current_phase": "B"})
    except StaleVersionError:
        return {"stale_update_rejected": True}
    raise AssertionError("Update stale nao foi rejeitado.")


def m009(store: MissionStateStore, root: Path) -> dict:
    store.create_mission("project", "Restart", "Retomar", mission_id="m009")
    store.create_work_package("project", "m009", "Elegivel", work_package_id="wp")
    resumed = MissionStateStore(str(root)).load_mission("project", "m009")
    require(resumed["eligible_work_packages"] == ["wp"], "Snapshot retomado perdeu elegibilidade.")
    require(len(resumed["recent_events"]) >= 2, "Eventos nao sobreviveram ao restart.")
    return {"events": len(resumed["recent_events"])}


def m010(store: MissionStateStore, _root: Path) -> dict:
    store.create_mission("project", "Isolada A", "A", mission_id="same-id")
    store.create_mission("other", "Isolada B", "B", mission_id="same-id")
    require(store.load_mission("project", "same-id")["mission"]["title"] == "Isolada A", "Projeto A contaminado.")
    require(store.load_mission("other", "same-id")["mission"]["title"] == "Isolada B", "Projeto B contaminado.")
    return {"isolated": True}


def m011(store: MissionStateStore, root: Path) -> dict:
    legacy = root / ".jarvis_plan.json"
    legacy.write_text(json.dumps({"goal": "Legado", "status": "PENDING", "steps": [{"id": 1, "action": "A", "status": "PENDING"}]}), encoding="utf-8")
    before = legacy.read_bytes()
    preview = store.legacy_plan_to_mission_preview()
    require(preview and preview["read_only"], "Preview legado nao e read-only.")
    require(legacy.read_bytes() == before, "Preview alterou o plano legado.")
    return {"migration_performed": preview["migration_performed"]}


def m012(store: MissionStateStore, _root: Path) -> dict:
    snapshot = store.create_mission(
        "project",
        "Projeto universitario de detecao de fraude",
        "Revisao, dataset, baseline, experiencias, relatorio e apresentacao",
        mission_id="fraud-university",
    )
    definitions = [
        ("wp1", "Revisao bibliografica", "RESEARCH", []),
        ("wp2", "Preparacao de dataset", "RESEARCH", []),
        ("wp3", "Implementacao baseline", "CODING", ["wp2"]),
        ("wp4", "Experiencias", "EXPERIMENT", ["wp3"]),
        ("wp5", "Relatorio", "DOCUMENT", ["wp1", "wp4"]),
        ("wp6", "Apresentacao", "DOCUMENT", ["wp5"]),
        ("wp7", "Revisao final", "REVIEW", ["wp5", "wp6"]),
    ]
    for item_id, title, item_type, dependencies in definitions:
        snapshot = store.create_work_package(
            "project", "fraud-university", title, type=item_type, dependencies=dependencies, work_package_id=item_id
        )
    require(set(snapshot["eligible_work_packages"]) == {"wp1", "wp2"}, "WP1 e WP2 deviam estar READY inicialmente.")
    require(all(wp(snapshot, item_id)["status"] == "PENDING" for item_id in ("wp3", "wp4", "wp5", "wp6", "wp7")), "Dependentes deviam estar PENDING.")
    try:
        store.set_work_package_status("project", "fraud-university", "wp3", "IN_PROGRESS", wp(snapshot, "wp3")["version"])
    except MissionStateError:
        pass
    else:
        raise AssertionError("WP3 iniciou antes de WP2.")

    snapshot = store.set_mission_status("project", "fraud-university", "READY", snapshot["mission"]["version"])
    snapshot = store.set_mission_status("project", "fraud-university", "ACTIVE", snapshot["mission"]["version"])
    for item_id in ("wp1", "wp2", "wp3", "wp4", "wp5", "wp6", "wp7"):
        deliverable_id = f"deliverable-{item_id}"
        criterion_id = f"criterion-{item_id}"
        evidence_id = f"evidence-{item_id}"
        snapshot = store.create_deliverable(
            "project", "fraud-university", item_id, f"Resultado {item_id}", kind="ACADEMIC_ARTIFACT",
            required=True, deliverable_id=deliverable_id,
        )
        snapshot = store.create_criterion(
            "project", "fraud-university", "WORK_PACKAGE", item_id, f"{item_id} validado",
            ["VALIDATION"], criterion_id=criterion_id,
        )
        snapshot = store.attach_evidence(
            "project", "fraud-university", item_id, "VALIDATION", f"validation:{item_id}",
            deliverable_id=deliverable_id, evidence_id=evidence_id,
        )
        snapshot = store.set_criterion_status(
            "project", "fraud-university", criterion_id, "SATISFIED", criterion(snapshot, criterion_id)["version"], [evidence_id]
        )
        snapshot = store.set_deliverable_status(
            "project", "fraud-university", deliverable_id, "ACCEPTED", deliverable(snapshot, deliverable_id)["version"]
        )
        snapshot = store.set_work_package_status(
            "project", "fraud-university", item_id, "IN_PROGRESS", wp(snapshot, item_id)["version"]
        )
        snapshot = store.set_work_package_status(
            "project", "fraud-university", item_id, "COMPLETED", wp(snapshot, item_id)["version"]
        )
    snapshot = store.set_mission_status(
        "project", "fraud-university", "COMPLETED", snapshot["mission"]["version"]
    )
    resumed = MissionStateStore(store.workspace_root).load_mission("project", "fraud-university")
    require(resumed["mission"]["status"] == "COMPLETED", "Mission completa nao sobreviveu ao restart.")
    require(resumed["mission"]["progress"] == 100.0, "Progresso final nao e 100%.")
    return {"work_packages": 7, "events": len(resumed["recent_events"]), "status": "COMPLETED"}


BENCHMARKS: list[tuple[str, Benchmark]] = [
    ("M001", m001), ("M002", m002), ("M003", m003), ("M004", m004),
    ("M005", m005), ("M006", m006), ("M007", m007), ("M008", m008),
    ("M009", m009), ("M010", m010), ("M011", m011), ("M012", m012),
]


def classification(passed: int) -> str:
    if passed == len(BENCHMARKS):
        return "STABLE_MISSION_STATE"
    if passed >= 8:
        return "BASIC_MISSION_STATE"
    return "PROTO_MISSION_STATE"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", choices=[name for name, _ in BENCHMARKS])
    args = parser.parse_args()
    selected = [(name, fn) for name, fn in BENCHMARKS if not args.only or args.only == name]
    results = []
    with tempfile.TemporaryDirectory(prefix="jarvis-mission-benchmark-") as temp_dir:
        root = Path(temp_dir)
        store = prepare(root, "project", "other")
        for name, benchmark in selected:
            started = time.perf_counter()
            try:
                details = benchmark(store, root)
                results.append({"id": name, "status": "PASS", "duration_seconds": round(time.perf_counter() - started, 4), "details": details})
                print(f"{name}: PASS")
            except Exception as exc:
                results.append({"id": name, "status": "FAIL", "duration_seconds": round(time.perf_counter() - started, 4), "error": f"{type(exc).__name__}: {exc}"})
                print(f"{name}: FAIL - {type(exc).__name__}: {exc}")
                break
    passed = sum(item["status"] == "PASS" for item in results)
    final_classification = classification(passed if not args.only else (len(BENCHMARKS) if passed == 1 else 0))
    print(json.dumps({"results": results, "classification": final_classification}, ensure_ascii=False, indent=2))
    return 0 if len(results) == len(selected) and all(item["status"] == "PASS" for item in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
