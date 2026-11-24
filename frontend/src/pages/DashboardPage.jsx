import { Inbox } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { analysisApi } from '../api/endpoints.js'
import AnalysisList from '../components/dashboard/AnalysisList.jsx'
import QuickClaimCheck from '../components/dashboard/QuickClaimCheck.jsx'
import StatsPanel from '../components/dashboard/StatsPanel.jsx'
import SubmitVideoForm from '../components/dashboard/SubmitVideoForm.jsx'
import { ErrorBanner } from '../components/ui/index.jsx'
import { useAuth } from '../context/AuthContext.jsx'
import { isActive } from '../utils/format.js'

export default function DashboardPage() {
  const { user } = useAuth()
  const [stats, setStats] = useState(null)
  const [recent, setRecent] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    let timer
    let cancelled = false
    const load = async () => {
      try {
        const [s, r] = await Promise.all([analysisApi.stats(), analysisApi.list({ pageSize: 5 })])
        if (cancelled) return
        setStats(s); setRecent(r.items); setError(null)
        if (r.items.some((i) => isActive(i.status))) timer = setTimeout(load, 4000)
      } catch (e) { if (!cancelled) setError(e) }
    }
    load()
    return () => { cancelled = true; clearTimeout(timer) }
  }, [])

  return (
    <div className="mx-auto max-w-6xl space-y-6">
      <div>
        <h1 className="text-2xl font-extrabold">Hello, {user?.name?.split(' ')[0]}</h1>
        <p className="text-sm text-navy-500">Paste a link or upload a video to check its claims.</p>
      </div>
      <ErrorBanner error={error} />
      <div className="grid lg:grid-cols-5 gap-6">
        <div className="lg:col-span-3"><SubmitVideoForm /></div>
        <div className="lg:col-span-2"><StatsPanel stats={stats} /></div>
      </div>
      <QuickClaimCheck />
      <section className="card p-6">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-bold">Recent analyses</h2>
          <Link to="/history" className="text-sm font-semibold text-navy-600 hover:text-navy-900">View all</Link>
        </div>
        <div className="mt-3">
          {recent === null ? <p className="py-6 text-sm text-navy-400">Loading…</p>
            : recent.length ? <AnalysisList items={recent} />
            : <div className="flex flex-col items-center py-10 text-navy-400"><Inbox className="h-6 w-6" /><p className="mt-2 text-sm">No analyses yet.</p></div>}
        </div>
      </section>
    </div>
  )
}
