# 11. TEST AND EVIDENCE REGISTER

**Status:** IMPLEMENTED | INTEGRATED | UNIT_TESTED | INTEGRATION_TESTED | REAL_QWEN_TESTED | INDEPENDENTLY_VALIDATED  
**Data:** 2026-11-05  

---

## 11.1 Resultados Consolidados da Suite de Testes

Executados 67 testes através do ambiente `pytest` oficial com o ambiente virtual `venv`:
```
tests/test_obsidian_knowledge_hardening.py ................... [19/19 PASSED]
tests/test_obsidian_graph_engine.py ......                     [6/6 PASSED]
tests/test_websocket_dispatcher_contract.py .........          [9/9 PASSED]
tests/test_server_websocket_characterization.py ........       [8/8 PASSED]
tests/test_study_engine_forensic_qa.py ......................... [25/25 PASSED]

TOTAL: 67 PASSED (0 FAILED, 0 SKIPPED) em 88.81s
```

---

## 11.2 Investigação dos Dois Avisos (Warnings)

Os dois avisos observados na suite foram categorizados e esclarecidos:
1. `backend/startup.py:8: DeprecationWarning: 'asyncio.DefaultEventLoopPolicy' is deprecated and slated for removal in Python 3.16`
2. `backend/startup.py:30: DeprecationWarning: 'asyncio.set_event_loop_policy' is deprecated and slated for removal in Python 3.16`

**Conclusão:** Os avisos provêm unicamente da política de event loop do Python 3.14 no backend web, sem qualquer relação com o motor PyMuPDF (o qual utiliza a API moderna `import pymupdf` com zero avisos).
