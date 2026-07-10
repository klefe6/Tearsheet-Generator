// Mock performance data for the "$100,000 investment" chart.
//
// Deterministic by construction (seeded PRNG, fixed anchor date) so the chart
// looks identical on every load. Two comparison modes are supported, each
// with a different x-axis:
//
//   Combined ("All Strategies") — a LIFECYCLE comparison. Each product is
//   normalized to $100,000 on its own first trading day and plotted against
//   trading-day INDEX (Day 0, Day 1, ...), not calendar date. Products don't
//   all share one calendar start date, so a shorter-lived product's line
//   simply stops once its own history runs out. No benchmarks here.
//
//   Individual program ("TKP" / "TCP" / "AGM" / "Y&Q") — a CALENDAR
//   comparison. The selected product is normalized to $100,000 on its own
//   real first date; SPX/NDX/BTC are rebased to $100,000 from that same real
//   date, sharing one calendar x-axis with the product.
//
// All builder functions here are pure (no React, no fetch) so the same shape
// can be produced by a future `/api/performance` backend call without
// touching the chart component.

import { formatAxisDate } from '../lib/format'

export type ProductKey = 'TKP' | 'TCP' | 'AGM' | 'YQ'
export type BenchmarkKey = 'SPX' | 'NDX' | 'BTC'
export type SeriesKey = ProductKey | BenchmarkKey

export interface SeriesDef {
  key: SeriesKey
  label: string
  color: string
  dashed: boolean
  strokeWidth: number
  group: 'product' | 'benchmark'
}

// Legend / draw order. Products first (solid, brand colors), then benchmarks
// (SPX/NDX muted + dashed = secondary encoding; BTC the prominent volatile line).
export const SERIES: SeriesDef[] = [
  { key: 'TKP', label: 'TKP', color: '#2a78d6', dashed: false, strokeWidth: 2, group: 'product' },
  { key: 'TCP', label: 'TCP', color: '#12a150', dashed: false, strokeWidth: 2, group: 'product' },
  { key: 'AGM', label: 'AGM', color: '#7c3aed', dashed: false, strokeWidth: 2, group: 'product' },
  { key: 'YQ', label: 'Y&Q', color: '#e0a000', dashed: false, strokeWidth: 2, group: 'product' },
  { key: 'SPX', label: 'SPX', color: '#8a8f98', dashed: true, strokeWidth: 1.5, group: 'benchmark' },
  { key: 'NDX', label: 'NDX', color: '#5b6470', dashed: true, strokeWidth: 1.5, group: 'benchmark' },
  { key: 'BTC', label: 'BTC', color: '#e8543a', dashed: false, strokeWidth: 2.5, group: 'benchmark' },
]

export const PRODUCT_KEYS: ProductKey[] = ['TKP', 'TCP', 'AGM', 'YQ']
export const BENCHMARK_KEYS: BenchmarkKey[] = ['SPX', 'NDX', 'BTC']

function isProductKey(key: SeriesKey): key is ProductKey {
  return (PRODUCT_KEYS as string[]).includes(key)
}

// Trading days in the master window (~1 year), ending "today".
const TRADING_DAYS = 260
// Fixed anchor so dates never depend on "today" (keeps the mock deterministic).
const ANCHOR_ISO = '2026-07-08'

// Per-series daily drift / volatility, tuned for the requested shape:
//  BTC  = highest + most volatile · NDX/SPX = steady upward benchmarks
//  products = visible, distinct, clustered nearer the $100k baseline.
const WALK_PARAMS: Record<SeriesKey, { drift: number; vol: number; seed: number }> = {
  TKP: { drift: 0.00060, vol: 0.0060, seed: 101 },
  TCP: { drift: 0.00045, vol: 0.0042, seed: 202 },
  AGM: { drift: 0.00072, vol: 0.0082, seed: 303 },
  YQ: { drift: 0.00040, vol: 0.0070, seed: 404 },
  SPX: { drift: 0.00052, vol: 0.0068, seed: 505 },
  NDX: { drift: 0.00080, vol: 0.0100, seed: 606 },
  // Highest-ending and by far the most volatile: dips below $100k early, then
  // climbs well above every other series.
  BTC: { drift: 0.00320, vol: 0.0240, seed: 42 },
}

