# hooks/

재사용 가능한 React 커스텀 훅.

- `useWebSocket.ts` — `/ws/events` WebSocket 연결 + 자동 재연결 훅. 수신 메시지를 파싱해 반환.
- `useEvents.ts` — REST API로 이벤트 목록을 페칭하는 훅 (페이지네이션, 필터 파라미터 포함)
