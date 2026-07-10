import { describe, expect, it } from 'vitest'
import {
  LEVERAGE_SIMULATOR_STRATEGIES,
  applyLeverageToCombinedSeries,
  applyLeverageToProgramSeries,
  applyLeverageToSeriesValues,
  isLeverageActive,
  leverageSimulatedLabel,
} from './leverageSimulator'
import type { CombinedTradingDayPoint, ProgramSeriesPoint } from '../data/performance'

describe('applyLeverageToSeriesValues', () => {
  it('returns unchanged series at 1.0x', () => {
    const base = [100_000, 105_000, 110_000]
    expect(applyLeverageToSeriesValues(base, 1)).toEqual(base)
  })

  it('doubles period returns at 2.0x, not raw values', () => {
    const base = [100_000, 110_000, 121_000]
    expect(applyLeverageToSeriesValues(base, 2)).toEqual([100_000, 120_000, 144_000])
  })

  it('halves period returns at 0.5x', () => {
    const base = [100_000, 110_000]
    expect(applyLeverageToSeriesValues(base, 0.5)).toEqual([100_000, 105_000])
  })

  it('scales drawdown proportionally', () => {
    const base = [100_000, 90_000, 99_000]
    expect(applyLeverageToSeriesValues(base, 2)).toEqual([100_000, 80_000, 96_000])
  })

  it('preserves the first value and skips missing prior base', () => {
    const base = [undefined, 100_000, 110_000]
    expect(applyLeverageToSeriesValues(base, 2)).toEqual([
      undefined,
      100_000,
      120_000,
    ])
  })

  it('does not mutate the input array', () => {
    const base = [100_000, 110_000]
    const copy = [...base]
    applyLeverageToSeriesValues(base, 2)
    expect(base).toEqual(copy)
  })

  it('floors negative leveraged values at zero', () => {
    const base = [100_000, 50_000]
    expect(applyLeverageToSeriesValues(base, 5)).toEqual([100_000, 0])
  })
})

describe('applyLeverageToCombinedSeries', () => {
  const data: CombinedTradingDayPoint[] = [
    { dayIndex: 0, TKP: 100_000, TCP: 100_000 },
    { dayIndex: 1, TKP: 110_000, TCP: 102_000 },
    { dayIndex: 2, TKP: 121_000, TCP: 104_000 },
  ]

  it('leverages only the selected strategy', () => {
    const result = applyLeverageToCombinedSeries(data, 'TKP', 2)
    expect(result[1]?.TKP).toBe(120_000)
    expect(result[1]?.TCP).toBe(102_000)
  })

  it('returns a shallow copy at 1.0x without mutating source', () => {
    const result = applyLeverageToCombinedSeries(data, 'TKP', 1)
    expect(result).not.toBe(data)
    expect(result).toEqual(data)
    expect(data[1]?.TKP).toBe(110_000)
  })
})

describe('applyLeverageToProgramSeries', () => {
  const data: ProgramSeriesPoint[] = [
    { date: '2026-01-01', TKP: 100_000, SPX: 100_000 },
    { date: '2026-01-02', TKP: 110_000, SPX: 101_000 },
  ]

  it('leaves benchmarks unchanged', () => {
    const result = applyLeverageToProgramSeries(data, 'TKP', 2)
    expect(result[1]?.TKP).toBe(120_000)
    expect(result[1]?.SPX).toBe(101_000)
  })
})

describe('leverage simulator UI helpers', () => {
  it('is inactive at 1.0x or when no strategy selected', () => {
    expect(isLeverageActive(null, 2)).toBe(false)
    expect(isLeverageActive('TKP', 1)).toBe(false)
    expect(isLeverageActive('TKP', 2)).toBe(true)
  })

  it('formats simulated labels', () => {
    expect(leverageSimulatedLabel('TKP', 2)).toBe('TKP 2.0x simulated')
    expect(leverageSimulatedLabel('TCP', 0.5)).toBe('TCP 0.5x simulated')
  })

  it('excludes Y&Q from simulator strategies', () => {
    expect(LEVERAGE_SIMULATOR_STRATEGIES).toEqual(['TKP', 'TCP', 'AGM'])
    expect(LEVERAGE_SIMULATOR_STRATEGIES).not.toContain('YQ')
  })
})
