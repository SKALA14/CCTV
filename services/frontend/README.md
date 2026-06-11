# AI CCTV Frontend

Vue 3 + Vite + Pinia + Vue Router + Tailwind CSS 기반 CCTV 관제/관리 웹앱.

백엔드(FastAPI) · MediaMTX(WebRTC) · Redis 파이프라인과 연동되는 **풀스택 클라이언트**입니다.

---

## 핵심 구조 — 관제(월) vs 콘솔

화면을 두 면으로 분리했습니다. **관제(월)** 가 홈이고, 설정·관리는 톱니 뒤 **콘솔**에 모았습니다.

```
로그인 → 관제(월) = 홈                  ← 사이드바 없는 풀스크린 라이브 그리드 + 실시간 알림
   └─ 헤더 우상단 [⚙ 콘솔] → 별도 창으로 콘솔 열기 (관제 화면은 그대로 유지)
                                ├─ 검색      (이벤트 자연어 검색)
                                ├─ 구역      (구역별 점검 체크리스트 현황)
                                ├─ 매뉴얼    (PDF 업로드 → 체크리스트)
                                ├─ 리포트    (admin 전용 — 안전 이벤트 집계·차트)
                                ├─ 현황      (admin 전용 — 현장/기기/계정 모니터링)
                                ├─ 관리      (admin 전용 — 계정 관리)
                                └─ 프로필    (비밀번호 변경·테마·로그아웃)
   ← 콘솔 사이드바 최상위에서 관제로 복귀(또는 콘솔 창을 닫음)
```

> 사이드바 상단엔 **시스템 상태 점등**(자기 현장 채널 온라인 `n/N`, 색 점)이, 하단 프로필엔 **인삿말 + 마지막 접속 시각**이 표시됩니다(서비스 상태/개인화).

- **홈(`/`)은 `/wall`로 리다이렉트** — 로그인하면 바로 관제 화면이 단일로 뜸
- 관제(`/wall`)는 `meta.bare` 라우트라 사이드바 등 크롬을 숨김
- 라이브 그리드(`DashboardView`)는 관제에서만 마운트됨 (콘솔 창이 WebRTC를 이중 연결하지 않도록)

---

## 역할(RBAC) — admin / user

2단계 역할이며, 화면(월/콘솔)이 아니라 **권한(보기 vs 관리)** 으로 갈립니다.

| 기능 | **user** | **admin** |
|---|---|---|
| 관제(월) · 검색 · 구역 · 매뉴얼 보기 | ✅ | ✅ |
| 채널 추가/수정/삭제 | ❌ | ✅ |
| 매뉴얼·구역 등록, 체크리스트 편집 | ❌ | ✅ |
| 리포트 · 현황 · 관리(계정) 탭 | ❌ | ✅ |
| 계정 생성(admin·user 둘 다) | ❌ | ✅ |

- 역할은 한 현장(site)에 소속됩니다(모든 계정 `site_id` 필수). 현장과 초기 admin은 **설치 시 백엔드에서 seed** 되며, 추가 계정은 admin이 관리 탭에서 생성합니다. 모든 데이터(이벤트·채널·체크리스트·현황)는 **자기 현장으로 격리**됩니다.
- 라우터 가드(`src/router/index.js`): `meta.public`(로그인) · `meta.bare`(월) · `meta.adminOnly`(리포트·현황·관리) + 최초 로그인 시 비밀번호 변경 강제(`/password-change`).

---

## 인증

- 백엔드가 **httpOnly 쿠키(JWT)** 를 발급. axios는 `withCredentials: true`로 쿠키를 자동 전송합니다(`src/api/index.js`).
- 응답이 `401`이면 자동으로 `/login`으로 이동.
- 상태는 `src/stores/authStore.js`(`user`, `isLoggedIn`, `isAdmin`, `mustChangePwd`).

---

## 실시간 영상 — WebRTC(MediaMTX)

영상은 MediaMTX를 통해 WebRTC로 재생/송출합니다. nginx가 `/webrtc/` → `mediamtx:8889`로 프록시합니다(`constants/mediamtx.js`의 `MEDIAMTX_URL = '/webrtc'`).

