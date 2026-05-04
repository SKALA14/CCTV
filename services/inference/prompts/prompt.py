"""target_event 기반 VLM 프롬프트 로더."""

from __future__ import annotations

from pathlib import Path
from jinja2 import Template
from config import config
from redis_client import get_client


def get_prompt(camera_id: str) -> str:
    base = (Path(config.PROMPT_DIR) / "base.j2").read_text()
    instruction = get_client().get(f"camera_instruction:{camera_id}") or ""
    return Template(base).render(camera_id=camera_id, instruction=instruction)