import os
import sqlite3
import psutil
from datetime import datetime

class RuntimeObserver:
    def __init__(self, db_path="database.db"):
        self.db_path = db_path

    def get_system_telemetry(self):
        try:
            process = psutil.Process(os.getpid())
            mem_info = process.memory_info()
            cpu = process.cpu_percent(interval=0.1)
            mem_mb = round(mem_info.rss / (1024 * 1024), 2)
        except Exception:
            cpu = 0.0
            mem_mb = 0.0
            
        from datetime import timezone
        return {
            "backend_online": True,
            "memory_usage_mb": mem_mb,
            "cpu_percent": cpu,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
    def get_db_metrics(self):
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Conta sessões totais
            cursor.execute("SELECT COUNT(*) FROM sessions")
            total_sessions = cursor.fetchone()[0]
            
            # Conta eventos no historico
            cursor.execute("SELECT COUNT(*) FROM event_sourcing_log")
            total_events = cursor.fetchone()[0]
            
            conn.close()
            return {
                "sqlite_online": True,
                "total_sessions": total_sessions,
                "total_events_in_log": total_events
            }
        except Exception as e:
            return {"sqlite_online": False, "error": str(e)}

    def compile_runtime_state(self, websocket_connected=False, active_agents=0, frontend_connected=False):
        """
        Compila o 'Runtime Awareness' que será injetado no contexto dos LLMs
        para que saibam exatamente o que se passa na máquina.
        """
        telemetry = self.get_system_telemetry()
        db_metrics = self.get_db_metrics()
        
        state = {
            "runtime_awareness": {
                "status": "ONLINE",
                "infrastructure": telemetry,
                "database": db_metrics,
                "orchestrator_state": {
                    "frontend_connected": frontend_connected,
                    "websocket_connected": websocket_connected,
                    "active_agent_count": active_agents
                }
            }
        }
        return state

if __name__ == "__main__":
    observer = RuntimeObserver()
    print("Teste de Runtime Observer:")
    import json
    print(json.dumps(observer.compile_runtime_state(websocket_connected=True, active_agents=2, frontend_connected=True), indent=2))
