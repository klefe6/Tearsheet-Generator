import { describe, expect, it } from 'vitest'
import {
  combinedProgramsWithData,
  filterWarningsForMode,
  getCombinedDayTicks,
  isRoutinePriorCloseWarning,
  partitionChartWarnings,
  programEmptyMessage,
  programNeedsMoreMessage,
  resolveCombinedChartState,
  resolveProgramChartState,
} from './chartState'
import type { CombinedTradingDayPoint, ProgramSeriesPoint } from '../data/performance'

describe('getCombinedDayTicks', () => {
  it('returns unique sorted day indices without duplicates', () => {
    const data: CombinedTradingDayPoint[] = [
      { dayIndex: 0, TCP: 100_000, AGM: 100_000 },
      { dayIndex: 1, TCP: 101_000, AGM: 102_000 },
      { dayIndex: 2, TCP: 103_000 },
    ]
    expect(getCombinedDayTicks(data)).toEqual([0, 1, 2])
  })
})

describe('combinedProgramsWithData', () => {
  it('lists only programs with at least one point', () => {
    const data: CombinedTradingDayPoint[] = [
      { dayIndex: 0, TCP: 100_000 },
      { dayIndex: 1, TCP: 101_000 },
    ]
    expect(combinedProgramsWithData(data)).toEqual(['TCP'])
  })
})

describe('resolveProgramChartState', () => {
  const pts = (n: number): ProgramSeriesPoint[] =>
    Array.from({ length: n }, (_, i) => ({
      date: `2026-07-${10 + i}`,
      TCP: 100_000 + i * 1000,
    }))

  it('empty when backend has zero rows', () => {
    expect(resolveProgramChartState('backend', [], 'TCP')).toBe('empty')
  })

  it('needs_more with one row', () => {
    expect(resolveProgramChartState('backend', pts(1), 'TCP')).toBe('needs_more')
  })

  it('sparse with two rows', () => {
    expect(resolveProgramChartState('backend', pts(2), 'TCP')).toBe('sparse')
  })

  it('ready with three or more rows', () => {
    expect(resolveProgramChartState('backend', pts(3), 'TCP')).toBe('ready')
  })
})

describe('resolveCombinedChartState', () => {
  const data: CombinedTradingDayPoint[] = [
    { dayIndex: 0, TCP: 100_000, AGM: 100_000 },
    { dayIndex: 1, TCP: 101_000, AGM: 102_000 },
    { dayIndex: 2, TCP: 103_000, AGM: 104_000 },
  ]

  it('empty when no visible programs have data', () => {
    expect(resolveCombinedChartState('backend', data, [])).toBe('empty')
  })

  it('ready when visible programs have three points', () => {
    expect(resolveCombinedChartState('backend', data, ['TCP', 'AGM'])).toBe('ready')
  })
})

describe('empty state copy', () => {
  it('uses program-specific empty message', () => {
    expect(programEmptyMessage('TKP')).toMatch(/No TKP entries yet/)
  })

  it('explains benchmarks appear once the strategy has entries', () => {
    expect(programEmptyMessage('TKP')).toMatch(
      /Benchmarks appear after this strategy has entries\./,
    )
  })

  it('needs-more message does not mention normalization', () => {
    expect(programNeedsMoreMessage('TKP', 'July 10, 2026')).toMatch(
      /at least two TKP entries/,
    )
    expect(programNeedsMoreMessage('TKP', 'July 10, 2026')).not.toMatch(/normalized/)
  })
})

describe('filterWarningsForMode', () => {
  it('drops no-data warnings for the active program tab', () => {
    const warnings = ['TKP: no data yet.', 'SPX: aligned fallback.']
    expect(filterWarningsForMode(warnings, 'TKP')).toEqual(['SPX: aligned fallback.'])
  })

  it('drops all no-data warnings in combined mode', () => {
    const warnings = ['TKP: no data yet.', 'YQ: no data yet.', 'TCP: aligned.']
    expect(filterWarningsForMode(warnings, 'combined')).toEqual(['TCP: aligned.'])
  })
})

describe('isRoutinePriorCloseWarning', () => {
  it('matches weekend/holiday prior-close alignment', () => {
    expect(
      isRoutinePriorCloseWarning(
        'SPX: no close on 2026-07-11; used prior close from 2026-07-10 (1d earlier).',
      ),
    ).toBe(true)
    expect(
      isRoutinePriorCloseWarning(
        'NDX has no close on 2026-01-01; rebased from 2026-01-02 instead.',
      ),
    ).toBe(true)
  })

  it('does not match unavailable or mock warnings', () => {
    expect(isRoutinePriorCloseWarning('SPX: no benchmark data available.')).toBe(false)
    expect(isRoutinePriorCloseWarning('Using mock performance fallback.')).toBe(false)
    expect(isRoutinePriorCloseWarning('SPX: no close within 5d before 2026-07-11.')).toBe(false)
  })
})

describe('partitionChartWarnings', () => {
  const priorClose = [
    'SPX: no close on 2026-07-11; used prior close from 2026-07-10 (1d earlier).',
    'NDX: no close on 2026-07-11; used prior close from 2026-07-10 (1d earlier).',
  ]

  it('keeps prior-close warnings out of visible inline list', () => {
    const { visible, diagnostic } = partitionChartWarnings(
      [...priorClose, 'SPX: no benchmark data available.'],
      'combined',
    )
    expect(visible).toEqual(['SPX: no benchmark data available.'])
    expect(diagnostic).toEqual(priorClose)
  })

  it('still surfaces mock/fallback and no-data strategy messages', () => {
    const warnings = [
      'TKP: no data yet.',
      'Using mock performance fallback.',
      ...priorClose,
    ]
    const { visible, diagnostic } = partitionChartWarnings(warnings, 'TKP')
    expect(visible).toEqual(['Using mock performance fallback.'])
    expect(diagnostic).toEqual(priorClose)
  })

  it('filters program no-data warnings in combined mode before partitioning', () => {
    const warnings = ['YQ: no data yet.', ...priorClose, 'TCP: no aligned benchmark points.']
    const { visible, diagnostic } = partitionChartWarnings(warnings, 'combined')
    expect(visible).toEqual(['TCP: no aligned benchmark points.'])
    expect(diagnostic).toEqual(priorClose)
  })
})
