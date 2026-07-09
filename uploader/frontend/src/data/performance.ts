// Mock performance data for the "$100,000 investment" chart.
//
// Deterministic by construction (seeded PRNG, fixed anchor date) so the chart
// looks identical on every load. All series are generated as geometric random
// walks; the chart component re-normalizes whatever window is shown so every
// series starts at exactly $100,000 — matching "normalized to a $100,000
// starting investment" for any selected date range.

export type SeriesKey = 'TKP' | 'TCP' | 'AGM' | 'YQ' | 'SPX' | 'NDX' | 'BTC'

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

export type PerfPoint = { date: string } & Record<SeriesKey, number>

// Trading days to synthesize (~1 year).
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

function buildPerformanceData(): PerfPoint[] {
  const dates = businessDaysEndingAt(ANCHOR_ISO, TRADING_DAYS)
  const series = SERIES.map((s) => {
    const p = WALK_PARAMS[s.key]
    return { key: s.key, values: walk(TRADING_DAYS, p.drift, p.vol, p.seed) }
  })
  return dates.map((date, i) => {
    const point = { date } as PerfPoint
    for (const s of series) point[s.key] = s.values[i]
    return point
  })
}

export const PERFORMANCE_DATA: PerfPoint[] = buildPerformanceData()

export interface RangeOption {
  key: string
  label: string
  /** Trading days to show; null = full history. */
  days: number | null
}

export const RANGE_OPTIONS: RangeOption[] = [
  { key: '1M', label: '1M', days: 21 },
  { key: '3M', label: '3M', days: 63 },
  { key: '6M', label: '6M', days: 126 },
  { key: '1Y', label: '1Y', days: null },
]

export const DEFAULT_RANGE_KEY = '1Y'

/**
 * Slice to the selected window and re-normalize every series so its first
 * visible point equals exactly $100,000.
 */
export function getNormalizedData(rangeDays: number | null): PerfPoint[] {
  const all = PERFORMANCE_DATA
  const sliced = rangeDays == null ? all : all.slice(Math.max(0, all.length - rangeDays))
  if (sliced.length === 0) return []

  const base = {} as Record<SeriesKey, number>
  for (const s of SERIES) base[s.key] = sliced[0][s.key]

  return sliced.map((pt) => {
    const norm = { date: pt.date } as PerfPoint
    for (const s of SERIES) {
      const b = base[s.key]
      norm[s.key] = b ? (pt[s.key] / b) * 100_000 : 100_000
    }
    return norm
  })
}

/** One tick per month (first visible trading day of each month) — avoids the
 *  duplicate "Oct 25 / Oct 25" labels that auto-ticks produce on daily data. */
export function getMonthTicks(data: PerfPoint[]): string[] {
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
