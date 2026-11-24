import { Loader2 } from 'lucide-react'
import { Link } from 'react-router-dom'
import { confidenceLabel, pct, verdictLabel, verdictMeta } from '../../utils/format.js'

export function Logo({ to = '/', light = false }) {
  return (
    <Link to={to} className="flex items-center gap-2.5 font-display font-extrabold text-lg">
      <svg viewBox="0 0 32 32" className="h-8 w-8" aria-hidden>
        <path d="M16 2 4 6.5v8.2c0 7.3 5 13.4 12 15.3 7-1.9 12-8 12-15.3V6.5L16 2z" fill={light ? '#fff' : '#14213d'} />
        <path d="m10.5 16.2 3.6 3.6 7.4-7.6" fill="none" stroke={light ? '#14213d' : '#fff'} strokeWidth="2.6"
          strokeLinecap="round" strokeLinejoin="round" />
      </svg>
      <span className={light ? 'text-white' : 'text-navy-900'}>LiveTruth <span className="font-semibold opacity-70">Shield</span></span>
    </Link>
  )
}

const VARIANTS = {
  primary: 'bg-navy-900 text-white hover:bg-navy-800 shadow-sm',
  secondary: 'bg-white text-navy-900 border border-navy-200 hover:bg-navy-50',
  ghost: 'text-navy-700 hover:bg-navy-50',
  danger: 'bg-white text-red-600 border border-red-200 hover:bg-red-50',
}

export function Button({ variant = 'primary', loading, className = '', children, as: As = 'button', ...props }) {
  return (
    <As
      className={`inline-flex items-center justify-center gap-2 rounded-xl px-4 py-2.5 text-sm font-semibold transition
        disabled:opacity-50 disabled:cursor-not-allowed ${VARIANTS[variant]} ${className}`}
      disabled={loading || props.disabled}
      {...props}
    >
      {loading && <Loader2 className="h-4 w-4 animate-spin" />}
      {children}
    </As>
  )
}

export function Spinner({ label = 'Loading…' }) {
  return (
    <div className="flex items-center justify-center gap-3 py-16 text-navy-500" role="status">
      <Loader2 className="h-5 w-5 animate-spin" /> <span className="text-sm">{label}</span>
    </div>
  )
}

export function VerdictBadge({ verdict, size = 'sm', lang = 'en' }) {
  const m = verdictMeta(verdict)
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full ring-1 ${m.bg} ${m.text} ${m.ring}
      ${size === 'lg' ? 'px-3 py-1 text-sm' : 'px-2.5 py-0.5 text-xs'} font-semibold whitespace-nowrap`}>
      <span className="h-2 w-2 rounded-full" style={{ background: m.color }} />
      {verdictLabel(verdict, lang)}
    </span>
  )
}

export function ConfidenceMeter({ value, color }) {
  return (
    <div className="flex items-center gap-2 text-xs text-navy-500" title="Computed from the amount, agreement, diversity and credibility of retrieved evidence — not from the AI's own certainty.">
      <span className="font-medium">Confidence</span>
      {value == null ? (
        <span className="italic">{confidenceLabel(null)}</span>
      ) : (
        <>
          <div className="h-1.5 w-20 rounded-full bg-navy-100 overflow-hidden">
            <div className="h-full rounded-full" style={{ width: pct(value), background: color }} />
          </div>
          <span className="tabular-nums font-semibold text-navy-700">{pct(value)}</span>
          <span>({confidenceLabel(value)})</span>
        </>
      )}
    </div>
  )
}

export function EmptyState({ icon: Icon, title, children, action }) {
  return (
    <div className="card flex flex-col items-center text-center px-6 py-14">
      {Icon && <div className="mb-4 rounded-2xl bg-navy-50 p-3 text-navy-600"><Icon className="h-6 w-6" /></div>}
      <h3 className="text-lg font-bold">{title}</h3>
      {children && <p className="mt-1 max-w-md text-sm text-navy-500">{children}</p>}
      {action && <div className="mt-5">{action}</div>}
    </div>
  )
}

export function ErrorBanner({ error, onRetry }) {
  if (!error) return null
  return (
    <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 flex items-center justify-between gap-3" role="alert">
      <span>{error.message || String(error)}</span>
      {onRetry && <button className="font-semibold underline" onClick={onRetry}>Try again</button>}
    </div>
  )
}
