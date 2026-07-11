import os
import chromadb
from intelligence.project_intelligence import ProjectIntelligenceEngine

class SemanticCodeIndex:
    def __init__(self, workspace_root: str = ".", db_path: str | None = None, collection_name: str = "codebase_index"):
        self.workspace_root = os.path.realpath(os.path.abspath(workspace_root))
        self.db_path = db_path or os.path.join(self.workspace_root, "chroma_db")
        os.makedirs(self.db_path, exist_ok=True)
        # ChromaDB setup
        self.client = chromadb.PersistentClient(path=self.db_path)
        # Using default embedding model: sentence-transformers/all-MiniLM-L6-v2
        self.collection = self.client.get_or_create_collection(name=collection_name)

    def build_index(self, graph=None):
        print("[Semantic Index] A extrair a AST do workspace...")
        if graph is None:
            engine = ProjectIntelligenceEngine(self.workspace_root)
            graph = engine.scan_workspace()
        
        docs = []
        metadatas = []
        ids = []
        
        for filepath, data in graph.items():
            items = data.get("classes", []) + data.get("functions", [])
            for item in items:
                if "code" in item and item["code"].strip():
                    snippet = item["code"]
                    # Prefixing filepath so the model understands context inside the snippet
                    rich_snippet = f"// File: {filepath}\n// Symbol: {item['name']}\n{snippet}"
                    
                    node_id = f"{filepath}::{item['name']}::{item.get('line', 0)}"
                    docs.append(rich_snippet)
                    metadatas.append({
                        "filepath": filepath,
                        "name": item["name"],
                        "line": item.get("line", 0)
                    })
                    ids.append(node_id)
                    
        existing_ids = self.collection.get(include=[]).get("ids", [])
        if existing_ids:
            self.collection.delete(ids=existing_ids)

        if docs:
            print(f"[Semantic Index] A vetorizar e guardar {len(docs)} fragmentos de código no ChromaDB...")
            # We index in batches of 5000 to avoid sqlite limits
            batch_size = 5000
            for i in range(0, len(docs), batch_size):
                self.collection.upsert(
                    documents=docs[i:i+batch_size],
                    metadatas=metadatas[i:i+batch_size],
                    ids=ids[i:i+batch_size]
                )
            print("[Semantic Index] Concluído!")
        else:
            print("[Semantic Index] Nenhum código encontrado para indexar.")

    def search(self, query: str, n_results: int = 5) -> str:
        results = self.collection.query(
            query_texts=[query],
            n_results=n_results
        )
        
        if not results['documents'] or not results['documents'][0]:
            return "Nenhum resultado semântico encontrado."
            
        output = f"Resultados da pesquisa semântica para: '{query}'\n\n"
        
        docs = results['documents'][0]
        metas = results['metadatas'][0]
        distances = results['distances'][0] if 'distances' in results and results['distances'] else []
        
        for i in range(len(docs)):
            dist = distances[i] if i < len(distances) else "N/A"
            meta = metas[i]
            output += f"--- {meta['filepath']} (Linha {meta['line']}) [Distância: {dist}] ---\n"
            output += f"{docs[i]}\n\n"
            
        return output

if __name__ == "__main__":
    # Teste de Inicialização Local
    index = SemanticCodeIndex()
    index.build_index()
    print("Teste de pesquisa: 'onde é que as métricas são gravadas?'")
    res = index.search("onde é que as métricas são gravadas?")
    print(res)
