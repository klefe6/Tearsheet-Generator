import { useEffect, useMemo, useState } from 'react'
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { fetchPerformance } from '../api/client'
import {
  BENCHMARK_KEYS,
  PRODUCT_KEYS,
  SERIES,
  buildCombinedTradingDaySeries,
  buildProgramBenchmarkSeries,
  formatChartXAxis,
  getMonthTicks,
  getSeriesStartDate,
  transformCombinedResponse,
  transformProgramResponse,
  type BenchmarkKey,
  type ChartMode,
  type CombinedTradingDayPoint,
  type ProductKey,
  type ProgramSeriesPoint,
  type SeriesKey,
} from '../data/performance'
import {
  combinedModeSubtitle,
  defaultEnabledBenchmarks,
  programModeSubtitle,
  provenanceNotice,
  readBenchmarkDataSource,
  resolveChartProvenance,
  seriesDisplayLabel,
  showBenchmarkToggles,
  type BenchmarkDataSource,
  type ChartProvenance,
} from '../lib/chartProvenance'
import {
  formatAxisCurrency,
  formatLongDate,
  formatShortDate,
  formatTooltipCurrency,
} from '../lib/format'
import styles from './PerformanceChart.module.css'

// Concrete hex (not CSS vars): Recharts writes these as SVG presentation
// attributes, which don't resolve var().
const AXIS_MUTED = '#8a8f98'
const GRID = '#eef0f3'
const BORDER = '#e6e8ec'
const CURSOR = '#c9ced6'

const MODE_OPTIONS: { key: ChartMode; label: string }[] = [
  { key: 'combined', label: 'All Strategies' },
  { key: 'TKP', label: 'TKP' },
  { key: 'TCP', label: 'TCP' },
  { key: 'AGM', label: 'AGM' },
  { key: 'YQ', label: 'Y&Q' },
]

const SERIES_BY_KEY = new Map(SERIES.map((s) => [s.key, s]))

interface TooltipEntry {
  dataKey: string
  name: string
  value: number
  color: string
  payload: Record<string, number | string | undefined>
}

interface ChartTooltipProps {
  active?: boolean
  payload?: TooltipEntry[]
  label?: string | number
  mode: ChartMode
}

function ChartTooltip({ active, payload, label, mode }: ChartTooltipProps) {
  if (!active || !payload || payload.length === 0 || label === undefined) return null
  const rows = [...payload].sort((a, b) => b.value - a.value)
  const heading =
    mode === 'combined' ? `Day ${label}` : formatLongDate(String(label))

  return (
    <div className={styles.tooltip}>
      <div className={styles.tooltipDate}>{heading}</div>
      <ul className={styles.tooltipList}>
        {rows.map((entry) => {
          // Combined mode: each product's own real calendar date on this
          // trading day, since products don't share one calendar start.
          const realDate =
            mode === 'combined' ? entry.payload[`${entry.dataKey}_date`] : undefined
          return (
            <li key={entry.dataKey} className={styles.tooltipRow}>
              <span className={styles.tooltipDot} style={{ background: entry.color }} />
              <span className={styles.tooltipName}>{entry.name}</span>
              {typeof realDate === 'string' && (
                <span className={styles.tooltipSubDate}>{formatShortDate(realDate)}</span>
              )}
              <span className={styles.tooltipVal}>{formatTooltipCurrency(entry.value)}</span>
            </li>
          )
        })}
      </ul>
    </div>
  )
}

interface Props {
  /** Bump this (e.g. after Enter/Delete/Export) to force a fresh
   *  GET /api/performance for whatever mode is currently showing. */
  refreshToken?: number
}

