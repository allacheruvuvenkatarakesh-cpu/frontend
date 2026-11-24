export const VERDICTS = {
  verified: { label: 'Verified', color: '#16a34a', bg: 'bg-green-50', text: 'text-green-700', ring: 'ring-green-200' },
  false: { label: 'False', color: '#dc2626', bg: 'bg-red-50', text: 'text-red-700', ring: 'ring-red-200' },
  misleading: { label: 'Misleading', color: '#eab308', bg: 'bg-yellow-50', text: 'text-yellow-800', ring: 'ring-yellow-200' },
  unverified: { label: 'Insufficient Evidence', color: '#9ca3af', bg: 'bg-gray-100', text: 'text-gray-600', ring: 'ring-gray-200' },
}

export const STANCES = {
  supports: { label: 'Supports', cls: 'bg-green-50 text-green-700' },
  refutes: { label: 'Refutes', cls: 'bg-red-50 text-red-700' },
  mixed: { label: 'Mixed', cls: 'bg-yellow-50 text-yellow-800' },
  irrelevant: { label: 'Not directly relevant', cls: 'bg-gray-100 text-gray-500' },
}

export const verdictMeta = (v) => VERDICTS[v] || VERDICTS.unverified

export function formatTime(seconds) {
  if (seconds == null || Number.isNaN(seconds)) return '--:--'
  const s = Math.max(0, Math.floor(seconds))
  const h = Math.floor(s / 3600)
  const m = Math.floor((s % 3600) / 60)
  const sec = String(s % 60).padStart(2, '0')
  return h ? `${h}:${String(m).padStart(2, '0')}:${sec}` : `${m}:${sec}`
}

export function formatDate(iso) {
  if (!iso) return ''
  return new Date(iso).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' })
}

export const pct = (x) => (x == null ? '—' : `${Math.round(x * 100)}%`)

export const isActive = (status) => !['completed', 'failed'].includes(status)

export function confidenceLabel(c) {
  if (c == null) return 'Not enough evidence'
  if (c >= 0.75) return 'High'
  if (c >= 0.5) return 'Moderate'
  return 'Low'
}

/** Split an explanation into text and [E#] citation tokens. */
export function splitCitations(text = '') {
  return text.split(/(\[E\d+\])/g).filter(Boolean).map((part) => {
    const m = part.match(/^\[E(\d+)\]$/)
    return m ? { cite: Number(m[1]) } : { text: part }
  })
}

export const LANGUAGES = { en: 'English', hi: 'हिन्दी (Hindi)', te: 'తెలుగు (Telugu)' }
export const LANGUAGE_NAMES = { en: 'English', hi: 'Hindi', te: 'Telugu' }

// Verdict labels in the supported languages (have a native speaker review before launch).
export const VERDICT_I18N = {
  en: { verified: 'Verified', false: 'False', misleading: 'Misleading', unverified: 'Insufficient Evidence' },
  hi: { verified: 'सत्यापित', false: 'गलत', misleading: 'भ्रामक', unverified: 'अपर्याप्त साक्ष्य' },
  te: { verified: 'ధృవీకరించబడింది', false: 'తప్పు', misleading: 'తప్పుదోవ పట్టించేది', unverified: 'తగిన ఆధారాలు లేవు' },
}
export const verdictLabel = (v, lang = 'en') => (VERDICT_I18N[lang] || VERDICT_I18N.en)[v] || verdictMeta(v).label

export const TRUST_STYLES = {
  high: 'bg-green-50 text-green-700 ring-green-200',
  medium: 'bg-navy-50 text-navy-700 ring-navy-200',
  low: 'bg-orange-50 text-orange-700 ring-orange-200',
}
export const RISK_STYLES = {
  high: 'bg-red-50 text-red-700 ring-red-200', medium: 'bg-yellow-50 text-yellow-800 ring-yellow-200',
  low: 'bg-navy-50 text-navy-700 ring-navy-200', none: 'bg-gray-50 text-gray-500 ring-gray-200',
  unknown: 'bg-gray-50 text-gray-500 ring-gray-200',
}
