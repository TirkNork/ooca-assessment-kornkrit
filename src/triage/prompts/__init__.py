"""Prompt templates, stored as Markdown next to this module.

`PROMPT_VERSION` is reported in run metadata so results can be traced to the prompts that
produced them; bump it whenever a prompt changes.
"""

from functools import cache
from importlib.resources import files

PROMPT_VERSION = "4"


@cache
def load_prompt(name: str) -> str:
    return files(__package__).joinpath(f"{name}.md").read_text(encoding="utf-8")
