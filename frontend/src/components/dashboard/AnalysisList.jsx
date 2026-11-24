import { AlertCircle, ChevronRight, Loader2, Trash2 } from 'lucide-react'
import { Link } from 'react-router-dom'
import { formatDate, isActive, VERDICTS } from '../../utils/format.js'

function MiniBar({ counts = {}, total }) {
  if (!total) return null
  return (
    <div className="flex h-1.5 w-28 overflow-hidden rounded-full bg-navy-100" aria-hidden>
      {Object.entries(VERDICTS).map(([k, m]) => counts[k] ? (
        <div key={k} style={{ width: `${(counts[k] / total) * 100}%`, background: m.color }} />
      ) : null)}
    </div>
  )
}

function StatusPill({ item }) {
  if (item.status === 'failed') return <span className="inline-flex items-center gap-1 text-xs font-semibold text-red-600"><AlertCircle className="h-3.5 w-3.5" />Failed</span>
  if (isActive(item.status)) return <span className="inline-flex items-center gap-1 text-xs font-semibold text-navy-600"><Loader2 className="h-3.5 w-3.5 animate-spin" />{item.progress}%</span>
  return <span className="text-xs font-semibold text-navy-700">{item.summary?.overall_rating}</span>
}

export default function AnalysisList({ items, onDelete }) {
  return (
    <ul className="divide-y divide-navy-100">
      {items.map((item) => (
        <li key={item.video_id} className="group flex items-center gap-3">
          <Link to={`/analysis/${item.video_id}`} className="flex flex-1 min-w-0 items-center gap-4 py-3.5 px-2 rounded-xl hover:bg-navy-50/60 transition">
            <div className="min-w-0 flex-1">
              <div className="truncate font-semibold text-sm">{item.title}</div>
              <div className="mt-0.5 text-xs text-navy-400">
                {item.platform ? item.platform.charAt(0).toUpperCase() + item.platform.slice(1) : item.source_type === 'upload' ? 'Upload' : 'Direct link'}
                {' · '}{formatDate(item.created_at)}
                {item.summary?.total_claims ? ` · ${item.summary.total_claims} claims` : ''}
              </div>
            </div>
            <div className="hidden sm:block"><MiniBar counts={item.summary?.counts} total={item.summary?.total_claims} /></div>
            <div className="w-32 text-right"><StatusPill item={item} /></div>
            <ChevronRight className="h-4 w-4 text-navy-300" />
          </Link>
          {onDelete && (
            <button aria-label={`Delete ${item.title}`} onClick={() => onDelete(item)} disabled={isActive(item.status)}
              className="rounded-lg p-2 text-navy-300 hover:text-red-600 hover:bg-red-50 disabled:invisible">
              <Trash2 className="h-4 w-4" />
            </button>
          )}
        </li>
      ))}
    </ul>
  )
}
