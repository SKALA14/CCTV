export function getAvatarText(name) {
  const normalized = String(name ?? '').trim()

  if (!normalized) return '?'

  const parts = normalized.split(/\s+/).filter(Boolean)
  if (parts.length >= 2) {
    return parts.slice(0, 2).map(part => part[0] ?? '').join('').toUpperCase()
  }

  const compact = normalized.replace(/\s+/g, '')
  const hasLatinOrDigit = /[A-Za-z0-9]/.test(compact)

  return hasLatinOrDigit
    ? compact.slice(0, 2).toUpperCase()
    : compact.slice(0, 2)
}
