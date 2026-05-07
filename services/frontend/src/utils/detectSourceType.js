/**
 * URL 문자열로 ingestion 소스 타입을 반환합니다.
 * 반환값: 'rtsp' | 'youtube' | 'file'
 */
export function detectSourceType(url) {
  const lower = url.toLowerCase()
  if (lower.startsWith('rtsp://') || lower.startsWith('rtsps://')) return 'rtsp'
  if (lower.includes('youtube.com/') || lower.includes('youtu.be/')) return 'youtube'
  return 'file'
}
