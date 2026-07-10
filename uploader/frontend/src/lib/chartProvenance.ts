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
): string | null {
  if (provenance === 'loading') return null
  if (provenance === 'mock') {
    return 'Preview chart — demo data only. Connect the uploader backend to show strategy lines from your entries.'
  }
  if (mode === 'combined') {
    return 'Strategy lines reflect uploader entries only (no historical tearsheet data).'
  }
  if (benchmarksAreUnavailable(benchmarkSource)) {
    return 'Strategy line from uploader entries. Market benchmarks are unavailable — cache not populated yet.'
  }
  if (benchmarksAreSynthetic(provenance, benchmarkSource)) {
    return 'Strategy line from uploader entries. SPX / NDX / BTC are sample benchmarks — not live market data.'
  }
  if (isRealBenchmarkSource(benchmarkSource)) {
    return 'Strategy line from uploader entries. Benchmarks use cached market closes (prior close within 5 calendar days on weekends/holidays).'
  }
  return 'Strategy line from uploader entries.'
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
): string {
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
  } else {
    benchmarkNote = ' Enable sample benchmarks below to compare (not live market data).'
  }
  return `${programLabel} is normalized to $100,000 on its first uploader entry (${formatLongDate(startDate)}).${benchmarkNote}`
}

/** Combined-mode subtitle keyed to data source. */
export function combinedModeSubtitle(provenance: ChartProvenance): string {
  if (provenance === 'mock') {
    return 'Preview demo curves — not from uploader entries. Each strategy is indexed by trading-day count.'
  }
  return 'Each strategy is normalized to $100,000 on its first uploader entry — compared by trading-day count, not calendar date.'
}

/** Whether benchmark legend toggles should render in program mode. */
export function showBenchmarkToggles(
  provenance: ChartProvenance,
  benchmarkSource: BenchmarkDataSource,
): boolean {
  if (provenance === 'mock') return true
  return !benchmarksAreUnavailable(benchmarkSource)
}
