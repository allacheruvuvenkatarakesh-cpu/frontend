import { describe, expect, it } from 'vitest'
import { confidenceLabel, formatTime, isActive, splitCitations, verdictMeta } from '../utils/format.js'

describe('format utils', () => {
  it('formats timestamps', () => {
    expect(formatTime(0)).toBe('0:00')
    expect(formatTime(75.9)).toBe('1:15')
    expect(formatTime(3725)).toBe('1:02:05')
    expect(formatTime(null)).toBe('--:--')
  })

  it('maps verdicts with a safe fallback', () => {
    expect(verdictMeta('false').label).toBe('False')
    expect(verdictMeta('nonsense').label).toBe('Insufficient Evidence')
  })

  it('splits citations', () => {
    expect(splitCitations('Astronauts say no [E1][E2].')).toEqual([
      { text: 'Astronauts say no ' }, { cite: 1 }, { cite: 2 }, { text: '.' },
    ])
  })

  it('labels confidence', () => {
    expect(confidenceLabel(null)).toBe('Not enough evidence')
    expect(confidenceLabel(0.8)).toBe('High')
    expect(confidenceLabel(0.3)).toBe('Low')
  })

  it('knows active statuses', () => {
    expect(isActive('verifying')).toBe(true)
    expect(isActive('completed')).toBe(false)
  })
})