| 소스 타입 | 재생/송출 | 비고 |
|---|---|---|
| `rtsp` | **WHEP**로 재생 (`useWebRTC`) | 백엔드가 RTSP를 MediaMTX 경로로 끌어옴 |
| `webcam` | 브라우저가 **WHIP**로 송출 (`useWebRTCPublish`) 후 재생 | |
| `file` | `<video src="/sample/...">` | 로컬 샘플 파일 |
| `youtube` | iframe 임베드 | |

> **경로(mtxPath) 주의**: MediaMTX 경로는 현장 격리를 위해 `{site_id 앞 8자}_{채널명}` 접두사가 붙습니다. 프론트는 채널명이 아니라 **백엔드가 내려주는 `channel.mtxPath`** 로 WHEP/WHIP URL을 구성해야 합니다(`ChannelCard.vue`). 채널 등록 응답·`GET /channels` 모두 `mtxPath`를 포함합니다.

---

## 실시간 알림

- `useWebSocket` → `ws://<host>/ws` 연결(JWT 쿠키 인증). 끊기면 3초 간격 재연결, 인증 실패(4001) 시 로그인으로 이동.
- 수신 이벤트는 `eventStore`로 들어가 **`NotificationToast`** (우하단, 전 페이지 표시)로 노출됩니다.

---

## 매뉴얼 · 체크리스트

PDF 안전 매뉴얼을 업로드해 구역별 점검 체크리스트를 생성/편집합니다(admin).

- 업로드 → 분석(`analyzeManual`) → 보정(`refineManual`) → 확정(`confirmManual`)
- **구역별 보기 + 인라인 편집**: `ManualView` + `ChecklistReview` / `ChecklistItem`. 확정된 체크리스트를 STATIC/DYNAMIC·구역(zone)별로 보고 항목을 직접 추가/수정.
- 구역은 CSV/XLSX(`registerZones`)로 등록.

---

## 실행

```bash
npm install
npm run dev      # 개발 서버 (Vite, 기본 5173)
npm run build    # 프로덕션 빌드 → dist/
npm run preview  # 빌드 결과 미리보기
```

배포 시에는 `nginx.conf`가 `dist/`를 서빙하며 `/api`(백엔드)·`/ws`(웹소켓)·`/webrtc`(MediaMTX)를 프록시합니다. 컨테이너 빌드는 루트 `infra/docker-compose.yaml`의 `frontend` 서비스를 사용하세요.

### 환경변수

| 변수 | 기본값 | 설명 |
|---|---|---|
| `VITE_USE_DUMMY` | (미설정 시 `true`) | `false`면 실제 백엔드 사용. 배포(`.env.example`)는 `false` |

> **DUMMY_MODE는 레거시 부분 스텁**입니다. 인증·WebRTC·현황·관리에는 더미가 없으며, 일부 API(`channels`/`events`/`manuals`)에만 `if (DUMMY_MODE)` 분기가 남아 있습니다. 실제 운영은 항상 `VITE_USE_DUMMY=false`.

---

## 라우트

| 경로 | 이름 | 메타 | 화면 |
|---|---|---|---|
| `/login` | login | `public` | 로그인 |
| `/` | — | redirect | → `/wall` |
| `/wall` | wall | `bare` | 관제(풀스크린 라이브 그리드) |
| `/search` · `/search/:id` | search · clip-detail | — | 이벤트 검색 / 클립 상세 |
| `/zones` | zones | — | 구역별 점검 체크리스트 현황 |
| `/manual` | manual | — | 매뉴얼·체크리스트 |
| `/reports` | reports | `adminOnly` | 안전 이벤트 집계·차트 |
| `/admin` | admin | `adminOnly` | 계정 관리 |
| `/status` | status | `adminOnly` | 현장/기기/계정 현황 |
| `/profile` | profile | — | 프로필 |
| `/password-change` | password-change | — | 비밀번호 변경(최초 로그인 강제) |

---

## API 연동 맵

모든 호출은 axios 인스턴스(`src/api/index.js`, baseURL `/api`, 쿠키 인증)를 통합니다.

