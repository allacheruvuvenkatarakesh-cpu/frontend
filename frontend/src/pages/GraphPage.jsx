import { Background, Controls, Handle, MarkerType, MiniMap, Position, ReactFlow } from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import { ArrowLeft, ExternalLink, Network } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { featureApi } from '../api/endpoints.js'
import { EmptyState, Spinner, VerdictBadge } from '../components/ui/index.jsx'
import { formatTime, verdictMeta } from '../utils/format.js'

export const EDGE_STYLE = {
  makes: { stroke: '#c4d1e5', label: '' },
  supports: { stroke: '#16a34a', label: 'supports' },
  refutes: { stroke: '#dc2626', label: 'refutes' },
  mixed: { stroke: '#eab308', label: 'mixed' },
  contradicts: { stroke: '#dc2626', label: 'contradicts', dash: '6 4' },
  shares_source: { stroke: '#9ca3af', label: 'same source', dash: '3 3' },
  related: { stroke: '#6482b5', label: 'other video', dash: '5 4' },
}

function Box({ data }) {
  return (
    <div className={`rounded-xl border bg-white px-3 py-2 text-xs shadow-card ${data.selected ? 'ring-2 ring-navy-700' : ''}`}
      style={{ borderColor: data.border || '#c4d1e5', width: data.width || 200 }}>
      <Handle type="target" position={Position.Left} style={{ opacity: 0 }} />
      <div className="font-semibold text-navy-900 line-clamp-2">{data.title}</div>
      {data.subtitle && <div className="mt-0.5 text-navy-500 line-clamp-2">{data.subtitle}</div>}
      <Handle type="source" position={Position.Right} style={{ opacity: 0 }} />
    </div>
  )
}
const nodeTypes = { box: Box }

/** Columns: related claims (other videos) | video | claims | sources. */
export function layout(graph, selectedId) {
  const by = (t) => graph.nodes.filter((n) => n.type === t)
  const col = { related_claim: 0, video: 1, claim: 2, source: 3 }
  const x = [-40, 260, 560, 920]
  const out = []
  for (const [type, ci] of Object.entries(col)) {
    const list = by(type)
    const gap = type === 'claim' ? 96 : 76
    const top = -((list.length - 1) * gap) / 2
    list.forEach((n, i) => {
      const verdict = n.data?.verdict
      const border = type === 'claim' || type === 'related_claim' ? verdictMeta(verdict).color
        : type === 'video' ? '#14213d' : n.data?.trust_level === 'high' ? '#16a34a' : n.data?.trust_level === 'low' ? '#f97316' : '#c4d1e5'
      const title = type === 'claim' ? `${n.label} · ${formatTime(n.data.start)}` : n.label
      const subtitle = type === 'claim' ? (n.data.text_en || n.data.text) : type === 'source' ? (n.data.title || '')
        : type === 'related_claim' ? n.data.text : ''
      out.push({ id: n.id, type: 'box', position: { x: x[ci], y: top + i * gap },
        data: { title, subtitle, border, width: type === 'claim' ? 260 : 200, selected: n.id === selectedId, raw: n } })
    })
  }
  return out
}

