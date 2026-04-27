# GPT-4o Vision API를 호출해 프레임 묶음을 분석하는 래퍼를 정의한다.
# 정의: analyze(frame_paths, camera_id) — Jinja2 프롬프트 렌더링 후 OpenAI API 호출.
# 입력: frame_paths: list[str] (JPEG 절대경로들), camera_id: str.
# 출력: dict — {"description": str, "is_anomaly": bool}.
