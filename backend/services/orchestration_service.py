def clean_prompt_for_command_matching(prompt: str) -> str:
    return prompt.lower().strip(" .?!,")
