# services/inference/vlm/client.py
"""OpenAI Vision API 호출 및 응답 파싱."""

from __future__ import annotations

import base64
import json
import logging
from pathlib import Path

from jinja2 import Template
from openai import OpenAI

from config import config
from redis_client import get_client

logger = logging.getLogger(__name__)

_REFUSAL_PHRASES = ("i'm sorry", "i cannot", "i can't", "i am sorry", "cannot assist", "can't assist")
_VALID_SEVERITIES = frozenset({"critical", "high", "low", "none"})


def _extract_description(data: dict) -> str:
    """최상위 description 우선, 없으면 detections 첫 항목에서 추출."""
    desc = str(data.get("description", "")).strip()
    if desc:
        return desc
    for det in data.get("detections", []):
        d = str(det.get("description", "")).strip()
        if d:
            return d
    return ""


def _encode_image(image_path: str) -> tuple[str, str]:
    """JPEG/PNG/WebP 파일을 base64 문자열과 media_type으로 인코딩."""
    path = Path(image_path)
    media_map = {
        ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
        ".png": "image/png", ".webp": "image/webp",
    }
    media_type = media_map.get(path.suffix.lower(), "image/jpeg")
    data = base64.standard_b64encode(path.read_bytes()).decode("utf-8")
    return data, media_type


class VLMClient:
    """프롬프트 + 이미지 리스트로 VLM 분석을 수행하는 공통 클라이언트."""

    def __init__(self, max_tokens: int = 512, temperature: float = 0.1) -> None:
        if not config.OPENAI_API_KEY:
            raise EnvironmentError("OPENAI_API_KEY 환경변수가 필요합니다.")
        self.model = config.OPENAI_MODEL
        self.max_tokens = max_tokens
        self.temperature = temperature
        self._client = OpenAI(api_key=config.OPENAI_API_KEY)

    def _predict(self, prompt: str, image_paths: list[str]) -> str:
        if not image_paths:
            raise ValueError("image_paths가 비어 있습니다.")

        content: list[dict] = []
        for i, path in enumerate(image_paths):
            image_data, media_type = _encode_image(path)
            content.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:{media_type};base64,{image_data}",
                    "detail": "high" if i == 0 else "low",
                },
            })
        content.append({"type": "text", "text": prompt})

        response = self._client.chat.completions.create(
            model=self.model,
            max_completion_tokens=self.max_tokens,
            messages=[{"role": "user", "content": content}],
        )
        return response.choices[0].message.content.strip()

    def _parse(self, raw_text: str, categories: dict[str, str] | None = None) -> dict:
        """VLM 응답을 표준 dict로 파싱. 실패 시 normal fallback.

        categories: {"1": "SAFETY_BARRIERS", ...} — violated_index → anomaly_type 조회용.
        danger_level은 VLM이 출력한 detections[].severity에서 직접 읽음 (체크리스트에서 복사).
        """
        normal = {
            "result": "normal",
            "anomaly_type": "normal",
            "danger_level": "none",
            "description": "",
        }

        if raw_text.find("{") == -1:
            lower = raw_text.lower()
            if any(p in lower for p in _REFUSAL_PHRASES):
                logger.warning("VLM 콘텐츠 정책 거부: %.100s", raw_text)
            else:
                logger.warning("VLM 응답에 JSON 없음: %.200s", raw_text)
            return normal

        try:
            start = raw_text.find("{")
            end = raw_text.rfind("}") + 1
            data = json.loads(raw_text[start:end])
        except json.JSONDecodeError as e:
            logger.warning("VLM JSON 파싱 실패: %s | %.200s", e, raw_text)
            return normal

        try:
            result = str(data.get("result", "normal"))

            if result not in ("anomaly", "unverifiable"):
                return {
                    "result": "normal",
                    "anomaly_type": "normal",
                    "danger_level": "none",
                    "description": _extract_description(data),
                }

            if result == "unverifiable":
                return {
                    "result": "unverifiable",
                    "anomaly_type": "normal",
                    "danger_level": "none",
                    "description": _extract_description(data),
                }

            # violated_index + severity: 위반 detection에서 직접 추출
            violated_det = next(
                (d for d in data.get("detections", [])
                 if str(d.get("violated_index") or "").strip() not in ("", "null")),
                {},
            )
            violated_index = str(violated_det.get("violated_index") or "").strip()
            raw_sev = str(violated_det.get("severity", "low"))
            danger_level = raw_sev if raw_sev in _VALID_SEVERITIES else "low"
            anomaly_type = categories.get(violated_index, "GENERAL") if (categories and violated_index) else "GENERAL"

            return {
                "result": "anomaly",
                "anomaly_type": anomaly_type,
                "danger_level": danger_level,
                "description": _extract_description(data),
            }
        except (ValueError, TypeError) as e:
            logger.warning("VLM 값 변환 실패: %s | data: %s", e, data)
            return normal

    def analyze(self, frame_paths: list[str], prompt: str, categories: dict[str, str] | None = None) -> dict:
        """이미지 리스트와 prompt로 VLM 분석 수행. 결과 dict 반환."""
        if not frame_paths:
            return {
                "result": "normal",
                "anomaly_type": "normal",
                "danger_level": "none",
                "description": "",
            }
        raw = self._predict(prompt, frame_paths)
        logger.debug("VLM raw: %s", raw[:200])
        return self._parse(raw, categories)


