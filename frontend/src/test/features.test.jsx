import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import ClaimCard from '../components/analysis/ClaimCard.jsx'
import { TrustBadge } from '../components/analysis/EvidencePanel.jsx'
import { verdictLabel } from '../utils/format.js'

vi.mock('@xyflow/react', () => ({ ReactFlow: () => null, Background: () => null, Controls: () => null, MiniMap: () => null,
  Handle: () => null, MarkerType: { ArrowClosed: 'arrowclosed' }, Position: { Left: 'left', Right: 'right' } }))
vi.mock('@xyflow/react/dist/style.css', () => ({}))
const { layout } = await import('../pages/GraphPage.jsx')

const TRUST = {
  score: 0.82, level: 'high', metadata_checked: true,
  signals: [
    { signal: 'publisher', score: 0.9, value: 'cdc.gov', reason: 'Government publisher' },
    { signal: 'corroboration', score: 1, value: '2 other independent site(s) agree', reason: 'Independently corroborated' },
  ],
}

describe('TrustBadge', () => {
  it('shows level and reveals the reasons', () => {
    render(<TrustBadge trust={TRUST} fallback="General web" />)
    fireEvent.click(screen.getByRole('button', { name: /Trust: high \(82\)/ }))
    expect(screen.getByText(/Independently corroborated/)).toBeInTheDocument()
    expect(screen.getByText(/never the whole score/)).toBeInTheDocument()
  })
  it('falls back to the publisher tier when no assessment exists', () => {
    render(<TrustBadge trust={null} fallback="Reference" />)
    expect(screen.getByText('Reference')).toBeInTheDocument()
  })
})

describe('ClaimCard multilingual + context', () => {
  const claim = {
    id: 'c1', code: 'CLM001', text: 'భారతదేశ జనాభా 140 కోట్లు దాటింది', text_en: 'India’s population has crossed 1.4 billion',
    language: 'te', original_quote: 'భారతదేశ జనాభా 140 కోట్లు దాటింది', start: 12, end: 18, claim_type: 'statistical',
    verification: { verdict: 'verified', confidence: 0.8, explanation: 'Census estimates agree [E1].', adjusted: false },
    evidence: [],
    context_analysis: { risk: 'medium', missing_context: 'Figure is an estimate, not a census count.',
      flags: [{ type: 'out_of_context', label: 'Taken out of context', explanation: 'Next sentence qualifies it.',
        transcript_quote: 'but that is an estimate', start: 19 }] },
  }

  it('shows original, English, translated verdict label and context flags', () => {
    const onSeek = vi.fn()
    render(<ClaimCard claim={claim} index={0} onSeek={onSeek} lang="te"
      translation={{ text: { text: 'భారతదేశ జనాభా 140 కోట్లు', translated: false }, explanation: { text: 'జనాభా అంచనాలు [E1].', translated: true } }} />)
    expect(screen.getByText('CLM001')).toBeInTheDocument()
    expect(screen.getByText(/India’s population has crossed 1.4 billion/)).toBeInTheDocument()
    expect(screen.getByText(verdictLabel('verified', 'te'))).toBeInTheDocument()
    expect(screen.getByText(/జనాభా అంచనాలు/)).toBeInTheDocument()
    expect(screen.getByText('Taken out of context:')).toBeInTheDocument()
    fireEvent.click(screen.getByText(/but that is an estimate/))
    expect(onSeek).toHaveBeenCalledWith(19)
  })
})

describe('Evidence graph layout', () => {
  it('places nodes in columns and colours claims by verdict', () => {
    const graph = { nodes: [
      { id: 'video:v', type: 'video', label: 'V', data: {} },
      { id: 'claim:a', type: 'claim', label: 'CLM001', data: { verdict: 'false', start: 10, text: 'x' } },
      { id: 'source:u', type: 'source', label: 'nasa.gov', data: { trust_level: 'high' } },
    ], edges: [] }
    const nodes = layout(graph, 'claim:a')
    const pos = Object.fromEntries(nodes.map((n) => [n.id, n.position.x]))
    expect(pos['video:v']).toBeLessThan(pos['claim:a'])
    expect(pos['claim:a']).toBeLessThan(pos['source:u'])
    const claim = nodes.find((n) => n.id === 'claim:a')
    expect(claim.data.border).toBe('#dc2626')
    expect(claim.data.selected).toBe(true)
  })
})
