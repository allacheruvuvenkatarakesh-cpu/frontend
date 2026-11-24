import { fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import TruthFingerprintCard from '../components/fingerprint/TruthFingerprintCard.jsx'
import { MatchCard } from '../pages/ComparePage.jsx'

const FP = {
  fingerprint_id: 'LTS-1A2B-3C4D-5E6F', content_hash: '9f86d081884c7d65',
  video: { id: 'va', title: 'Myths', duration: 52 }, total_claims: 4,
  counts: { verified: 1, false: 2, misleading: 0, unverified: 1 }, truth_score: 41, overall_rating: 'Mixed Accuracy',
  evidence_quality: { score: 61.2, grade: 'C', label: 'Moderate', coverage: 0.75, avg_credibility: 0.75,
    source_diversity: 0.42, avg_confidence: 0.84, grounded_sources: 4, distinct_domains: 2, fact_checker_sources: 0 },
  timestamps: [
    { claim_id: 'a1', start: 10.8, end: 17.5, verdict: 'false' },
    { claim_id: 'a2', start: 17.5, end: 23.9, verdict: 'verified' },
  ],
  claims: [{ claim_id: 'a1', confidence: 0.86 }, { claim_id: 'a2', confidence: 0.82 }],
  versions: [
    { version: 1, content_hash: 'aaaa', verified_at: '2026-11-24T10:00:00Z', truth_score: 30, evidence_grade: 'D', changes: null },
    { version: 2, content_hash: '9f86d081884c7d65', verified_at: '2026-11-24T12:00:00Z', truth_score: 41, evidence_grade: 'C',
      changes: { unchanged: false, verdict_changes: [{ text: 'Water boils at 100 °C', from: 'unverified', to: 'verified', start: 41 }],
        added_claims: [], removed_claims: [] } },
  ],
}

describe('TruthFingerprintCard', () => {
  it('shows id, counts, evidence grade, timestamps and history', () => {
    const onSeek = vi.fn()
    render(<MemoryRouter><TruthFingerprintCard fingerprint={FP} onSeek={onSeek} /></MemoryRouter>)
    expect(screen.getByText('LTS-1A2B-3C4D-5E6F')).toBeInTheDocument()
    expect(screen.getByText('4')).toBeInTheDocument()
    expect(screen.getByText(/Moderate · 61\/100/)).toBeInTheDocument()
    fireEvent.click(screen.getByLabelText('Jump to 0:10 (False)'))
    expect(onSeek).toHaveBeenCalledWith(FP.timestamps[0])
    expect(screen.getByText(/1 verdict change/)).toBeInTheDocument()
    fireEvent.click(screen.getByText(/1 verdict change/))
    expect(screen.getByText((_, el) => el?.tagName === 'LI' && !el.querySelector('li') && el.textContent.includes('Water boils at 100 °C'))).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /Compare with another video/ })).toHaveAttribute('href', '/compare?a=va')
  })
})

describe('MatchCard', () => {
  it('flags conflicting claims, figure differences and a source used both ways', () => {
    const m = {
      claim_a: { claim_id: 'a1', text: 'The Great Wall is visible from the Moon.', start: 10.8, end: 17.5, verdict: 'false', confidence: 0.86 },
      claim_b: { claim_id: 'b1', text: 'The Great Wall cannot be seen from the Moon.', start: 5, end: 12, verdict: 'verified', confidence: 0.8 },
      similarity: 0.88, match_method: 'semantic', relation: 'conflict', relation_label: 'Conflicting', contradictory: true,
      different_figures: { video_a: ['8849'], video_b: ['8848'] },
      evidence: { relation: 'same_evidence', label: 'Same evidence', url_overlap: 1, domain_overlap: 1,
        shared_sources: [{ url: 'https://en.wikipedia.org/wiki/Great_Wall_of_China', domain: 'en.wikipedia.org', stance_a: 'refutes', stance_b: 'supports' }],
        only_a: [], only_b: [], stance_conflicts: [{}] },
      insight: 'The videos conflict.',
    }
    render(<MemoryRouter><MatchCard m={m} a="va" b="vb" /></MemoryRouter>)
    expect(screen.getByText('Conflicting')).toBeInTheDocument()
    expect(screen.getByText(/Different figures: 8849 vs 8848/)).toBeInTheDocument()
    expect(screen.getByText('en.wikipedia.org')).toBeInTheDocument()
    expect(screen.getByLabelText('Open video A at 0:10')).toHaveAttribute('href', '/analysis/va?claim=a1')
    expect(screen.getByText('100% of sources shared')).toBeInTheDocument()
  })
})
