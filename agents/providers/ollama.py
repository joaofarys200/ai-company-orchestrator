import os


class OllamaProvider:
    name = "ollama"

    def has_credentials(self) -> bool:
        return True

    def crewai_model(self) -> str:
        return f"ollama/{os.getenv('OLLAMA_MODEL', 'qwen2.5:14b')}"

    def build_crewai_llm(self, llm_cls, temperature: float):
        return llm_cls(
            model=self.crewai_model(),
            base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
            temperature=temperature,
        )
