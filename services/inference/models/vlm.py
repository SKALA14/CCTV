"""
VLM 모델 모듈.

단일 책임: OpenAI Vision API 호출(_predict) + 응답 파싱(_parse).
직렬화·프롬프트 조립·RAG는 이 파일에 포함하지 않는다.

Public API:
    analyze(frame_paths, target_event, prompt) -> dict
"""
from __future__ import annotations

import base64
import json
import logging
import os
from pathlib import Path
from typing import Optional

from openai import OpenAI

from config import config

logger = logging.getLogger(__name__)

_VALID_LEVELS      = {"high", "medium", "low", "none"}
_VALID_EVENT_TYPES = {"fall", "fire", "intrusion", "ppe", "normal"}


def _encode_image(image_path: str) -> tuple[str, str]:
    """이미지 파일 → (base64 문자열, media_type)."""
    path = Path(image_path)
    media_map = {
        ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
        ".png": "image/png",  ".webp": "image/webp",
    }
    media_type = media_map.get(path.suffix.lower(), "image/jpeg")
    data = base64.standard_b64encode(path.read_bytes()).decode("utf-8")
    return data, media_type


class VLMClient:
    """OpenAI Vision API 래퍼. 단일 책임: analyze()."""

    def __init__(self, max_tokens: int = 512, temperature: float = 0.1):
        """config.py의 OPENAI_MODEL을 기본 모델로 설정하고 클라이언트를 미초기화 상태로 생성."""
        self.model       = config.OPENAI_MODEL
        self.max_tokens  = max_tokens
        self.temperature = temperature
        self._client: OpenAI | None = None

    def load(self) -> "VLMClient":
        """OpenAI 클라이언트 초기화. 체이닝 가능."""
        api_key = config.OPENAI_API_KEY or os.getenv("OPENAI_API_KEY", "")
        if not api_key:
            raise EnvironmentError("OPENAI_API_KEY 환경변수가 필요합니다.")
        self._client = OpenAI(api_key=api_key)
        return self

    def unload(self) -> None:
        """OpenAI 클라이언트 참조 해제."""
        self._client = None

    def _predict(self, prompt: str, image_paths: list[str]) -> str:
        """이미지 목록 + 프롬프트 → OpenAI API 단일 호출 → 원문 텍스트 반환."""
        if self._client is None:
            raise RuntimeError("load()를 먼저 호출하세요.")
        if not image_paths:
            raise ValueError("image_paths가 비어 있습니다.")

        content: list[dict] = []
        for i, path in enumerate(image_paths):
            image_data, media_type = _encode_image(path)
            content.append({
                "type": "image_url",
                "image_url": {
                    "url":    f"data:{media_type};base64,{image_data}",
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
        """VLM 응답 JSON → 결과 dict. 파싱 실패 시 보수적 폴백."""
        try:
            start = raw_text.find("{")
            end   = raw_text.rfind("}") + 1
            data  = json.loads(raw_text[start:end])

            level = data.get("danger_level", "none")
            etype = data.get("event_type", "normal")

            return {
                "description":  str(data.get("reason", "")),
                "is_anomaly":   bool(data.get("is_danger", False)),
                "danger_level": level if level in _VALID_LEVELS      else "none",
                "event_type":   etype if etype in _VALID_EVENT_TYPES else "normal",
                "confidence":   float(max(0.0, min(1.0, data.get("confidence", 0.5)))),
            }

        except Exception:
            # 파싱 완전 실패 → 알림 누락 방지를 위해 is_anomaly=True 보수적 처리
            logger.warning("VLM 응답 파싱 실패, 보수적 폴백 적용")
            return {
                "description":  raw_text[:300],
                "is_anomaly":   True,
                "danger_level": "medium",
                "event_type":   "normal",
                "confidence":   0.3,
            }

    def analyze(self, frame_paths: list[str], prompt: str) -> dict:
        """
        general_pipeline 진입점.

        Args:
            frame_paths : JPEG 프레임 경로 목록 (general.py buffer에서 추출)
            prompt      : get_prompt_for_event()로 조립된 프롬프트 문자열

        Returns:
            {"description": str, "is_anomaly": bool,
             "danger_level": str, "event_type": str, "confidence": float}
        """
        if not frame_paths:
            return {
                "description":  "",
                "is_anomaly":   False,
                "danger_level": "none",
                "event_type":   "normal",
                "confidence":   0.0,
            }

        raw = self._predict(prompt, frame_paths)
        logger.debug("VLM raw: %s", raw[:200])
        return self._parse(raw)


_instance: Optional[VLMClient] = None


def _get_client() -> VLMClient:
    """최초 호출 시에만 초기화하는 지연 싱글턴."""
    global _instance
    if _instance is None:
        _instance = VLMClient()
        _instance.load()
    return _instance


def analyze(frame_paths: list[str], prompt: str) -> dict:
    """general.py의 vlm.analyze() 호출을 받는 모듈 레벨 진입점."""
    return _get_client().analyze(frame_paths, prompt)
