/**
 * Chart data provenance helpers — pure functions for truthful UI labeling.
 * See backend/docs/PERFORMANCE_PROVENANCE.md for the full contract.
 */

import type { ApiPerformanceResponse } from '../api/client'
import type { BenchmarkKey, ChartMode, ProductKey, SeriesKey } from '../data/performance'
import { BENCHMARK_KEYS, PRODUCT_KEYS, SERIES } from '../data/performance'

export type ChartProvenance = 'loading' | 'backend' | 'mock'

export type BenchmarkDataSource =
  | 'deterministic_fixture'
  | 'market_cache_live_fetch'
  | 'market_cache_cached'
  | 'unavailable'
  | null

/** Where the strategy lines' rows came from (backend `program_data_source`). */
export type ProgramDataSource =
  | 'uploader_daily_rows'
  | 'uploader_daily_rows+tearsheet_backfill'
  | null

const SERIES_LABEL = new Map(SERIES.map((s) => [s.key, s.label]))

/** Whether strategy/benchmark lines came from the API or local mock builders. */
export function resolveChartProvenance(
  response: ApiPerformanceResponse | null,
  fetchSettled: boolean,
): ChartProvenance {
  if (!fetchSettled) return 'loading'
  return response ? 'backend' : 'mock'
}

export function readBenchmarkDataSource(
  response: ApiPerformanceResponse | null,
): BenchmarkDataSource {
  const raw = response?.benchmark_data_source
  if (!raw) return null
  if (
    raw === 'deterministic_fixture' ||
    raw === 'market_cache_live_fetch' ||
    raw === 'market_cache_cached' ||
    raw === 'unavailable'
  ) {
    return raw
  }
  return null
}

export function readProgramDataSource(
  response: ApiPerformanceResponse | null,
): ProgramDataSource {
  const raw = response?.program_data_source
  if (raw === 'uploader_daily_rows' || raw === 'uploader_daily_rows+tearsheet_backfill') {
    return raw
  }
  return null
}

/** True when any plotted strategy point was backfilled from tearsheet history. */
export function hasBackfilledHistory(source: ProgramDataSource): boolean {
  return source === 'uploader_daily_rows+tearsheet_backfill'
}

export function isRealBenchmarkSource(source: BenchmarkDataSource): boolean {
  return source === 'market_cache_live_fetch' || source === 'market_cache_cached'
}

export function benchmarksAreSynthetic(
  provenance: ChartProvenance,
  benchmarkSource: BenchmarkDataSource,
): boolean {
  return provenance === 'mock' || benchmarkSource === 'deterministic_fixture'
}

export function benchmarksAreUnavailable(benchmarkSource: BenchmarkDataSource): boolean {
  return benchmarkSource === 'unavailable'
}

/** Benchmarks hidden by default unless real/cached market data is confirmed. */
export function defaultEnabledBenchmarks(
  provenance: ChartProvenance,
  benchmarkSource: BenchmarkDataSource,
): Set<BenchmarkKey> {
  if (provenance === 'mock') return new Set()
  if (benchmarksAreUnavailable(benchmarkSource)) return new Set()
  if (benchmarksAreSynthetic(provenance, benchmarkSource)) return new Set()
  if (isRealBenchmarkSource(benchmarkSource)) return new Set(['SPX', 'NDX'])
  return new Set()
}

export function provenanceNotice(
  provenance: ChartProvenance,
  mode: ChartMode,
  benchmarkSource: BenchmarkDataSource,
  programDataSource: ProgramDataSource = null,
): string | null {
  if (provenance === 'loading') return null
  if (provenance === 'mock') {
    return 'Preview chart — demo data only. Connect the uploader backend to show strategy lines from your entries.'
  }
  const backfilled = hasBackfilledHistory(programDataSource)
  if (mode === 'combined') {
    return backfilled
      ? 'Strategy lines include historical tearsheet backfill plus uploader entries.'
      : 'Strategy lines reflect uploader entries only.'
  }
  const strategyLead = backfilled
    ? 'Strategy line includes historical tearsheet backfill plus uploader entries.'
    : 'Strategy line from uploader entries.'
  if (benchmarksAreUnavailable(benchmarkSource)) {
    return `${strategyLead} Market benchmarks are unavailable — cache not populated yet.`
  }
  if (benchmarksAreSynthetic(provenance, benchmarkSource)) {
    return `${strategyLead} SPX / NDX / BTC are sample benchmarks — not live market data.`
  }
  if (isRealBenchmarkSource(benchmarkSource)) {
    return `${strategyLead} Benchmarks use cached market closes (prior close within 5 calendar days on weekends/holidays).`
  }
  return strategyLead
}

