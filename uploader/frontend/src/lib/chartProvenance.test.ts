import { describe, expect, it } from 'vitest'
import {
  combinedModeSubtitle,
  defaultEnabledBenchmarks,
  provenanceNotice,
  readBenchmarkDataSource,
  resolveChartProvenance,
  seriesDisplayLabel,
} from './chartProvenance'

describe('resolveChartProvenance', () => {
  it('prefers backend when response is present', () => {
    expect(resolveChartProvenance({} as never, true)).toBe('backend')
  })

  it('falls back to mock when fetch settled without response', () => {
    expect(resolveChartProvenance(null, true)).toBe('mock')
  })

  it('stays loading until fetch settles', () => {
    expect(resolveChartProvenance(null, false)).toBe('loading')
  })
})

describe('benchmark defaults', () => {
  it('hides synthetic benchmarks by default', () => {
    expect(
      defaultEnabledBenchmarks('backend', 'deterministic_fixture').size,
    ).toBe(0)
  })

  it('hides benchmarks in mock fallback', () => {
    expect(defaultEnabledBenchmarks('mock', null).size).toBe(0)
  })
})

describe('seriesDisplayLabel', () => {
  it('marks fixture benchmarks as sample', () => {
    expect(seriesDisplayLabel('SPX', 'backend', 'deterministic_fixture')).toBe(
      'SPX (sample)',
    )
  })

  it('marks mock product lines as preview', () => {
    expect(seriesDisplayLabel('TKP', 'mock', null)).toBe('TKP (preview)')
  })

  it('keeps backend product labels plain', () => {
    expect(seriesDisplayLabel('TCP', 'backend', null)).toBe('TCP')
  })
})

describe('provenanceNotice', () => {
  it('warns on mock fallback', () => {
    expect(provenanceNotice('mock', 'combined', null)).toMatch(/Preview chart/)
  })

  it('states uploader source on backend combined', () => {
    expect(provenanceNotice('backend', 'combined', null)).toMatch(/uploader entries/)
  })

  it('states sample benchmarks in program mode', () => {
    expect(provenanceNotice('backend', 'TKP', 'deterministic_fixture')).toMatch(
      /sample benchmarks/,
    )
  })
})

describe('readBenchmarkDataSource', () => {
  it('reads fixture flag from API', () => {
    expect(
      readBenchmarkDataSource({
        benchmark_data_source: 'deterministic_fixture',
      } as never),
    ).toBe('deterministic_fixture')
  })
})

describe('combinedModeSubtitle', () => {
  it('labels mock as preview demo', () => {
    expect(combinedModeSubtitle('mock')).toMatch(/Preview demo/)
  })
})
