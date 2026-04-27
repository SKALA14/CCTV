# AI CCTV Frontend

Vue 3 + Vite + Pinia + Tailwind CSS 기반 CCTV 모니터링 대시보드.

---

## 실행 방법

```bash
# 의존성 설치
npm install

# 개발 서버 (기본 포트 5173)
npm run dev

# 프로덕션 빌드
npm run build
```

---

## 환경변수

| 변수 | 기본값 | 설명 |
|---|---|---|
| `VITE_USE_DUMMY` | `true` | `false`로 설정하면 실제 백엔드 API 사용 |
| `VITE_API_BASE_URL` | `/api` | 백엔드 API 베이스 URL |

`.env` 파일 예시:
```
VITE_USE_DUMMY=false
VITE_API_BASE_URL=/api
```

---

## 프론트 단독 모드 (DUMMY_MODE, 기본값)

`VITE_USE_DUMMY`가 `false`가 아닌 모든 경우 더미 모드로 동작합니다.

### 현재 동작

- **대시보드**: 채널 추가/수정/삭제는 Pinia store에 in-memory로 저장. 새로고침 시 초기화됨
- **검색**: `src/constants/dummyData.js`의 `DUMMY_EVENTS` 3건을 자동 로드. 텍스트 검색과 채널 필터가 클라이언트 사이드에서 동작
- **클립 상세**: `DUMMY_EVENTS`에서 id로 조회. clip_url이 null이므로 영상은 빈 상태로 표시
- **채널 필터**: `DUMMY_CHANNELS` 3개가 고정 표시됨
- **메뉴얼**: 파일 메타데이터를 `localStorage("cctv_manuals")`에 저장. 새로고침 후에도 목록 유지. 실제 파일 내용은 저장되지 않음 (VLM RAG 연동 불가)

### 더미 데이터 수정

`src/constants/dummyData.js`에서 `DUMMY_CHANNELS`와 `DUMMY_EVENTS`를 직접 편집합니다.

### 메뉴얼 파일 저장 위치

브라우저 localStorage의 `cctv_manuals` 키. 파일 메타데이터(이름·크기·업로드 일시)만 저장되며 실제 바이너리는 저장되지 않습니다.

---

## 풀스택 전환 가이드

### 1. 환경변수 변경

```
VITE_USE_DUMMY=false
```

### 2. 수정이 필요한 파일

더미 모드 → 실제 모드 전환 시 **컴포넌트는 수정 불필요**. 아래 API 함수 내부의 `if (DUMMY_MODE)` 분기만 동작하지 않습니다.

| 파일 | 역할 | 백엔드 연동 포인트 |
|---|---|---|
| `src/api/events.js` | 이벤트 목록 조회·검색·단건 조회 | `GET /api/events`, `GET /api/events/search`, `GET /api/events/:id` |
| `src/api/manuals.js` | 메뉴얼 CRUD | `GET /api/manuals`, `POST /api/manuals`, `DELETE /api/manuals/:id` |
| `src/api/websocket.js` | 실시간 이벤트 수신 | `ws://host/ws/events` |
| `src/api/index.js` | axios 인스턴스 | baseURL 확인 |

### 3. 백엔드 API 엔드포인트 목록

| Method | Path | 설명 |
|---|---|---|
| `GET` | `/api/events` | 전체 이벤트 목록 |
| `GET` | `/api/events/search?q=&channel_id=` | 자연어 검색 (VLM/Qdrant) |
| `GET` | `/api/events/:id` | 단건 이벤트 조회 |
| `GET` | `/api/manuals` | 메뉴얼 목록 |
| `POST` | `/api/manuals` | 메뉴얼 업로드 (multipart/form-data) |
| `DELETE` | `/api/manuals/:id` | 메뉴얼 삭제 |
| `WS` | `/ws/events` | 실시간 이벤트 스트림 |

### 4. 채널 데이터

현재 채널은 프론트 Pinia store에서만 관리됩니다. 백엔드에 채널 CRUD API가 생기면:
- `src/api/channels.js` 신규 작성
- `src/stores/channelStore.js`에 persist 로직 추가
- `src/composables/useChannels.js`의 더미 분기 제거

### 5. Docker Compose 예시

```yaml
services:
  frontend:
    build: ./services/frontend
    ports: ["80:80"]
    environment:
      - VITE_USE_DUMMY=false
  backend:
    build: ./services/backend
    ports: ["8000:8000"]
  qdrant:
    image: qdrant/qdrant
    ports: ["6333:6333"]
```

---

## 컴포넌트 구조

```
src/
├── views/
│   ├── DashboardView.vue     # 2×2 채널 그리드
│   ├── SearchView.vue        # 이벤트 검색
│   ├── ClipDetailView.vue    # 클립 상세 (데이터 로딩)
│   └── ManualView.vue        # 메뉴얼 업로드/관리
├── components/
│   ├── layout/
│   │   └── AppNav.vue        # 상단 네비게이션 탭
│   ├── dashboard/
│   │   ├── ChannelGrid.vue   # 2×2 그리드 레이아웃
│   │   ├── ChannelCard.vue   # 개별 채널 카드
│   │   ├── AddChannelModal.vue
│   │   └── EventToast.vue    # 전폭 이벤트 배너
│   └── search/
│       ├── SearchBar.vue
│       ├── ChannelFilter.vue # 채널 칩 필터
│       ├── ResultList.vue
│       ├── ResultCard.vue
│       └── ClipDetail.vue    # 비디오 플레이어 + 메타패널
├── stores/
│   ├── channelStore.js
│   ├── eventStore.js         # lastSearchResults 포함
│   └── manualStore.js
├── composables/
│   ├── useChannels.js        # DUMMY_MODE 분기
│   ├── useEvents.js          # DUMMY_MODE 분기
│   └── useWebSocket.js
├── api/
│   ├── index.js              # axios 인스턴스
│   ├── events.js
│   ├── manuals.js            # DUMMY_MODE 분기
│   └── websocket.js
└── constants/
    ├── mode.js               # DUMMY_MODE 단일 소스
    ├── dummyData.js          # 더미 채널·이벤트 데이터
    └── events.js             # MAX_CHANNELS 등 상수
```

---

## 데이터 흐름

```
[WebSocket] → useWebSocket → eventStore.addEvent → EventToast

[SearchView]
  onMounted → useEvents.load() → DUMMY_EVENTS | fetchEvents()
  handleSearch → useEvents.search() → events ref
              → eventStore.setSearchResults()   (클립 목록 전달용)

[ClipDetailView]
  onMounted → DUMMY_EVENTS.find() | fetchEventById()
  relatedEvents ← eventStore.lastSearchResults

[ManualView]
  onMounted → manualStore.load() → localStorage | GET /api/manuals
  upload → manualStore.upload() → localStorage | POST /api/manuals
```