export function seriesDisplayLabel(
  key: SeriesKey,
  provenance: ChartProvenance,
  benchmarkSource: BenchmarkDataSource,
): string {
  const base = SERIES_LABEL.get(key) ?? key
  const isBenchmark = (BENCHMARK_KEYS as string[]).includes(key)
  const isProduct = (PRODUCT_KEYS as string[]).includes(key as ProductKey)

  if (isBenchmark && benchmarksAreSynthetic(provenance, benchmarkSource)) {
    return `${base} (sample)`
  }
  if (isProduct && provenance === 'mock') {
    return `${base} (preview)`
  }
  return base
}

/** Subtitle for individual-program mode — prefer backend first date over mock. */
export function programModeSubtitle(
  programLabel: string,
  provenance: ChartProvenance,
  programPoints: { date: string }[],
  mockStartDate: string,
  formatLongDate: (iso: string) => string,
  benchmarkSource: BenchmarkDataSource,
  entryCount?: number,
  programDataSource: ProgramDataSource = null,
): string | null {
  const count = entryCount ?? programPoints.length

  if (provenance === 'backend' && count === 0) {
    return null
  }
  if (provenance === 'backend' && count === 1) {
    return null
  }

  const startDate =
    provenance === 'backend' && programPoints.length > 0
      ? programPoints[0].date
      : mockStartDate

  let benchmarkNote = ''
  if (provenance === 'mock') {
    benchmarkNote = ' Benchmarks are preview data only.'
  } else if (benchmarksAreUnavailable(benchmarkSource)) {
    benchmarkNote = ' Market benchmarks unavailable until cache is populated.'
  } else if (isRealBenchmarkSource(benchmarkSource)) {
    benchmarkNote = ' SPX / NDX / BTC use cached market closes when enabled.'
  } else if (benchmarkSource === 'deterministic_fixture') {
    benchmarkNote = ' Enable sample benchmarks below to compare (not live market data).'
  }
  // backend + null benchmarkSource: no benchmark note (benchmarks not returned)

  const entryNoun = hasBackfilledHistory(programDataSource)
    ? 'first recorded entry (imported tearsheet history or uploader entry)'
    : 'first uploader entry'
  return `${programLabel} is normalized to $100,000 on its ${entryNoun} (${formatLongDate(startDate)}).${benchmarkNote}`
}

/** Combined-mode subtitle keyed to data source. */
export function combinedModeSubtitle(
  provenance: ChartProvenance,
  programDataSource: ProgramDataSource = null,
): string {
  if (provenance === 'mock') {
    return 'Preview demo curves — not from uploader entries. Each strategy is indexed by trading-day count.'
  }
  const entryNoun = hasBackfilledHistory(programDataSource)
    ? 'first recorded entry'
    : 'first uploader entry'
  return `Each strategy is normalized to $100,000 on its ${entryNoun} — compared by trading-day count, not calendar date.`
}

/** Whether benchmark legend toggles should render in program mode. */
export function showBenchmarkToggles(
  provenance: ChartProvenance,
  benchmarkSource: BenchmarkDataSource,
  programHasRows = true,
): boolean {
  if (!programHasRows) return false
  if (provenance === 'mock') return true
  if (benchmarksAreUnavailable(benchmarkSource)) return false
  if (benchmarkSource === null) return false
  if (isRealBenchmarkSource(benchmarkSource)) return true
  return benchmarkSource === 'deterministic_fixture'
}