export default function GraphPage() {
  const { videoId } = useParams()
  const [graph, setGraph] = useState(null)
  const [error, setError] = useState(null)
  const [selected, setSelected] = useState(null)
  const [hidden, setHidden] = useState({ makes: false, shares_source: false, related: false })

  useEffect(() => { featureApi.graph(videoId).then(setGraph).catch(setError) }, [videoId])

  const nodes = useMemo(() => (graph ? layout(graph, selected?.id) : []), [graph, selected])
  const edges = useMemo(() => (graph ? graph.edges.filter((e) => !hidden[e.type]).map((e) => {
    const st = EDGE_STYLE[e.type] || EDGE_STYLE.makes
    return { id: e.id, source: e.source, target: e.target, label: st.label, animated: e.type === 'contradicts',
      style: { stroke: st.stroke, strokeWidth: e.type === 'makes' ? 1 : 2, strokeDasharray: st.dash },
      labelStyle: { fontSize: 10, fill: st.stroke }, markerEnd: { type: MarkerType.ArrowClosed, color: st.stroke } }
  }) : []), [graph, hidden])

  if (error) return <EmptyState icon={Network} title="Couldn't build the graph">{error.message}</EmptyState>
  if (!graph) return <Spinner label="Building evidence graph…" />

  const sel = selected?.data?.raw
  const connected = sel ? graph.edges.filter((e) => e.source === sel.id || e.target === sel.id) : []

  return (
    <div className="mx-auto max-w-7xl space-y-4">
      <Link to={`/analysis/${videoId}`} className="inline-flex items-center gap-1 text-sm text-navy-500 hover:text-navy-900"><ArrowLeft className="h-4 w-4" />Back to analysis</Link>
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="flex items-center gap-2 text-2xl font-extrabold"><Network className="h-6 w-6" />Evidence graph</h1>
          <p className="text-sm text-navy-500">
            {graph.stats.claim || 0} claims · {graph.stats.source || 0} sources · {graph.stats.related_claim || 0} related claims in your other videos
          </p>
        </div>
        <div className="flex flex-wrap gap-2 text-xs">
          {[['makes', 'Video links'], ['shares_source', 'Shared sources'], ['related', 'Other videos']].map(([k, label]) => (
            <label key={k} className="inline-flex items-center gap-1.5 rounded-lg border border-navy-200 bg-white px-2 py-1">
              <input type="checkbox" checked={!hidden[k]} onChange={() => setHidden({ ...hidden, [k]: !hidden[k] })} />{label}
            </label>
          ))}
        </div>
      </div>
      <div className="grid lg:grid-cols-4 gap-4">
        <div className="lg:col-span-3 card h-[640px] overflow-hidden" aria-label="Evidence relationship graph">
          <ReactFlow nodes={nodes} edges={edges} nodeTypes={nodeTypes} fitView minZoom={0.2}
            onNodeClick={(_, n) => setSelected(n)} onPaneClick={() => setSelected(null)} proOptions={{ hideAttribution: true }}>
            <Background color="#e1e8f2" gap={24} />
            <MiniMap pannable zoomable nodeColor={(n) => n.data.border} />
            <Controls showInteractive={false} />
          </ReactFlow>
        </div>
        <aside className="card p-4 text-sm h-fit">
          {!sel ? (
            <>
              <h2 className="font-bold">How to read it</h2>
              <ul className="mt-2 space-y-1.5 text-navy-600">
                {Object.entries(EDGE_STYLE).filter(([k]) => k !== 'makes').map(([k, st]) => (
                  <li key={k} className="flex items-center gap-2"><span className="h-0.5 w-6" style={{ background: st.stroke }} />{st.label}</li>
                ))}
              </ul>
              <p className="mt-3 text-xs text-navy-400">Click a claim or source to see its connections. Source borders show trust: green high, orange low.</p>
            </>
          ) : (
            <>
              <div className="text-xs font-semibold uppercase text-navy-400">{sel.type.replace('_', ' ')}</div>
              {sel.type === 'claim' && (<>
                <div className="mt-1"><VerdictBadge verdict={sel.data.verdict} /></div>
                <p className="mt-2 font-semibold">{sel.data.text}</p>
                <Link className="mt-2 inline-block text-navy-700 underline" to={`/analysis/${videoId}?claim=${sel.data.claim_id}`}>Open at {formatTime(sel.data.start)}</Link>
              </>)}
              {sel.type === 'source' && (<>
                <p className="mt-1 font-semibold">{sel.data.title || sel.label}</p>
                <a className="mt-1 inline-flex items-center gap-1 text-navy-700 underline break-all" href={sel.data.url} target="_blank" rel="noopener noreferrer">{sel.label}<ExternalLink className="h-3 w-3" /></a>
                {sel.data.trust_level && <p className="mt-1 text-xs text-navy-500">Trust: {sel.data.trust_level}</p>}
              </>)}
              {sel.type === 'related_claim' && (<>
                <p className="mt-1 font-semibold">{sel.data.text}</p>
                <div className="mt-1"><VerdictBadge verdict={sel.data.verdict} /></div>
                <Link className="mt-2 inline-block text-navy-700 underline" to={`/analysis/${sel.data.video_id}?claim=${sel.data.claim_id}`}>Open in {sel.label}</Link>
              </>)}
              {sel.type === 'video' && <p className="mt-1 font-semibold">{sel.label}</p>}
              <div className="mt-3 text-xs text-navy-500">{connected.length} connection{connected.length === 1 ? '' : 's'}:</div>
              <ul className="mt-1 space-y-1 text-xs">
                {connected.slice(0, 12).map((e) => <li key={e.id}><span style={{ color: (EDGE_STYLE[e.type] || {}).stroke }}>{e.type.replace('_', ' ')}</span>{e.data?.quote ? `: “${e.data.quote}”` : ''}</li>)}
              </ul>
            </>
          )}
        </aside>
      </div>
    </div>
  )
}
