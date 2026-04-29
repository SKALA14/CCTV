"""target_event 기반 VLM 프롬프트 로더."""

from __future__ import annotations

from pathlib import Path
from jinja2 import Template
from config import config
from utils.channel_target_event import TargetEvent

PROMPT_FILE_BY_EVENT: dict[TargetEvent, str] = {
    "ppe": "ppe.j2",
    "fall": "fall.j2",
    "intrusion": "intrusion.j2",
    "fire": "fire.j2",
}


def get_prompt_for_event(target_event: TargetEvent, camera_id: str) -> str:
    template_file = PROMPT_FILE_BY_EVENT[target_event]
    template_path = Path(config.PROMPT_DIR) / template_file
    template = Template(template_path.read_text())
    return template.render(camera_id=camera_id)
