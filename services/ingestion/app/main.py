# ingestion 서비스 진입점.
# config에서 SOURCE_TYPE을 읽어 적절한 FrameSource를 선택하고,
# FpsSampler → FramePublisher 루프를 실행한다.
