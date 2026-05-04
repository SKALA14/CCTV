### docker-compose.override.yaml
services:
  ingestion:
    volumes:
      - ./../frames:/frames
  inference:
    volumes:
      - ./../frames:/frames

로컬에서 프레임 저장을 확인하기 위한 용도

ANNOTATE_FRAMES: 태그를 확인하기 위한 용도

이 파일은 배포 시엔 .gitignore에 올라갑니다

지금은 ingestion 쪽에서 file source로 받아오고 있는데, 실시간 카메라 연결하면 뺄거에요
