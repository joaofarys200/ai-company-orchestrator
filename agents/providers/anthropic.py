import os


class AnthropicProvider:
    name = "claude"

    def has_credentials(self) -> bool:
        return bool(os.getenv("ANTHROPIC_API_KEY"))

    def crewai_model(self) -> str:
        return os.getenv("ANTHROPIC_CREW_MODEL", "anthropic/claude-3-5-sonnet-latest")

    def build_crewai_llm(self, llm_cls, temperature: float):
        return llm_cls(
            model=self.crewai_model(),
            api_key=os.getenv("ANTHROPIC_API_KEY"),
            temperature=temperature,
        )
