# "emergency" Consumer Group으로 프레임을 읽어 YOLO 추론 후 즉시 알람을 발행하는 프로세스.
# 정의: run() — XREADGROUP 루프, YOLOModel.predict 호출, 긴급 클래스 탐지 시 XADD(alerts).
# 입력: Redis Stream "frames" 메시지 — {frame_path, camera_id, timestamp}.
# 출력: 긴급 상황 시 "alerts" 스트림에 XADD; 항상 XACK 후 mark_processed 호출.
