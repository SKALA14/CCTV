// 이벤트 유형 목록 (VLM 탐지 대상)
export const GENERAL_OPTIONS = [
    '쓰러짐 / 추락',
    '화재 / 연기',
    '침입',
    '폭행',
    '안전복장 미착용',
    '침수',
]

// 위험도 레벨
export const DANGER_LEVELS = {
    HIGH: 'high',
    MEDIUM: 'medium',
    LOW: 'low',
}

// 신뢰도 임계값 — 이 값 미만이면 알람 발송 제외
export const CONFIDENCE_THRESHOLD = 0.7

// WebSocket 이벤트 타입
export const WS_EVENT_TYPES = {
    NEW_EVENT: 'new_event',
}

// 채널 상태
export const CHANNEL_STATUS = {
    OK: 'ok',
    ALERT: 'alert',
    ERROR: 'error',
}

// 토스트 자동 닫힘 시간 (ms)
export const TOAST_DURATION = 5000

// 클립 전후 구간 (초)
export const CLIP_PADDING_SEC = 10

// 채널 최대 등록 수
export const MAX_CHANNELS = 4