/**
 * Chart data provenance helpers — pure functions for truthful UI labeling.
 * See backend/docs/PERFORMANCE_PROVENANCE.md for the full contract.
 */

import type { ApiPerformanceResponse } from '../api/client'
import type { BenchmarkKey, ChartMode, ProductKey, SeriesKey } from '../data/performance'
import { BENCHMARK_KEYS, PRODUCT_KEYS, SERIES } from '../data/performance'

export type ChartProvenance = 'loading' | 'backend' | 'mock'

export type BenchmarkDataSource = 'deterministic_fixture' | 'live' | null

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
  if (!response?.benchmark_data_source) return null
  if (response.benchmark_data_source === 'deterministic_fixture') {
    return 'deterministic_fixture'
  }
  return 'live'
}

export function benchmarksAreSynthetic(
  provenance: ChartProvenance,
  benchmarkSource: BenchmarkDataSource,
): boolean {
  return provenance === 'mock' || benchmarkSource === 'deterministic_fixture'
}

/** Benchmarks hidden by default when data is synthetic or the whole chart is mock. */
export function defaultEnabledBenchmarks(
  provenance: ChartProvenance,
  benchmarkSource: BenchmarkDataSource,
): Set<BenchmarkKey> {
  if (benchmarksAreSynthetic(provenance, benchmarkSource)) return new Set()
  return new Set(['SPX', 'NDX'])
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
  if (benchmarksAreSynthetic(provenance, benchmarkSource)) {
    return 'Strategy line from uploader entries. SPX / NDX / BTC are sample benchmarks — not live market data.'
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
): string {
  const startDate =
    provenance === 'backend' && programPoints.length > 0
      ? programPoints[0].date
      : mockStartDate
  const benchmarkNote = provenance === 'mock'
    ? ' Benchmarks are preview data only.'
    : ' Enable sample benchmarks below to compare (not live market data).'
  return `${programLabel} is normalized to $100,000 on its first uploader entry (${formatLongDate(startDate)}).${benchmarkNote}`
}

/** Combined-mode subtitle keyed to data source. */
export function combinedModeSubtitle(provenance: ChartProvenance): string {
  if (provenance === 'mock') {
    return 'Preview demo curves — not from uploader entries. Each strategy is indexed by trading-day count.'
  }
  return 'Each strategy is normalized to $100,000 on its first uploader entry — compared by trading-day count, not calendar date.'
}
