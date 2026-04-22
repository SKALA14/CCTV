# WebSocket 엔드포인트.
# WS /ws/events : Redis events 스트림을 실시간으로 클라이언트에 푸시한다.
# 연결 시점 이후의 신규 메시지만 전달하며, 연결 유지를 위해 주기적으로 ping을 보낸다.
