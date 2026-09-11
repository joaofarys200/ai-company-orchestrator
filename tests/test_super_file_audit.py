"""
JARVIS OS — Test Suite: Super-File Auditor & Multi-Dimensional Scoring (Fase 38)
"""

import os
import pytest
from intelligence.super_file_audit import (
    SuperFileAuditor,
    SeverityLevel,
    DecompositionRisk,
    SuperFileReport,
)


@pytest.fixture
def auditor():
    return SuperFileAuditor()


def test_auditor_initialization(auditor):
    assert auditor.workspace_root is not None
    assert auditor.repo_graph is not None
    assert len(auditor.WEIGHTS) == 10
    assert sum(auditor.WEIGHTS.values()) == pytest.approx(1.0, 0.001)


def test_score_calculation_boundaries(auditor):
    # Test normal score
    score, breakdown = auditor._calculate_score(
        loc=100,
        classes=1,
        functions=3,
        responsibilities=1,
        fan_out=2,
        fan_in=1,
        shared_state=1,
        complexity=5,
        public_symbols=2,
        domains=1,
    )
    assert score < 40.0
    assert auditor._classify_severity(score) == SeverityLevel.NORMAL

    # Test critical score
    score_crit, breakdown_crit = auditor._calculate_score(
        loc=3000,
        classes=20,
        functions=60,
        responsibilities=10,
        fan_out=35,
        fan_in=25,
        shared_state=15,
        complexity=100,
        public_symbols=30,
        domains=6,
    )
    assert score_crit >= 80.0
    assert auditor._classify_severity(score_crit) == SeverityLevel.CRITICAL


def test_severity_classification_levels(auditor):
    assert auditor._classify_severity(25.0) == SeverityLevel.NORMAL
    assert auditor._classify_severity(45.0) == SeverityLevel.WATCH
    assert auditor._classify_severity(70.0) == SeverityLevel.HIGH
    assert auditor._classify_severity(88.0) == SeverityLevel.CRITICAL


def test_responsibility_detection_python(auditor):
    py_code = """
import sqlite3
from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()

class TaskModel(BaseModel):
    title: str

@router.get("/tasks")
def get_tasks():
    conn = sqlite3.connect(":memory:")
    return {"status": "ok"}
"""
    cls_cnt, fn_cnt, pub_sym, state_cnt, cpx, resp = auditor._analyze_python(py_code, "api/test_route.py")
    resp_names = [r.name for r in resp]
    assert "api_endpoints" in resp_names
    assert "database_access" in resp_names
    assert "data_validation" in resp_names
    assert cpx["cyclomatic_complexity"] >= 1


def test_responsibility_detection_typescript(auditor):
    ts_code = """
import React, { useState } from 'react';

export const TaskWidget: React.FC = () => {
    const [tasks, setTasks] = useState([]);
    const [activeTab, setActiveTab] = useState('overview');

    const handlePause = () => {};

    return (
        <div id="task-card">
            <h1>Task Widget</h1>
        </div>
    );
};
"""
    cls_cnt, fn_cnt, pub_sym, state_cnt, cpx, resp = auditor._analyze_typescript(ts_code, "components/TaskWidget.tsx")
    resp_names = [r.name for r in resp]
    assert "ui_rendering" in resp_names
    assert "state_management" in resp_names
    assert "navigation_and_tabs" in resp_names
    assert "task_dag_visualization" in resp_names
    assert "mission_control_actions" in resp_names


def test_audit_execution_on_workspace(auditor):
    report = auditor.run_audit()
    assert "audit_metadata" in report
    assert "top_candidates" in report
    assert report["audit_metadata"]["files_scanned"] > 50
    assert len(report["top_candidates"]) <= 20
    assert report["audit_metadata"]["duration_seconds"] > 0
