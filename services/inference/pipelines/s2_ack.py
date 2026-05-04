'''
Redis Stream 처리 완료(XACK)와 프레임 삭제 후보 등록을 담당한다.

입력
- group: Redis consumer group 이름. 현재는 config.UNIFIED_GROUP.
- msg_id: Redis frames stream 메시지 ID.
- frame_path: ingestion이 저장한 JPEG 파일 경로.
- frames: VLMJob 내부 프레임 목록 [(msg_id, frame_path, timestamp), ...].

출력/부수효과
- Redis XACK으로 해당 frames 메시지를 처리 완료 상태로 표시한다.
- mark_processed(frame_path)로 delete_queue에 프레임 삭제 작업을 등록한다.
'''

from config import config
from redis_client import mark_processed, xack


def ack_frame(group: str, msg_id: str, frame_path: str) -> None:
    xack(config.FRAMES_STREAM, group, msg_id)
    mark_processed(frame_path)


def ack_all(group: str, frames: list[tuple[str, str, str]]) -> None:
    for msg_id, frame_path, _ in frames:
        ack_frame(group, msg_id, frame_path)
