import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import ClaimCard from '../components/analysis/ClaimCard.jsx'
import TruthTimeline from '../components/analysis/TruthTimeline.jsx'
import SubmitVideoForm from '../components/dashboard/SubmitVideoForm.jsx'

vi.mock('../api/endpoints.js', () => ({
  videoApi: { submitUrl: vi.fn(), upload: vi.fn() },
}))
const { videoApi } = await import('../api/endpoints.js')

const navigate = vi.fn()
vi.mock('react-router-dom', async (orig) => ({ ...(await orig()), useNavigate: () => navigate }))

const ITEMS = [
  { claim_id: 'a', start: 10, end: 15, verdict: 'false', color: '#dc2626', label: 'False', text: 'Great Wall visible from Moon' },
  { claim_id: 'b', start: 40, end: 44, verdict: 'verified', color: '#16a34a', label: 'Verified', text: 'Everest is highest' },
]

describe('TruthTimeline', () => {
  it('renders one segment per claim and reports clicks', () => {
    const onSelect = vi.fn()
    render(<TruthTimeline items={ITEMS} duration={60} onSelect={onSelect} />)
    const segs = within(screen.getByRole('list', { name: /Claims along the video timeline/ })).getAllByRole('listitem')
    expect(segs).toHaveLength(2)
    fireEvent.click(screen.getByLabelText(/0:40 — Verified/))
    expect(onSelect).toHaveBeenCalledWith(ITEMS[1])
  })
})

describe('ClaimCard', () => {
  const claim = {
    id: 'c1', text: 'Humans use only ten percent of their brains.', original_quote: 'we only use ten percent',
    start: 24, end: 30, claim_type: 'scientific', checkworthiness: 0.8,
    verification: { verdict: 'false', label: 'False', color: '#dc2626', confidence: 0.84, explanation: 'Brain imaging shows otherwise [E1].', adjusted: false },
    evidence: [{ id: 'e1', title: 'Ten percent myth', url: 'https://en.wikipedia.org/wiki/Ten_percent_of_the_brain_myth',
      source_name: 'Wikipedia', snippet: 'A myth.', stance: 'refutes', quote: 'It is a myth.', relevance: 0.8, credibility: 0.7 }],
  }

  it('shows verdict, confidence, and seeks on timestamp click', () => {
    const onSeek = vi.fn()
    render(<ClaimCard claim={claim} index={0} onSeek={onSeek} />)
    expect(screen.getByText('False')).toBeInTheDocument()
    expect(screen.getByText('84%')).toBeInTheDocument()
    fireEvent.click(screen.getByLabelText('Play from 0:24'))
    expect(onSeek).toHaveBeenCalledWith(24)
  })

  it('opens evidence when a citation is clicked', () => {
    render(<ClaimCard claim={claim} index={0} />)
    fireEvent.click(screen.getByRole('button', { name: 'E1' }))
    expect(screen.getByText('Ten percent myth')).toBeInTheDocument()
    expect(screen.getByText(/It is a myth/)).toBeInTheDocument()
  })
})

describe('SubmitVideoForm', () => {
  it('submits a URL and navigates to the analysis', async () => {
    videoApi.submitUrl.mockResolvedValue({ id: 'vid123' })
    render(<MemoryRouter><SubmitVideoForm /></MemoryRouter>)
    fireEvent.change(screen.getByLabelText('Video URL'), { target: { value: 'https://youtu.be/abc' } })
    fireEvent.click(screen.getByRole('button', { name: 'Start analysis' }))
    await waitFor(() => expect(navigate).toHaveBeenCalledWith('/analysis/vid123'))
    expect(videoApi.submitUrl).toHaveBeenCalledWith('https://youtu.be/abc', '')
  })

  it('shows server errors', async () => {
    videoApi.submitUrl.mockRejectedValue(new Error('Unsupported link'))
    render(<MemoryRouter><SubmitVideoForm /></MemoryRouter>)
    fireEvent.change(screen.getByLabelText('Video URL'), { target: { value: 'https://example.com/x' } })
    fireEvent.click(screen.getByRole('button', { name: 'Start analysis' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Unsupported link')
  })
})
