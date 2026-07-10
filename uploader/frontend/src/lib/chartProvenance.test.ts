import { describe, expect, it } from 'vitest'
import {
  combinedModeSubtitle,
  defaultEnabledBenchmarks,
  hasBackfilledHistory,
  isRealBenchmarkSource,
  programModeSubtitle,
  provenanceNotice,
  readBenchmarkDataSource,
  readProgramDataSource,
  resolveChartProvenance,
  seriesDisplayLabel,
  showBenchmarkToggles,
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

  it('enables SPX+NDX when market cache is confirmed', () => {
    const enabled = defaultEnabledBenchmarks('backend', 'market_cache_cached')
    expect(enabled.has('SPX')).toBe(true)
    expect(enabled.has('NDX')).toBe(true)
    expect(enabled.has('BTC')).toBe(false)
  })

  it('hides benchmarks when unavailable', () => {
    expect(defaultEnabledBenchmarks('backend', 'unavailable').size).toBe(0)
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

  it('uses plain labels for cached market benchmarks', () => {
    expect(seriesDisplayLabel('SPX', 'backend', 'market_cache_cached')).toBe('SPX')
    expect(seriesDisplayLabel('BTC', 'backend', 'market_cache_live_fetch')).toBe('BTC')
  })

  it('marks mock product lines as preview', () => {
    expect(seriesDisplayLabel('TKP', 'mock', null)).toBe('TKP (preview)')
  })

  it('keeps backend product labels plain', () => {
    expect(seriesDisplayLabel('TCP', 'backend', 'market_cache_cached')).toBe('TCP')
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

  it('states cached market benchmarks when real', () => {
    expect(provenanceNotice('backend', 'TKP', 'market_cache_cached')).toMatch(
      /cached market closes/,
    )
  })

  it('states unavailable benchmarks clearly', () => {
    expect(provenanceNotice('backend', 'TKP', 'unavailable')).toMatch(/unavailable/)
  })

  it('keeps uploader-only wording when no backfill is present', () => {
    expect(provenanceNotice('backend', 'combined', null, 'uploader_daily_rows')).toBe(
      'Strategy lines reflect uploader entries only.',
    )
  })

  it('states historical tearsheet backfill in combined mode when backfilled', () => {
    expect(
      provenanceNotice(
        'backend',
        'combined',
        null,
        'uploader_daily_rows+tearsheet_backfill',
      ),
    ).toBe('Strategy lines include historical tearsheet backfill plus uploader entries.')
  })

  it('states historical tearsheet backfill in program mode when backfilled', () => {
    const notice = provenanceNotice(
      'backend',
      'TKP',
      'market_cache_cached',
      'uploader_daily_rows+tearsheet_backfill',
    )
    expect(notice).toMatch(/includes historical tearsheet backfill plus uploader entries/)
    expect(notice).toMatch(/cached market closes/)
  })
})

describe('readProgramDataSource / hasBackfilledHistory', () => {
  it('reads both known values and rejects unknowns', () => {
    expect(
      readProgramDataSource({ program_data_source: 'uploader_daily_rows' } as never),
    ).toBe('uploader_daily_rows')
    expect(
      readProgramDataSource({
        program_data_source: 'uploader_daily_rows+tearsheet_backfill',
      } as never),
    ).toBe('uploader_daily_rows+tearsheet_backfill')
    expect(readProgramDataSource({ program_data_source: 'weird' } as never)).toBeNull()
    expect(readProgramDataSource(null)).toBeNull()
  })

  it('flags backfill only for the backfill source', () => {
    expect(hasBackfilledHistory('uploader_daily_rows+tearsheet_backfill')).toBe(true)
    expect(hasBackfilledHistory('uploader_daily_rows')).toBe(false)
    expect(hasBackfilledHistory(null)).toBe(false)
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

  it('reads market cache flags from API', () => {
    expect(
      readBenchmarkDataSource({
        benchmark_data_source: 'market_cache_cached',
      } as never),
    ).toBe('market_cache_cached')
  })
})

describe('showBenchmarkToggles', () => {
  it('hides toggles when backend reports unavailable', () => {
    expect(showBenchmarkToggles('backend', 'unavailable')).toBe(false)
  })

  it('hides toggles when program has no rows', () => {
    expect(showBenchmarkToggles('backend', 'market_cache_cached', false)).toBe(false)
  })

  it('hides toggles when backend returns no benchmark source', () => {
    expect(showBenchmarkToggles('backend', null)).toBe(false)
  })

  it('shows toggles for cached market data with rows', () => {
    expect(showBenchmarkToggles('backend', 'market_cache_cached', true)).toBe(true)
  })
})

describe('isRealBenchmarkSource', () => {
  it('accepts live fetch and cached', () => {
    expect(isRealBenchmarkSource('market_cache_live_fetch')).toBe(true)
    expect(isRealBenchmarkSource('market_cache_cached')).toBe(true)
    expect(isRealBenchmarkSource('deterministic_fixture')).toBe(false)
  })
})

describe('combinedModeSubtitle', () => {
  it('labels mock as preview demo', () => {
    expect(combinedModeSubtitle('mock')).toMatch(/Preview demo/)
  })

  it('says first uploader entry without backfill', () => {
    expect(combinedModeSubtitle('backend', 'uploader_daily_rows')).toMatch(
      /first uploader entry/,
    )
  })

  it('says first recorded entry with backfill', () => {
    expect(
      combinedModeSubtitle('backend', 'uploader_daily_rows+tearsheet_backfill'),
    ).toMatch(/first recorded entry/)
  })
})

describe('programModeSubtitle', () => {
  const fmt = (iso: string) => iso

  it('returns null when backend has zero rows (no contradictory normalized copy)', () => {
    expect(
      programModeSubtitle('TKP', 'backend', [], '2026-01-01', fmt, null, 0),
    ).toBeNull()
  })

  it('returns null when backend has one row', () => {
    expect(
      programModeSubtitle(
        'TKP',
        'backend',
        [{ date: '2026-07-10' }],
        '2026-01-01',
        fmt,
        null,
        1,
      ),
    ).toBeNull()
  })

  it('does not mention sample benchmarks when backend source is null', () => {
    const sub = programModeSubtitle(
      'TCP',
      'backend',
      [{ date: '2026-07-10' }, { date: '2026-07-11' }],
      '2026-01-01',
      fmt,
      null,
      2,
    )
    expect(sub).toMatch(/normalized/)
    expect(sub).not.toMatch(/sample/)
  })

  it('mentions cached market closes for real benchmark source', () => {
    expect(
      programModeSubtitle(
        'TCP',
        'backend',
        [{ date: '2026-07-10' }, { date: '2026-07-11' }],
        '2026-01-01',
        fmt,
        'market_cache_live_fetch',
        2,
      ),
    ).toMatch(/cached market closes/)
  })

  it('says first recorded entry when backfilled history is present', () => {
    const sub = programModeSubtitle(
      'TKP',
      'backend',
      [{ date: '2026-07-10' }, { date: '2026-07-11' }],
      '2026-01-01',
      fmt,
      null,
      2,
      'uploader_daily_rows+tearsheet_backfill',
    )
    expect(sub).toMatch(/first recorded entry/)
    expect(sub).toMatch(/imported tearsheet history/)
  })
})
