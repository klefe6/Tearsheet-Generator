/**
 * Chart display state — empty, sparse, and axis helpers for PerformanceChart.
 */

import type { ChartProvenance } from './chartProvenance'
import {
  PRODUCT_KEYS,
  type CombinedTradingDayPoint,
  type ProductKey,
  type ProgramSeriesPoint,
} from '../data/performance'

export type ChartDisplayState = 'loading' | 'empty' | 'needs_more' | 'sparse' | 'ready'

const SPARSE_POINT_THRESHOLD = 3

export function countProgramPoints(points: ProgramSeriesPoint[], program: ProductKey): number {
  return points.filter((pt) => pt[program] != null).length
}

export function combinedProgramsWithData(data: CombinedTradingDayPoint[]): ProductKey[] {
  return PRODUCT_KEYS.filter((key) => data.some((pt) => pt[key] != null))
}

/** Unique integer day indices for combined-mode x-axis (no duplicate ticks). */
export function getCombinedDayTicks(data: CombinedTradingDayPoint[]): number[] {
  const days = new Set<number>()
  for (const pt of data) days.add(pt.dayIndex)
  return [...days].sort((a, b) => a - b)
}

export function resolveProgramChartState(
  provenance: ChartProvenance,
  points: ProgramSeriesPoint[],
  program: ProductKey,
): ChartDisplayState {
  if (provenance === 'loading') return 'loading'
  const count = countProgramPoints(points, program)
  if (count === 0) return 'empty'
  if (count === 1) return 'needs_more'
  if (count < SPARSE_POINT_THRESHOLD) return 'sparse'
  return 'ready'
}

export function resolveCombinedChartState(
  provenance: ChartProvenance,
  data: CombinedTradingDayPoint[],
  visiblePrograms: ProductKey[],
): ChartDisplayState {
  if (provenance === 'loading') return 'loading'
  if (visiblePrograms.length === 0) return 'empty'
  const counts = visiblePrograms.map(
    (key) => data.filter((pt) => pt[key] != null).length,
  )
  const maxPoints = Math.max(...counts)
  if (maxPoints === 0) return 'empty'
  if (maxPoints === 1) return 'needs_more'
  if (maxPoints < SPARSE_POINT_THRESHOLD) return 'sparse'
  return 'ready'
}

export function programEmptyMessage(program: ProductKey): string {
  const label = program === 'YQ' ? 'Y&Q' : program
  return `No ${label} entries yet. Enter a ${label} row below to start the line.`
}

export function programNeedsMoreMessage(program: ProductKey, firstDate: string): string {
  const label = program === 'YQ' ? 'Y&Q' : program
  return `Need at least two ${label} entries to draw a performance line. First entry: ${firstDate}.`
}

export function sparseDataNote(): string {
  return 'Early data — only a few uploader entries so far. Lines will smooth out as more days are added.'
}

export function combinedEmptyMessage(): string {
  return 'No strategy entries yet. Enter rows for TKP, TCP, AGM, or Y&Q below to start the chart.'
}

export function combinedNeedsMoreMessage(): string {
  return 'Need at least two entries per strategy to draw comparison lines. Add another row for the strategies you are tracking.'
}

export function shouldShowDots(state: ChartDisplayState): boolean {
  return state === 'sparse' || state === 'needs_more'
}

export function chartLineType(state: ChartDisplayState): 'linear' | 'monotone' {
  return state === 'sparse' ? 'linear' : 'monotone'
}

export function chartHeightPx(state: ChartDisplayState): number {
  if (state === 'empty' || state === 'needs_more') return 120
  if (state === 'sparse') return 260
  return 360
}

/** Backend warnings that duplicate our empty-state copy — hide in program mode. */
export function filterWarningsForMode(
  warnings: string[],
  mode: 'combined' | ProductKey,
): string[] {
  if (mode === 'combined') {
    return warnings.filter((w) => !/: no data yet\.?$/i.test(w))
  }
  const prefix = `${mode}:`
  return warnings.filter((w) => !w.startsWith(prefix))
}
