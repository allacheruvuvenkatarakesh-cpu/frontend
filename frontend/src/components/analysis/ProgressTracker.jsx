import { motion } from 'framer-motion'
import { AlertTriangle, Check, Loader2 } from 'lucide-react'
import { Button } from '../ui/index.jsx'

const STAGES = [
  ['capturing', 'Capture video & extract audio'],
  ['transcribing', 'Transcribe speech'],
  ['extracting_claims', 'Find factual claims'],
  ['verifying', 'Verify claims with evidence'],
  ['completed', 'Build verdicts & timeline'],
]

export default function ProgressTracker({ status, onRetry }) {
  const failed = status.status === 'failed'
  const current = STAGES.findIndex(([k]) => k === status.status)
  const idx = status.status === 'queued' ? -1 : current

  return (
    <div className="card p-6" aria-live="polite">
      <div className="flex items-center justify-between">
        <h2 className="font-bold">{failed ? 'Analysis stopped' : status.stage_label}</h2>
        {!failed && <span className="text-sm font-semibold tabular-nums text-navy-600">{status.progress}%</span>}
      </div>
      {!failed && (
        <div className="mt-3 h-2 rounded-full bg-navy-100 overflow-hidden">
          <motion.div className="h-full bg-navy-800 rounded-full" animate={{ width: `${status.progress}%` }} transition={{ ease: 'easeOut' }} />
        </div>
      )}
      {failed ? (
        <div className="mt-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3 rounded-xl bg-red-50 border border-red-200 p-4">
          <div className="flex gap-3 text-sm text-red-700"><AlertTriangle className="h-5 w-5 shrink-0" />{status.error || 'Something went wrong.'}</div>
          {onRetry && <Button variant="danger" onClick={onRetry}>Retry analysis</Button>}
        </div>
      ) : (
        <ol className="mt-5 grid sm:grid-cols-5 gap-3">
          {STAGES.map(([key, label], i) => {
            const done = i < idx || status.status === 'completed'
            const active = i === idx && status.status !== 'completed'
            return (
              <li key={key} className={`flex items-center gap-2 text-xs ${done || active ? 'text-navy-900' : 'text-navy-300'}`}>
                <span className={`flex h-6 w-6 shrink-0 items-center justify-center rounded-full border
                  ${done ? 'bg-navy-900 border-navy-900 text-white' : active ? 'border-navy-700' : 'border-navy-200'}`}>
                  {done ? <Check className="h-3.5 w-3.5" /> : active ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : i + 1}
                </span>
                <span className="font-medium">{label}</span>
              </li>
            )
          })}
        </ol>
      )}
    </div>
  )
}
