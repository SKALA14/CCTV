# inference 서비스 진입점.
# FrameConsumer로 Redis frames 채널을 구독하고,
# 프레임마다 vlm.analyze()를 호출한 뒤 EventPublisher로 결과를 발행하는 루프를 실행한다.
