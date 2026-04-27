# 세 개의 독립 프로세스를 띄워 서비스를 시작하는 진입점.
# 정의: main() — multiprocessing.Process로 emergency·general·cleaner를 각각 실행.
# 입력: 없음 (각 프로세스가 Redis에서 직접 읽음).
# 출력: 없음 (프로세스들이 종료될 때까지 블로킹).
