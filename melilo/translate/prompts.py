"""Prompt templates used by the translator. Bump PROMPT_VERSION when these change."""

SYSTEM_PROMPT = (
    "You translate legal text into plain English for a non-lawyer reader. "
    "Preserve every obligation, right, condition, and exception from the source. "
    "Do not add legal advice, opinions, or facts that are not in the source. "
    "If a term has a specific legal meaning, restate it in everyday words and, "
    "when useful, keep the original term in parentheses. Use short sentences."
)

USER_TEMPLATE = """Rewrite the following legal text in plain English.

LEGAL TEXT:
{source_text}

PLAIN ENGLISH:"""


def build_messages(source_text: str) -> list[dict]:
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": USER_TEMPLATE.format(source_text=source_text)},
    ]
