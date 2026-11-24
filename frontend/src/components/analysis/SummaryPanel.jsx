import { Bar, BarChart, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { VERDICTS } from '../../utils/format.js'

const RATING_STYLES = {
  'Mostly Accurate': 'bg-green-50 text-green-800 ring-green-200',
  'Mixed Accuracy': 'bg-yellow-50 text-yellow-800 ring-yellow-200',
  'Mostly Inaccurate': 'bg-red-50 text-red-700 ring-red-200',
}

export default function SummaryPanel({ summary }) {
  const data = Object.entries(VERDICTS).map(([k, m]) => ({ key: k, name: m.label.replace('Insufficient Evidence', 'Insufficient'), value: summary.counts?.[k] || 0, color: m.color }))
  return (
    <div className="card p-5">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="text-xs font-semibold uppercase tracking-wide text-navy-400">Overall</div>
          <span className={`mt-1 inline-block rounded-full px-3 py-1 text-sm font-bold ring-1 ${RATING_STYLES[summary.overall_rating] || 'bg-gray-100 text-gray-700 ring-gray-200'}`}>
            {summary.overall_rating}
          </span>
        </div>
        <div className="text-right">
          <div className="text-xs font-semibold uppercase tracking-wide text-navy-400">Truth score</div>
          <div className="font-display text-3xl font-extrabold tabular-nums">{summary.truth_score == null ? '—' : Math.round(summary.truth_score)}</div>
        </div>
      </div>
      <p className="mt-3 text-sm text-navy-600">{summary.overall_explanation}</p>
      {summary.total_claims > 0 && (
        <div className="mt-4 h-32">
          <ResponsiveContainer>
            <BarChart data={data} layout="vertical" margin={{ left: 8, right: 16 }}>
              <XAxis type="number" hide allowDecimals={false} />
              <YAxis type="category" dataKey="name" width={84} tick={{ fontSize: 12, fill: '#42629b' }} axisLine={false} tickLine={false} />
              <Tooltip cursor={{ fill: '#f1f4f9' }} />
              <Bar dataKey="value" radius={[0, 6, 6, 0]} barSize={14}>
                {data.map((d) => <Cell key={d.key} fill={d.color} />)}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}
      <p className="mt-3 text-[11px] text-navy-400">
        Truth score weights verified = 100, misleading = 50, false = 0 by evidence confidence. Claims with insufficient evidence are excluded.
      </p>
    </div>
  )
}
