# Redis Streams events 채널 구독 → PostgreSQL INSERT 백그라운드 워커.
# Consumer Group 방식으로 수신하며, main.py의 lifespan에서 asyncio 태스크로 실행된다.