| 파일 | 백엔드 엔드포인트 |
|---|---|
| `api/auth.js` | `POST /auth/login`, `POST /auth/logout`, `GET /auth/me` |
| `api/channels.js` | `GET/POST /channels`, `PUT/DELETE /channels/{name}` |
| `api/events.js` | `GET /events`, 자연어 검색, 단건 조회 |
| `api/manuals.js` | 분석/보정/확정 · `zones` · `checklist` |
| `api/sites.js` | `GET /sites` (현장은 seed 전용, 읽기만) |
| `api/users.js` | `/sites/{id}/users` CRUD, `PATCH /users/me/password` |
| `api/status.js` | `/status/overview · /devices · /accounts · /sites/{id}/today-events · /health` |
| `api/reports.js` | `GET /reports/summary` (안전 이벤트 집계) |
| `api/websocket.js` | `WS /ws` |

---

## 디렉터리 구조

```
src/
├── App.vue                      # 루트 셸: 월/콘솔 레이아웃 분기, WS·채널 부트스트랩, 상태 점등(health pill)
├── main.js
├── router/index.js              # 라우트 + 인증/역할 가드
├── views/
│   ├── DashboardView.vue        # 관제(월) 라이브 그리드 + [⚙ 콘솔] 진입
│   ├── SearchView.vue           # 이벤트 검색
│   ├── ClipDetailView.vue       # 클립 상세
│   ├── ZoneView.vue             # 구역별 점검 체크리스트 현황
│   ├── ManualView.vue           # 매뉴얼 업로드 + 구역별 체크리스트 편집
│   ├── ReportView.vue           # 안전 이벤트 집계·SVG 미니차트(admin)
│   ├── StatusView.vue           # 현황(admin, 자기 현장)
│   ├── AdminView.vue            # 계정 관리(admin, 자기 현장)
│   ├── ProfileView.vue          # 프로필·비번·테마·로그아웃 + 인삿말·마지막 접속
│   ├── LoginView.vue
│   └── PasswordChangeView.vue
├── components/
│   ├── layout/
│   │   ├── AppNav.vue           # 콘솔 사이드바 내비
│   │   └── AppHeader.vue
│   ├── dashboard/
│   │   ├── ChannelGrid.vue      # 2×2 그리드(빈 슬롯 클릭으로 채널 추가)
│   │   ├── ChannelCard.vue      # WebRTC(WHEP/WHIP) 재생/송출
│   │   ├── AddChannelModal.vue
│   │   ├── EventPanel.vue       # 알림 히스토리 패널
│   │   └── NotificationToast.vue
│   ├── manual/
│   │   ├── ChecklistReview.vue  # 확정 체크리스트 구역별 보기
│   │   └── ChecklistItem.vue    # 항목 인라인 편집
│   └── search/
│       ├── SearchBar.vue · ChannelFilter.vue
│       ├── ResultList.vue · ResultCard.vue · ClipDetail.vue
├── stores/                      # authStore · channelStore · eventStore · manualStore
├── composables/
│   ├── useWebRTC.js             # WHEP 재생 클라이언트
│   ├── useWebRTCPublish.js      # WHIP 송출(webcam)
│   ├── useWebSocket.js          # 실시간 알림
│   └── useChannels.js · useEvents.js · useTheme.js
├── api/                         # axios 래퍼 (위 연동 맵 참고)
├── constants/
│   ├── mode.js                  # DUMMY_MODE 플래그
│   ├── mediamtx.js              # MEDIAMTX_URL
│   └── events.js · dummyData.js
└── utils/detectSourceType.js
```

---

## 데이터 흐름 요약

```
[부팅] App.vue → useWebSocket(/ws) + 로그인 사용자 채널 로드(GET /channels)

[관제(월)] /wall → DashboardView
   ChannelGrid → ChannelCard → useWebRTC(`/webrtc/{mtxPath}/whep`)  # 영상
   WS 알림 → eventStore → NotificationToast                          # 알림

[콘솔] (별도 창) /search · /zones · /manual · /reports · /status · /admin · /profile
   각 view → api/*.js → /api/...   (쿠키 인증)
   상태 점등(App.vue) → GET /status/health   ·   리포트 → GET /reports/summary

[매뉴얼] ManualView → analyze/refine/confirm → 구역별 체크리스트(ChecklistReview/Item)
```
