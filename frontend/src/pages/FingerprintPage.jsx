import { ArrowLeft, GitCompare } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { Bar, BarChart, Cell, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { analysisApi, fingerprintApi } from '../api/endpoints.js'
import TruthFingerprintCard from '../components/fingerprint/TruthFingerprintCard.jsx'
import { Button, EmptyState, Spinner } from '../components/ui/index.jsx'
import { formatDate, VERDICTS } from '../utils/format.js'

/** Dedicated Truth Fingerprint page: identity, claim distribution, verification history, comparison. */
export default function FingerprintPage() {
  const { videoId } = useParams()
  const navigate = useNavigate()
  const [fp, setFp] = useState(null)
  const [error, setError] = useState(null)

  const load = () => fingerprintApi.get(videoId).then(setFp).catch(setError)
  useEffect(() => { load() }, [videoId]) // eslint-disable-line react-hooks/exhaustive-deps

  if (error) {
    return <EmptyState title="No Truth Fingerprint yet" action={<Button as={Link} to={`/analysis/${videoId}`}>Back to analysis</Button>}>{error.message}</EmptyState>
  }
  if (!fp) return <Spinner label="Loading fingerprint…" />

  const dist = Object.entries(VERDICTS).map(([k, m]) => ({ key: k, name: m.label.replace('Insufficient Evidence', 'Insufficient'), value: fp.counts[k] || 0, color: m.color }))
  const history = fp.versions.map((v) => ({ name: `v${v.version}`, score: v.truth_score, evidence: v.evidence_quality, date: formatDate(v.verified_at) }))

  return (
    <div className="mx-auto max-w-6xl space-y-6">
      <Link to={`/analysis/${videoId}`} className="inline-flex items-center gap-1 text-sm text-navy-500 hover:text-navy-900"><ArrowLeft className="h-4 w-4" />Back to analysis</Link>
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-extrabold">Truth Fingerprint</h1>
          <p className="text-sm text-navy-500">{fp.video.title}</p>
        </div>
        <Button as={Link} to={`/compare?a=${videoId}`} variant="secondary"><GitCompare className="h-4 w-4" />Compare with another video</Button>
      </div>

      <div className="grid lg:grid-cols-5 gap-6">
        <div className="lg:col-span-2">
          <TruthFingerprintCard fingerprint={fp} onSeek={() => navigate(`/analysis/${videoId}`)}
            onRecheck={async () => { await analysisApi.recheck(videoId); navigate(`/analysis/${videoId}`) }} />
        </div>
        <div className="lg:col-span-3 space-y-6">
          <section className="card p-5">
            <h2 className="font-bold">Claim distribution</h2>
            <div className="mt-3 h-48">
              <ResponsiveContainer>
                <BarChart data={dist} margin={{ left: -20 }}>
                  <XAxis dataKey="name" tick={{ fontSize: 12, fill: '#42629b' }} axisLine={false} tickLine={false} />
                  <YAxis allowDecimals={false} tick={{ fontSize: 12, fill: '#42629b' }} axisLine={false} tickLine={false} />
                  <Tooltip cursor={{ fill: '#f1f4f9' }} />
                  <Bar dataKey="value" radius={[6, 6, 0, 0]}>{dist.map((d) => <Cell key={d.key} fill={d.color} />)}</Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </section>
          <section className="card p-5">
            <h2 className="font-bold">Verification history</h2>
            <p className="text-sm text-navy-500">Truth score and evidence quality across every verification of this video.</p>
            {history.length > 1 ? (
              <div className="mt-3 h-48">
                <ResponsiveContainer>
                  <LineChart data={history} margin={{ left: -20, right: 10 }}>
                    <XAxis dataKey="name" tick={{ fontSize: 12, fill: '#42629b' }} axisLine={false} tickLine={false} />
                    <YAxis domain={[0, 100]} tick={{ fontSize: 12, fill: '#42629b' }} axisLine={false} tickLine={false} />
                    <Tooltip />
                    <Line type="monotone" dataKey="score" name="Truth score" stroke="#14213d" strokeWidth={2} dot />
                    <Line type="monotone" dataKey="evidence" name="Evidence quality" stroke="#6482b5" strokeWidth={2} strokeDasharray="4 3" dot />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            ) : (
              <p className="mt-3 text-sm text-navy-400">One verification so far. Use “Re-check evidence” to add a version and track changes over time.</p>
            )}
          </section>
        </div>
      </div>
    </div>
  )
}
