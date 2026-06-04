# frontend 서비스

Vue 3 + Vite + Pinia + TailwindCSS 기반 CCTV 모니터링 대시보드.

---

## 실행

```bash
npm install

# 개발 서버 (기본 포트 5173)
npm run dev

# 프로덕션 빌드
npm run build
```

---

## 환경변수

| 변수 | 기본값 | 설명 |
|------|--------|------|
| `VITE_USE_DUMMY` | `true` | `false`로 설정하면 실제 백엔드 API 사용 |
| `VITE_API_BASE_URL` | `/api` | 백엔드 API 베이스 URL |

`.env` 예시:
```
VITE_USE_DUMMY=false
VITE_API_BASE_URL=/api
```

---

## 더미 모드 (DUMMY_MODE, 기본값)

`VITE_USE_DUMMY`가 `false`가 아닌 모든 경우 더미 모드로 동작한다.

| 기능 | 더미 동작 |
|------|----------|
| 대시보드 | 채널 CRUD가 Pinia store in-memory로만 저장. 새로고침 시 초기화 |
| 검색 | `src/constants/dummyData.js`의 DUMMY_EVENTS 3건으로 클라이언트 사이드 검색 |
| 매뉴얼·체크리스트 | `localStorage("cctv_manuals")`에 파일 메타데이터 저장 |
| PDF 분석 | 고정된 더미 응답 반환 |
| 구역 등록 | 더미 구역 목록 반환 |
| 채널 instruction | 더미 체크리스트 초안 반환 |

---

## 화면 구성

### DashboardView
실시간 채널 모니터링. 채널 추가 시 소스 타입(`rtsp` / `webcam` / `file`)을 선택하고 구역을 지정한다.
WebSocket(`/ws`)으로 alerts + events 스트림을 수신해 이벤트 발생 시 전폭 Toast 알림을 표시한다.
동일 채널 + 동일 이벤트 타입은 5분 쿨다운으로 중복 알림을 방지한다.

### SearchView
자연어 시맨틱 이벤트 검색. 채널 필터와 날짜 범위를 조합해 검색할 수 있다.
결과는 인시던트 단위로 묶여 표시되며 발생 건수·마지막 발생 시각을 함께 보여준다.

### ClipDetailView
이벤트 단건 상세. 스냅샷 이미지 슬라이더와 메타데이터(위험도·이벤트 타입·설명·신뢰도)를 표시한다.
이전 검색 결과에서 연관 이벤트 목록도 사이드에 표시한다.

### ManualView
2개 섹션으로 구성:

1. **구역 정보**: CSV/XLSX 파일 업로드 → `POST /manuals/zones` → 구역명 목록 표시
2. **매뉴얼 분석**: PDF 업로드 → `POST /manuals/analyze` → 체크리스트 초안 확인/수정 → 피드백 재생성 가능 → `POST /manuals/confirm` 으로 확정

구역을 먼저 등록하면 PDF 분석 시 구역별 세분화 체크리스트가 자동 생성된다.
채널 등록 시 구역을 지정하면 `POST /channels/{id}/instruction/analyze`로 채널별 추가 지시문을 설정할 수 있다.

---

## 컴포넌트 구조

```
src/
├── views/
│   ├── DashboardView.vue     # 채널 그리드 + 실시간 이벤트
│   ├── SearchView.vue        # 이벤트 검색
│   ├── ClipDetailView.vue    # 이벤트 상세
│   └── ManualView.vue        # 구역·매뉴얼·체크리스트 관리
├── components/
│   ├── layout/
│   │   └── AppNav.vue
│   ├── dashboard/
│   │   ├── ChannelGrid.vue
│   │   ├── ChannelCard.vue
│   │   ├── AddChannelModal.vue
│   │   └── EventToast.vue
│   ├── search/
│   │   ├── SearchBar.vue
│   │   ├── ChannelFilter.vue
│   │   ├── ResultList.vue
│   │   ├── ResultCard.vue
│   │   └── ClipDetail.vue
│   └── manual/
│       ├── ChecklistItem.vue
│       └── ChecklistReview.vue
├── stores/
│   ├── channelStore.js       # 채널 CRUD
│   ├── eventStore.js         # 이벤트 캐시 + 5분 쿨다운 알림 관리
│   └── manualStore.js        # 매뉴얼 파일 메타데이터
├── composables/
│   ├── useWebSocket.js       # /ws 연결 + 재연결
│   ├── useWebRTC.js
│   ├── useChannels.js
│   └── useEvents.js
├── api/
│   ├── index.js              # axios 인스턴스
│   ├── events.js             # GET /events, /events/search, /events/:id
│   ├── channels.js           # GET/POST/PUT/DELETE /channels
│   ├── manuals.js            # 매뉴얼·체크리스트·구역·instruction API
│   └── websocket.js          # WebSocket 연결
└── constants/
    ├── mode.js               # DUMMY_MODE 단일 소스
    ├── dummyData.js
    └── events.js
```

---

## 백엔드 API 연동 목록

| 파일 | 엔드포인트 |
|------|-----------|
| `api/events.js` | `GET /events`, `GET /events/search`, `GET /events/:id` |
| `api/channels.js` | `GET /channels`, `POST /channels`, `PUT /channels/:name`, `DELETE /channels/:name` |
| `api/manuals.js` | `GET/POST/DELETE /manuals`, `POST /manuals/analyze`, `POST /manuals/refine`, `POST /manuals/confirm`, `GET/POST /manuals/zones`, `POST /channels/:id/instruction/analyze`, `PATCH /channels/:id/instruction/confirm` |
| `api/websocket.js` | `WS /ws` |
