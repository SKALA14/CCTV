#!/usr/bin/env bash
# 더블클릭 → 스택 자동 기동 + 관제 wall을 'URL 바 없는' 앱 창으로 열기 (macOS / 개발·데모용)
set -euo pipefail

INFRA_DIR="$(cd "$(dirname "$0")/.." && pwd)"
URL="http://localhost/wall"
CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
PROFILE="$HOME/.cctv-wall-chrome"   # 사용자 기본 크롬과 분리된 전용 프로필

cd "$INFRA_DIR"

echo "▶ 스택 기동 (docker compose up -d)…"
docker compose up -d

echo "▶ 프론트 준비 대기…"
for i in $(seq 1 30); do
  if curl -fsS -o /dev/null "$URL"; then break; fi
  sleep 1
done

echo "▶ 관제 wall 열기 (앱 창)…"
"$CHROME" --app="$URL" --user-data-dir="$PROFILE" >/dev/null 2>&1 &

echo "✓ 완료. 콘솔은 wall 화면의 '콘솔' 버튼으로 여세요."
