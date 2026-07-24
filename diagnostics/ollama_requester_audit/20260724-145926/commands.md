# Audit Commands

All commands ran on system/full-health-audit and outside MissionState.

    venv/Scripts/python.exe -m py_compile diagnostics/ollama_requester_audit/20260724-145926/probe_ollama_stream.py
    venv/Scripts/python.exe probe_ollama_stream.py environment
    venv/Scripts/python.exe probe_ollama_stream.py capture
    venv/Scripts/python.exe probe_ollama_stream.py warmup
    venv/Scripts/python.exe probe_ollama_stream.py test --name A1
    venv/Scripts/python.exe probe_ollama_stream.py test --name A2
    venv/Scripts/python.exe probe_ollama_stream.py test --name B1
    venv/Scripts/python.exe probe_ollama_stream.py test --name B2
    venv/Scripts/python.exe probe_ollama_stream.py test --name C1
    venv/Scripts/python.exe probe_ollama_stream.py test --name C-focal
    venv/Scripts/python.exe probe_ollama_stream.py test --name D
    venv/Scripts/python.exe probe_ollama_stream.py requester
    venv/Scripts/python.exe probe_ollama_stream.py cold-reset
    ollama ps
    venv/Scripts/python.exe probe_ollama_stream.py test --name D-cold
    venv/Scripts/python.exe probe_ollama_stream.py environment --suffix after

Exit codes:

- all diagnostic script commands: 0;
- A1/A2/B1/B2/C-focal/D/D-cold: HTTP 200 and useful termination;
- C1: script exit 0 with recorded HTTP 400 because the probe records the
  expected negative result rather than converting it into a process failure;
- ollama ps after cold-reset: 0 and no loaded model;
- environment CIM memory and TCP connection subcommands: access denied/exit 1,
  preserved in the environment JSON instead of hidden.

Raw streams, event timelines, payloads and metrics are stored under tests,
payloads and resources in this directory.
