import { CheckCircle2, Film, MessageSquareQuote } from 'lucide-react'
import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from 'recharts'
import { VERDICTS } from '../../utils/format.js'

export default function StatsPanel({ stats }) {
  const counts = stats?.verdict_counts || {}
  const data = Object.entries(VERDICTS).map(([k, m]) => ({ key: k, name: m.label, value: counts[k] || 0, color: m.color }))
  const hasData = data.some((d) => d.value > 0)

  const tiles = [
    { icon: Film, label: 'Videos analysed', value: stats?.total_analyses ?? '—' },
    { icon: CheckCircle2, label: 'Completed', value: stats?.completed ?? '—' },
    { icon: MessageSquareQuote, label: 'Claims checked', value: stats?.total_claims ?? '—' },
  ]

  return (
    <div className="card p-6">
      <h2 className="text-lg font-bold">Your activity</h2>
      <div className="mt-4 grid grid-cols-3 gap-3">
        {tiles.map(({ icon: Icon, label, value }) => (
          <div key={label} className="rounded-xl bg-paper border border-navy-100 p-3">
            <Icon className="h-4 w-4 text-navy-400" />
            <div className="mt-2 text-2xl font-display font-extrabold tabular-nums">{value}</div>
            <div className="text-xs text-navy-500">{label}</div>
          </div>
        ))}
      </div>

      <h3 className="mt-6 text-sm font-semibold text-navy-700">Verdict breakdown</h3>
      {hasData ? (
        <div className="mt-2 flex items-center gap-4">
          <div className="h-36 w-36 shrink-0">
            <ResponsiveContainer>
              <PieChart>
                <Pie data={data} dataKey="value" nameKey="name" innerRadius={38} outerRadius={64} paddingAngle={2} stroke="none">
                  {data.map((d) => <Cell key={d.key} fill={d.color} />)}
                </Pie>
                <Tooltip />
              </PieChart>
            </ResponsiveContainer>
          </div>
          <ul className="space-y-1.5 text-sm">
            {data.map((d) => (
              <li key={d.key} className="flex items-center gap-2">
                <span className="h-2.5 w-2.5 rounded-full" style={{ background: d.color }} />
                <span className="text-navy-600">{d.name}</span>
                <span className="ml-auto pl-3 font-semibold tabular-nums">{d.value}</span>
              </li>
            ))}
          </ul>
        </div>
      ) : (
        <p className="mt-2 text-sm text-navy-400">Results appear here once your first analysis finishes.</p>
      )}
    </div>
  )
}
