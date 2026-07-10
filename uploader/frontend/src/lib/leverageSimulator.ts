import type {
  CombinedTradingDayPoint,
  ProductKey,
  ProgramSeriesPoint,
} from '../data/performance'

/** Strategies available in the leverage simulator (Y&Q excluded until data exists). */
export const LEVERAGE_SIMULATOR_STRATEGIES: ProductKey[] = ['TKP', 'TCP', 'AGM']

export const LEVERAGE_MIN = 0.25
export const LEVERAGE_MAX = 5
export const LEVERAGE_STEP = 0.25
export const LEVERAGE_DEFAULT = 1

export const LEVERAGE_SIMULATOR_NOTE =
  'Visual simulation only. Leverage scales daily returns and drawdowns; it is not saved and does not affect Export All.'

export function isLeverageActive(
  strategy: ProductKey | null,
  leverage: number,
): boolean {
  return strategy !== null && leverage !== 1
}

/** Display label for a leveraged strategy line in legend/tooltip. */
export function leverageSimulatedLabel(strategy: ProductKey, leverage: number): string {
  return `${strategy} ${formatLeverageMultiple(leverage)} simulated`
}

export function formatLeverageMultiple(leverage: number): string {
  const rounded = Math.round(leverage * 100) / 100
  if (Number.isInteger(rounded)) return `${rounded.toFixed(1)}x`
  return `${parseFloat(rounded.toFixed(2))}x`
}

function roundUsd(value: number): number {
  return Math.round(value * 100) / 100
}

/**
 * Apply leverage via period-over-period returns (not raw NAV multiplication).
 * First finite value is preserved; missing/zero prior base values skip safely.
 * Negative leveraged values are floored at 0.
 */
export function applyLeverageToSeriesValues(
  values: ReadonlyArray<number | undefined | null>,
  leverage: number,
): (number | undefined)[] {
  if (leverage === 1) {
    return values.map((v) => (v == null || !Number.isFinite(v) ? undefined : v))
  }

  const out: (number | undefined)[] = []
  let prevBase: number | undefined
  let prevLev: number | undefined

  for (const raw of values) {
    if (raw == null || !Number.isFinite(raw)) {
      out.push(undefined)
      continue
    }
    if (prevBase == null || prevBase === 0 || prevLev == null) {
      out.push(raw)
      prevBase = raw
      prevLev = raw
      continue
    }
    const baseReturn = raw / prevBase - 1
    const levReturn = baseReturn * leverage
    const next = prevLev * (1 + levReturn)
    const safe = next < 0 ? 0 : roundUsd(next)
    out.push(safe)
    prevBase = raw
    prevLev = safe
  }
  return out
}

/** Derive leveraged combined-mode points without mutating the source array. */
export function applyLeverageToCombinedSeries(
  data: ReadonlyArray<CombinedTradingDayPoint>,
  strategy: ProductKey,
  leverage: number,
): CombinedTradingDayPoint[] {
  if (!isLeverageActive(strategy, leverage)) return [...data]

  const values = data.map((p) => p[strategy])
  const leveraged = applyLeverageToSeriesValues(values, leverage)
  return data.map((p, i) => {
    const v = leveraged[i]
    if (v === undefined) return { ...p }
    return { ...p, [strategy]: v }
  })
}

/** Derive leveraged program-mode points without mutating the source array. */
export function applyLeverageToProgramSeries(
  data: ReadonlyArray<ProgramSeriesPoint>,
  strategy: ProductKey,
  leverage: number,
): ProgramSeriesPoint[] {
  if (!isLeverageActive(strategy, leverage)) return [...data]

  const values = data.map((p) => p[strategy])
  const leveraged = applyLeverageToSeriesValues(values, leverage)
  return data.map((p, i) => {
    const v = leveraged[i]
    if (v === undefined) return { ...p }
    return { ...p, [strategy]: v }
  })
}
