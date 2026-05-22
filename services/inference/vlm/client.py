# services/inference/vlm/client.py
"""OpenAI Vision API 호출 및 응답 파싱."""

from __future__ import annotations

import base64
import json
import logging
from pathlib import Path

from openai import OpenAI

from config import config

logger = logging.getLogger(__name__)

_VALID_LEVELS = {"critical", "none"}
_REFUSAL_PHRASES = ("i'm sorry", "i cannot", "i can't", "i am sorry", "cannot assist", "can't assist")


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
            max_tokens=self.max_tokens,
            temperature=self.temperature,
            messages=[{"role": "user", "content": content}],
        )
        return response.choices[0].message.content.strip()

    def _parse(self, raw_text: str) -> dict:
        """VLM 응답을 표준 dict로 파싱. 실패 시 normal fallback."""
        normal = {
            "result": "normal",
            "anomaly_type": "normal",
            "danger_level": "none",
            "description": "",
            "confidence": 0.0,
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
            level = data.get("danger_level", "none")
            anomaly_type = str(data.get("anomaly_type", "normal"))
            return {
                "result": result if result in ("normal", "anomaly") else "normal",
                "anomaly_type": anomaly_type,
                "danger_level": level if level in _VALID_LEVELS else "none",
                "description": str(data.get("description", "")),
                "confidence": float(max(0.0, min(1.0, data.get("confidence", 0.5)))),
            }
        except (ValueError, TypeError) as e:
            logger.warning("VLM 값 변환 실패: %s | data: %s", e, data)
            return normal

    def analyze(self, frame_paths: list[str], prompt: str) -> dict:
        """이미지 리스트와 prompt로 VLM 분석 수행. 결과 dict 반환."""
        if not frame_paths:
            return {
                "result": "normal",
                "anomaly_type": "normal",
                "danger_level": "none",
                "description": "",
                "confidence": 0.0,
            }
        raw = self._predict(prompt, frame_paths)
        logger.debug("VLM raw: %s", raw[:200])
        return self._parse(raw)


def load_prompt(filename: str) -> str:
    """prompts 디렉토리에서 텍스트 프롬프트 1회 로드."""
    return (Path(config.PROMPT_DIR) / filename).read_text(encoding="utf-8")