_template_cache: dict[str, Template] = {}


def _get_template(filename: str) -> Template:
    """Jinja2 Template을 파일별로 1회 로드 후 캐싱."""
    if filename not in _template_cache:
        text = (Path(config.PROMPT_DIR) / filename).read_text(encoding="utf-8")
        _template_cache[filename] = Template(text)
    return _template_cache[filename]


def _split_cam_key(camera_id: str) -> tuple[str, str]:
    """compound cam_key '{site_id}:{cam_id}'를 (site_id, cam_id)로 분리.
    콜론 없으면 ('', camera_id) — 레거시 글로벌 경로 fallback.
    """
    if ":" in camera_id:
        site_id, cam_id = camera_id.split(":", 1)
        return site_id, cam_id
    return "", camera_id


def _load_zone_meta(camera_id: str, zone: str) -> tuple[str, str]:
    """CHECKLIST_DIR/{site_id}/zones.json에서 zone의 description과 note 반환."""
    site_id, _ = _split_cam_key(camera_id)
    if not (site_id and zone):
        return "", ""
    zones_path = Path(config.CHECKLIST_DIR) / site_id / "zones.json"
    if not zones_path.exists():
        return "", ""
    try:
        data = json.loads(zones_path.read_text(encoding="utf-8"))
        for z in data:
            if isinstance(z, dict) and z.get("zone") == zone:
                return z.get("description", ""), z.get("note", "")
    except Exception as e:
        logger.warning("zones.json 읽기 실패 (camera=%s): %s", camera_id, e)
    return "", ""


def _load_checklist(track: str, camera_id: str = "") -> str:
    """체크리스트 파일을 매번 디스크에서 읽어 반환 (현장별).
    camera_id는 compound '{site_id}:{cam_id}'. site_id가 있으면 CHECKLIST_DIR/{site_id}/ 하위.
    구역(zone) 있으면 구역별 파일 우선, 없으면 글로벌 체크리스트 fallback.
    """
    site_id, _ = _split_cam_key(camera_id)
    base = Path(config.CHECKLIST_DIR)
    if site_id:
        base = base / site_id
    if camera_id:
        zone = get_client().get(f"camera:{camera_id}:zone") or ""
        if zone:
            safe = zone.replace(" ", "_")
            for ext in (".json", ".md"):
                zone_path = base / f"zone_{safe}_{track}{ext}"
                if zone_path.exists():
                    return zone_path.read_text(encoding="utf-8")
    for ext in (".json", ".md"):
        path = base / f"{track}_checklist{ext}"
        if path.exists():
            return path.read_text(encoding="utf-8")
    logger.warning("체크리스트 파일 없음: %s", base / f"{track}_checklist.json")
    return ""


def _get_categories_key(track: str, camera_id: str) -> str:
    """카메라의 site/구역을 조회해 적절한 Redis 카테고리 키 반환.

    site 있고 구역 있으면: checklist:{site_id}:zone_{safe}:{track}:categories
    site 있고 구역 없으면: checklist:{site_id}:{track}:categories
    site 없으면(레거시): checklist:{track}:categories
    """
    site_id, _ = _split_cam_key(camera_id)
    prefix = f"checklist:{site_id}:" if site_id else "checklist:"
    zone = get_client().get(f"camera:{camera_id}:zone") or ""
    if zone:
        safe = zone.replace(" ", "_")
        return f"{prefix}zone_{safe}:{track}:categories"
    return f"{prefix}{track}:categories"


def render_prompt(filename: str, camera_id: str) -> tuple[str, dict[str, str]]:
    """camera_id, Redis camera_instruction, 체크리스트를 주입해 프롬프트 렌더링.

    반환: (rendered_prompt, categories_dict)
    categories_dict: {"1": "SAFETY_BARRIERS", ...} — violated_index → anomaly_type
    danger_level은 VLM이 체크리스트에서 읽은 severity를 detections에 출력 → _parse()가 직접 사용.
    """
    track = filename.split("_", 1)[0]  # "dynamic_prompt.j2" → "dynamic"
    zone = get_client().get(f"camera:{camera_id}:zone") or ""
    description, note = _load_zone_meta(camera_id, zone)
    checklist = _load_checklist(track, camera_id)

    categories_key = _get_categories_key(track, camera_id)
    try:
        categories: dict[str, str] = get_client().hgetall(categories_key) or {}
    except Exception as e:
        logger.warning("categories 조회 실패 (camera=%s): %s", camera_id, e)
        categories = {}

    prompt = _get_template(filename).render(
        camera_id=camera_id,
        zone=zone,
        description=description,
        note=note,
        checklist=checklist,
    )
    return prompt, categories
