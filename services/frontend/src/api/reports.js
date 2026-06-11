import api from './index.js'

// 자기 현장 최근 N일 안전 이벤트 집계 — 리포트 탭용
export const getReportSummary = (days = 7) =>
  api.get('/reports/summary', { params: { days } }).then(r => r.data)
