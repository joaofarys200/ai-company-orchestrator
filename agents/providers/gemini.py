import os


class GeminiProvider:
    name = "gemini"

    def has_credentials(self) -> bool:
        return bool(os.getenv("GEMINI_API_KEY"))

    def crewai_model(self) -> str:
        return os.getenv("GEMINI_CREW_MODEL", "gemini/gemini-2.5-flash")

    def build_crewai_llm(self, llm_cls, temperature: float):
        return llm_cls(
            model=self.crewai_model(),
            api_key=os.getenv("GEMINI_API_KEY"),
            temperature=temperature,
        )
