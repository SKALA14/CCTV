# 프레임을 로컬 볼륨(FRAME_STORAGE_PATH)에 JPEG으로 저장하고,
# 저장된 경로(path)만 Redis Streams frames 채널에 발행한다.
# 프레임 바이너리를 Redis에 직접 넣지 않아 메모리 사용을 최소화한다.
