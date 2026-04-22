# 프레임 소비자 모듈.
# 로컬 영상 저장소(mp4 파일)에서 프레임을 읽어 inference 파이프라인에 전달한다.
# OpenCV로 영상을 열고, config의 SAMPLE_FPS 간격마다 프레임을 추출해 yield한다.
# 추후 Redis Streams 소비자로 교체하거나 병렬 실행할 수 있도록 인터페이스를 분리한다.