export function PerformanceChart({ refreshToken = 0 }: Props) {
  const [mode, setMode] = useState<ChartMode>('combined')
  const [hiddenProducts, setHiddenProducts] = useState<Set<ProductKey>>(() => new Set())
  const [enabledBenchmarks, setEnabledBenchmarks] = useState<Set<BenchmarkKey>>(() => new Set())
  const [provenance, setProvenance] = useState<ChartProvenance>('loading')
  const [benchmarkSource, setBenchmarkSource] = useState<BenchmarkDataSource>(null)

  const isCombined = mode === 'combined'

  const [backendCombined, setBackendCombined] = useState<CombinedTradingDayPoint[] | null>(null)
  const [backendProgram, setBackendProgram] = useState<ProgramSeriesPoint[] | null>(null)
  const [warnings, setWarnings] = useState<string[]>([])

  useEffect(() => {
    let cancelled = false
    setBackendCombined(null)
    setBackendProgram(null)
    setWarnings([])
    setProvenance('loading')

    const onSettled = (resp: Awaited<ReturnType<typeof fetchPerformance>>) => {
      if (cancelled) return
      setProvenance(resolveChartProvenance(resp, true))
      setBenchmarkSource(readBenchmarkDataSource(resp))
      if (resp) setWarnings(resp.warnings)
    }

    if (isCombined) {
      fetchPerformance('combined').then((resp) => {
        if (cancelled) return
        if (resp) setBackendCombined(transformCombinedResponse(resp))
        onSettled(resp)
      })
    } else {
      fetchPerformance('program', mode as ProductKey, [...BENCHMARK_KEYS]).then((resp) => {
        if (cancelled) return
        if (resp) setBackendProgram(transformProgramResponse(resp))
        onSettled(resp)
      })
    }
    return () => {
      cancelled = true
    }
  }, [mode, isCombined, refreshToken])

  useEffect(() => {
    setEnabledBenchmarks(defaultEnabledBenchmarks(provenance, benchmarkSource))
  }, [provenance, benchmarkSource, mode])

  const mockCombinedData = useMemo(
    () => (isCombined ? buildCombinedTradingDaySeries() : []),
    [isCombined],
  )
  const mockProgramData = useMemo(
    () => (isCombined ? [] : buildProgramBenchmarkSeries(mode as ProductKey)),
    [isCombined, mode],
  )
  const combinedData = backendCombined ?? mockCombinedData
  const programData = backendProgram ?? mockProgramData
  const data = isCombined ? combinedData : programData
  const monthTicks = useMemo(
    () => (isCombined ? [] : getMonthTicks(programData)),
    [isCombined, programData],
  )

  const toggleProduct = (key: ProductKey) => {
    setHiddenProducts((prev) => {
      const next = new Set(prev)
      if (next.has(key)) next.delete(key)
      else next.add(key)
      return next
    })
  }

  const toggleBenchmark = (key: BenchmarkKey) => {
    setEnabledBenchmarks((prev) => {
      const next = new Set(prev)
      if (next.has(key)) next.delete(key)
      else next.add(key)
      return next
    })
  }

  // Lines actually rendered for the current mode.
  const lineKeys: SeriesKey[] = isCombined
    ? PRODUCT_KEYS.filter((k) => !hiddenProducts.has(k))
    : [mode as ProductKey, ...BENCHMARK_KEYS.filter((k) => enabledBenchmarks.has(k))]

  const isEmpty = data.length === 0 || lineKeys.length === 0

  const activeLabel = isCombined ? '' : SERIES_BY_KEY.get(mode as ProductKey)?.label ?? mode
  const notice = provenanceNotice(provenance, mode, benchmarkSource)
  const subtitle = isCombined
    ? combinedModeSubtitle(provenance)
    : programModeSubtitle(
        activeLabel,
        provenance,
        programData,
        getSeriesStartDate(mode as ProductKey),
        formatLongDate,
        benchmarkSource,
      )
  const benchmarksVisible = showBenchmarkToggles(provenance, benchmarkSource)

  return (
    <section className={styles.card}>
      <div className={styles.head}>
        <div className={styles.heading}>
          <h2 className={styles.title}>Performance of $100,000 Investment</h2>
          <p className={styles.subtitle}>{subtitle}</p>
        </div>
        <div className={styles.modePill} role="group" aria-label="Chart mode">
          {MODE_OPTIONS.map((m) => (
            <button
              key={m.key}
              type="button"
              className={`${styles.modeBtn} ${m.key === mode ? styles.modeBtnActive : ''}`}
              onClick={() => setMode(m.key)}
              aria-pressed={m.key === mode}
            >
              {m.label}
            </button>
          ))}
        </div>
      </div>

      {notice && (
        <p className={styles.provenanceNote} role="note">
          {notice}
        </p>
      )}

      <div className={styles.legend}>
        {isCombined
          ? PRODUCT_KEYS.map((key) => {
              const s = SERIES_BY_KEY.get(key)!
              const off = hiddenProducts.has(key)
              return (
                <button
                  key={key}
                  type="button"
                  className={`${styles.legendItem} ${off ? styles.legendOff : ''}`}
                  onClick={() => toggleProduct(key)}
                  aria-pressed={!off}
                >
                  <span className={styles.swatch} style={{ background: s.color }} />
                  {seriesDisplayLabel(key, provenance, benchmarkSource)}
                </button>
              )
            })
          : (() => {
              const active = SERIES_BY_KEY.get(mode)!
              return (
                <>
                  <span className={styles.activeSeriesChip}>
                    <span className={styles.swatch} style={{ background: active.color }} />
                    {seriesDisplayLabel(mode as ProductKey, provenance, benchmarkSource)}
                  </span>
                  {benchmarksVisible && (
                    <>
                      <span className={styles.toggleDivider} aria-hidden="true" />
                      {BENCHMARK_KEYS.map((key) => {
                        const s = SERIES_BY_KEY.get(key)!
                        const on = enabledBenchmarks.has(key)
                        const swatch = s.dashed
                          ? `repeating-linear-gradient(90deg, ${s.color} 0 6px, transparent 6px 10px)`
                          : s.color
                        return (
                          <button
                            key={key}
                            type="button"
                            className={`${styles.legendItem} ${!on ? styles.legendOff : ''}`}
                            onClick={() => toggleBenchmark(key)}
                            aria-pressed={on}
                          >
                            <span className={styles.swatch} style={{ background: swatch }} />
                            {seriesDisplayLabel(key, provenance, benchmarkSource)}
                          </button>
                        )
                      })}
                    </>
                  )}
                </>
              )
            })()}
      </div>

      {warnings.length > 0 && (
        <p className={styles.warningNote}>{warnings.join(' ')}</p>
      )}

      <div className={styles.chartWrap}>
        {isEmpty ? (
          <div className={styles.emptyState}>
            No data to display for this selection — enable a series above to see the chart.
          </div>
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={data} margin={{ top: 8, right: 18, bottom: 4, left: 4 }}>
              <CartesianGrid stroke={GRID} vertical={false} />
              {isCombined ? (
                <XAxis
                  dataKey="dayIndex"
                  type="number"
                  domain={[0, 'dataMax']}
                  tickFormatter={(v) => formatChartXAxis('combined', v)}
                  tick={{ fill: AXIS_MUTED, fontSize: 12 }}
                  tickMargin={10}
                  axisLine={{ stroke: BORDER }}
                  tickLine={false}
                />
              ) : (
                <XAxis
                  dataKey="date"
                  ticks={monthTicks}
                  tickFormatter={(v) => formatChartXAxis(mode, v)}
                  tick={{ fill: AXIS_MUTED, fontSize: 12 }}
                  tickMargin={10}
                  minTickGap={28}
                  axisLine={{ stroke: BORDER }}
                  tickLine={false}
                />
              )}
              <YAxis
                tickFormatter={formatAxisCurrency}
                tick={{ fill: AXIS_MUTED, fontSize: 12 }}
                width={58}
                axisLine={false}
                tickLine={false}
                domain={['auto', 'auto']}
              />
              <Tooltip
                content={<ChartTooltip mode={mode} />}
                cursor={{ stroke: CURSOR, strokeWidth: 1 }}
              />
              {lineKeys.map((key) => {
                const s = SERIES_BY_KEY.get(key)!
                return (
                  <Line
                    key={key}
                    type="monotone"
                    dataKey={key}
                    name={seriesDisplayLabel(key, provenance, benchmarkSource)}
                    stroke={s.color}
                    strokeWidth={s.strokeWidth}
                    strokeDasharray={s.dashed ? '5 4' : undefined}
                    dot={false}
                    activeDot={{ r: 3.5, strokeWidth: 0 }}
                    isAnimationActive={false}
                  />
                )
              })}
            </LineChart>
          </ResponsiveContainer>
        )}
      </div>
    </section>
  )
}
