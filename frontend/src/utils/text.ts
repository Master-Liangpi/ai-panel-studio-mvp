export function looksCorrupted(value?: string | null): boolean {
  if (!value) return true
  const trimmed = value.trim()
  if (!trimmed) return true

  const questionMarks = (trimmed.match(/\?/g) || []).length
  if (questionMarks > 0 && questionMarks / trimmed.length >= 0.4) {
    return true
  }

  return /[�]|[ÃÂ][\S]?|[涓鈥鍏锛鏃寰缁璁]/.test(trimmed)
}

export function sanitizeDisplayText(
  value: string | null | undefined,
  fallback: string,
): string {
  if (!value) return fallback
  const trimmed = value.trim()
  if (!trimmed || looksCorrupted(trimmed)) {
    return fallback
  }
  return trimmed
}