// Illustrative product "launch" stagger: how many trading days into the
// master window each product's real history begins (0 = spans the whole
// window). Benchmarks (market indices) are always treated as available for
// the full window regardless of when a product launched.
const PRODUCT_START_OFFSET: Record<ProductKey, number> = {
  TKP: 0,
  TCP: 40,
  AGM: 80,
  YQ: 120,
}

/** mulberry32 — tiny deterministic PRNG. */
function mulberry32(seed: number): () => number {
  let a = seed >>> 0
  return function () {
    a = (a + 0x6d2b79f5) | 0
    let t = Math.imul(a ^ (a >>> 15), 1 | a)
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}

/** Standard normal via Box–Muller. */
function gaussian(rand: () => number): number {
  const u1 = Math.max(rand(), 1e-9)
  const u2 = rand()
  return Math.sqrt(-2 * Math.log(u1)) * Math.cos(2 * Math.PI * u2)
}

/** A geometric random walk starting at $100,000. */
function walk(days: number, drift: number, vol: number, seed: number): number[] {
  const rand = mulberry32(seed)
  const out: number[] = [100_000]
  for (let i = 1; i < days; i++) {
    const ret = drift + vol * gaussian(rand)
    out.push(out[i - 1] * (1 + ret))
  }
  return out
}

/** `count` business days (Mon–Fri) ending at `endISO`, ascending. */
function businessDaysEndingAt(endISO: string, count: number): string[] {
  const dates: string[] = []
  let d = new Date(`${endISO}T00:00:00Z`)
  while (dates.length < count) {
    const day = d.getUTCDay()
    if (day !== 0 && day !== 6) dates.push(d.toISOString().slice(0, 10))
    d = new Date(d.getTime() - 86_400_000)
  }
  return dates.reverse()
}

// Master (unnormalized) tables spanning the full window. Products only
// "really" exist from their own PRODUCT_START_OFFSET onward — see
// getSeriesStartDate / buildCombinedTradingDaySeries / buildProgramBenchmarkSeries.
const MASTER_DATES: string[] = businessDaysEndingAt(ANCHOR_ISO, TRADING_DAYS)
const MASTER_RAW: Record<SeriesKey, number[]> = SERIES.reduce(
  (acc, s) => {
    const p = WALK_PARAMS[s.key]
    acc[s.key] = walk(TRADING_DAYS, p.drift, p.vol, p.seed)
    return acc
  },
  {} as Record<SeriesKey, number[]>,
)

/** ISO date a series' history begins on. Benchmarks span the full window;
 *  products "launch" at their configured offset into that window. */
export function getSeriesStartDate(key: SeriesKey): string {
  const offset = isProductKey(key) ? PRODUCT_START_OFFSET[key] : 0
  return MASTER_DATES[offset]
}

/** How many trading days of real history a product has, up to "today". */
export function getProductTradingDayCount(key: ProductKey): number {
  return TRADING_DAYS - PRODUCT_START_OFFSET[key]
}

/** Rebase a raw value series so its first entry becomes exactly $100,000. */
export function normalizeSeriesToBase(rawValues: number[], baseValue: number): number[] {
  if (!baseValue) return rawValues.map(() => 100_000)
  return rawValues.map((v) => (v / baseValue) * 100_000)
}

/** First index in an ascending ISO-date array on or after `targetDate`. */
function firstIndexOnOrAfter(dates: string[], targetDate: string): number {
  const idx = dates.findIndex((d) => d >= targetDate)
  return idx === -1 ? dates.length - 1 : idx
}

export interface CombinedTradingDayPoint {
  dayIndex: number
  TKP?: number
  TCP?: number
  AGM?: number
  YQ?: number
  // Real calendar date backing each product's point on this trading day —
  // only used for the optional tooltip enhancement; keys are `${key}_date`.
  [dateKey: string]: number | string | undefined
}

/**
 * All Strategies / Combined mode: "if each strategy started at $100,000 on
 * its own first trading day, what would the curve look like by trading-day
 * count?" Each product is normalized independently to its own Day 0 and
 * indexed by trading-day count, NOT calendar date — so products are free to
 * have started on different real dates. A product's columns are simply
 * omitted once past its own history length, so its line ends earlier than
 * longer-running products rather than flattening or connecting through a gap.
 * No benchmarks are included in this mode.
 */
export function buildCombinedTradingDaySeries(): CombinedTradingDayPoint[] {
  const maxLen = Math.max(...PRODUCT_KEYS.map((k) => getProductTradingDayCount(k)))
  const points: CombinedTradingDayPoint[] = []
  for (let day = 0; day < maxLen; day++) {
    const point: CombinedTradingDayPoint = { dayIndex: day }
    for (const key of PRODUCT_KEYS) {
      const len = getProductTradingDayCount(key)
      if (day >= len || len <= 0) continue // this product's history already ended
      const offset = PRODUCT_START_OFFSET[key]
      const raw = MASTER_RAW[key]
      const base = raw[offset]
      point[key] = base ? (raw[offset + day] / base) * 100_000 : 100_000
      point[`${key}_date`] = MASTER_DATES[offset + day]
    }
    points.push(point)
  }
  return points
}

export interface ProgramSeriesPoint {
  date: string
  TKP?: number
  TCP?: number
  AGM?: number
  YQ?: number
  SPX?: number
  NDX?: number
  BTC?: number
}

/**
 * Individual-program mode: "from this program's real start date, how did it
 * perform versus SPX/NDX/BTC over real calendar time?" The selected program
 * is normalized to $100,000 on its own real first date; SPX/NDX/BTC are
 * rebased to $100,000 from that SAME real date so all four lines share one
 * calendar x-axis. Benchmark baselines use the first benchmark datapoint ON
 * OR AFTER the program's start date (firstIndexOnOrAfter) rather than
 * assuming an exact match — in this mock dataset every trading day has every
 * benchmark populated, so that lookup always lands exactly on the start date,
 * but it's written to hold up once real (potentially gappy, e.g. holiday-
 * missing) benchmark data replaces this mock.
 */
export function buildProgramBenchmarkSeries(program: ProductKey): ProgramSeriesPoint[] {
  const offset = PRODUCT_START_OFFSET[program]
  const programRaw = MASTER_RAW[program]
  const programBase = programRaw[offset]
  const startDate = MASTER_DATES[offset]

  const benchmarkBaseIndex = firstIndexOnOrAfter(MASTER_DATES, startDate)
  const benchmarkBase: Record<BenchmarkKey, number> = {} as Record<BenchmarkKey, number>
  for (const b of BENCHMARK_KEYS) benchmarkBase[b] = MASTER_RAW[b][benchmarkBaseIndex]

  const points: ProgramSeriesPoint[] = []
  for (let i = offset; i < TRADING_DAYS; i++) {
    const point: ProgramSeriesPoint = { date: MASTER_DATES[i] }
    point[program] = programBase ? (programRaw[i] / programBase) * 100_000 : 100_000
    for (const b of BENCHMARK_KEYS) {
      const base = benchmarkBase[b]
      point[b] = base ? (MASTER_RAW[b][i] / base) * 100_000 : 100_000
    }
    points.push(point)
  }
  return points
}

/** Chart mode: the lifecycle "combined" view, or one program's benchmark view. */
export type ChartMode = 'combined' | ProductKey

/** X-axis tick text for either mode: "Day N" for combined, a calendar label otherwise. */
export function formatChartXAxis(mode: ChartMode, value: number | string): string {
  return mode === 'combined' ? formatDayIndexTick(Number(value)) : formatAxisDate(String(value))
}

export function formatDayIndexTick(dayIndex: number): string {
  return `Day ${Math.round(dayIndex)}`
}

/** One tick per calendar month (first point of each month) — avoids the
 *  duplicate "Oct 25 / Oct 25" labels daily data produces on a category axis.
 *  Generic over any date-keyed point array (works for any program's window,
 *  which may start mid-year rather than at the master window's start). */
export function getMonthTicks(data: { date: string }[]): string[] {
  const ticks: string[] = []
  let lastMonth = ''
  for (const pt of data) {
    const ym = pt.date.slice(0, 7)
    if (ym !== lastMonth) {
      ticks.push(pt.date)
      lastMonth = ym
    }
  }
  return ticks
}
