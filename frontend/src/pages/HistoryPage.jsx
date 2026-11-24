import { History, Search } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { analysisApi } from '../api/endpoints.js'
import AnalysisList from '../components/dashboard/AnalysisList.jsx'
import { Button, EmptyState, ErrorBanner, Spinner } from '../components/ui/index.jsx'

const PAGE_SIZE = 10
const FILTERS = [['', 'All'], ['completed', 'Completed'], ['failed', 'Failed']]

export default function HistoryPage() {
  const [page, setPage] = useState(1)
  const [status, setStatus] = useState('')
  const [q, setQ] = useState('')
  const [query, setQuery] = useState('')
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  const [reloadKey, setReloadKey] = useState(0)

  useEffect(() => {
    const t = setTimeout(() => { setQuery(q); setPage(1) }, 300)
    return () => clearTimeout(t)
  }, [q])

  useEffect(() => {
    let cancelled = false
    analysisApi.list({ page, pageSize: PAGE_SIZE, status: status || undefined, q: query || undefined })
      .then((d) => !cancelled && (setData(d), setError(null)))
      .catch((e) => !cancelled && setError(e))
    return () => { cancelled = true }
  }, [page, status, query, reloadKey])

  const onDelete = async (item) => {
    if (!window.confirm(`Delete "${item.title}" and its results?`)) return
    try { await analysisApi.remove(item.video_id); setReloadKey((k) => k + 1) } catch (e) { setError(e) }
  }

  const pages = data ? Math.max(1, Math.ceil(data.total / PAGE_SIZE)) : 1

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <div>
        <h1 className="text-2xl font-extrabold">Analysis history</h1>
        <p className="text-sm text-navy-500">Every video you've checked, newest first.</p>
      </div>
      <div className="flex flex-col sm:flex-row gap-3">
        <div className="relative flex-1">
          <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 h-4 w-4 text-navy-300" />
          <input className="input pl-10" placeholder="Search by title" value={q} onChange={(e) => setQ(e.target.value)} aria-label="Search analyses" />
        </div>
        <div className="flex gap-1 rounded-xl bg-white border border-navy-200 p-1">
          {FILTERS.map(([v, label]) => (
            <button key={v} onClick={() => { setStatus(v); setPage(1) }}
              className={`rounded-lg px-3 py-1.5 text-sm font-medium ${status === v ? 'bg-navy-900 text-white' : 'text-navy-600 hover:bg-navy-50'}`}>{label}</button>
          ))}
        </div>
      </div>
      <ErrorBanner error={error} />
      {!data ? <Spinner /> : data.items.length === 0 ? (
        <EmptyState icon={History} title={query || status ? 'No matching analyses' : 'Nothing here yet'}
          action={<Button as={Link} to="/dashboard">Analyse a video</Button>}>
          {query || status ? 'Try a different search or filter.' : 'Submit your first video from the dashboard.'}
        </EmptyState>
      ) : (
        <div className="card p-4">
          <AnalysisList items={data.items} onDelete={onDelete} />
          {pages > 1 && (
            <div className="mt-4 flex items-center justify-between border-t border-navy-100 pt-4 text-sm">
              <Button variant="secondary" disabled={page <= 1} onClick={() => setPage(page - 1)}>Previous</Button>
              <span className="text-navy-500">Page {page} of {pages}</span>
              <Button variant="secondary" disabled={page >= pages} onClick={() => setPage(page + 1)}>Next</Button>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
