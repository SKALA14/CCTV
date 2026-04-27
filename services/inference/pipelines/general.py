# "general" Consumer Group으로 프레임을 읽어 버퍼링 후 VLM 분석 결과를 발행하는 프로세스.
# 정의: run() — XREADGROUP 루프, 프레임을 deque에 누적, VLM_BUFFER_SIZE 도달 시 vlm.analyze 호출.
# 입력: Redis Stream "frames" 메시지 — {frame_path, camera_id, timestamp}.
# 출력: "events" 스트림에 XADD — {camera_id, description, is_anomaly, timestamp}; XACK 후 mark_processed 호출.
