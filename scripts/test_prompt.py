#!/usr/bin/env python3
"""렌더링된 프롬프트를 출력하는 일회성 확인 스크립트."""

import os
import sys
from pathlib import Path

# 호스트에서 실행 시 Redis 접속 경로 + 프로젝트 prompts 경로
os.environ.setdefault("REDIS_URL", "redis://localhost:6379")
os.environ.setdefault("PROMPT_DIR", str(Path(__file__).parent.parent / "services" / "inference" / "prompts"))
os.environ.setdefault("CHECKLIST_DIR", str(Path(__file__).parent.parent / "prompts"))
os.environ.setdefault("OPENAI_API_KEY", "dummy")  # render_prompt만 쓰니까 더미 OK

sys.path.insert(0, str(Path(__file__).parent.parent / "services" / "inference"))

from vlm.client import render_prompt  # noqa: E402

camera_id = sys.argv[1] if len(sys.argv) > 1 else "cam0"
which = sys.argv[2] if len(sys.argv) > 2 else "dynamic"

print(f"--- {which}_prompt.j2 / camera_id={camera_id} ---\n")
print(render_prompt(f"{which}_prompt.j2", camera_id))
