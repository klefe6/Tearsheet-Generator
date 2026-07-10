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
  readProgramDataSource,
  resolveChartProvenance,
  seriesDisplayLabel,
  showBenchmarkToggles,
  type BenchmarkDataSource,
  type ChartProvenance,
  type ProgramDataSource,
} from '../lib/chartProvenance'
import {
  chartHeightPx,
  chartLineType,
  combinedEmptyMessage,
  combinedNeedsMoreMessage,
  combinedProgramsWithData,
  countProgramPoints,
  partitionChartWarnings,
  programEmptyMessage,
  programNeedsMoreMessage,
  getCombinedDayTicks,
  resolveCombinedChartState,
  resolveProgramChartState,
  shouldShowDots,
  sparseDataNote,
} from '../lib/chartState'
import {
  LEVERAGE_DEFAULT,
  LEVERAGE_MAX,
  LEVERAGE_MIN,
  LEVERAGE_SIMULATOR_NOTE,
  LEVERAGE_SIMULATOR_STRATEGIES,
  LEVERAGE_STEP,
  applyLeverageToCombinedSeries,
  applyLeverageToProgramSeries,
  formatLeverageMultiple,
  isLeverageActive,
  leverageSimulatedLabel,
} from '../lib/leverageSimulator'
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
  refreshToken?: number
}

export function PerformanceChart({ refreshToken = 0 }: Props) {
  const [mode, setMode] = useState<ChartMode>('combined')
  const [hiddenProducts, setHiddenProducts] = useState<Set<ProductKey>>(() => new Set())
  const [enabledBenchmarks, setEnabledBenchmarks] = useState<Set<BenchmarkKey>>(() => new Set())
  const [provenance, setProvenance] = useState<ChartProvenance>('loading')
  const [benchmarkSource, setBenchmarkSource] = useState<BenchmarkDataSource>(null)
  const [programDataSource, setProgramDataSource] = useState<ProgramDataSource>(null)

  const isCombined = mode === 'combined'

  const [backendCombined, setBackendCombined] = useState<CombinedTradingDayPoint[] | null>(null)
  const [backendProgram, setBackendProgram] = useState<ProgramSeriesPoint[] | null>(null)
  const [warnings, setWarnings] = useState<string[]>([])
  const [leverageStrategy, setLeverageStrategy] = useState<ProductKey | ''>('')
  const [leverage, setLeverage] = useState(LEVERAGE_DEFAULT)

  useEffect(() => {
    let cancelled = false
    setBackendCombined(null)
    setBackendProgram(null)
    setWarnings([])
    setProvenance('loading')
    setProgramDataSource(null)

    const onSettled = (resp: Awaited<ReturnType<typeof fetchPerformance>>) => {
      if (cancelled) return
      setProvenance(resolveChartProvenance(resp, true))
      setBenchmarkSource(readBenchmarkDataSource(resp))
      setProgramDataSource(readProgramDataSource(resp))
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

  const programsWithData = useMemo(
    () => (isCombined ? combinedProgramsWithData(combinedData) : []),
    [isCombined, combinedData],
  )

  const leverageApplies = useMemo(() => {
    if (!leverageStrategy || !isLeverageActive(leverageStrategy, leverage)) return false
    if (isCombined) return programsWithData.includes(leverageStrategy)
    return leverageStrategy === mode
  }, [leverageStrategy, leverage, isCombined, programsWithData, mode])

  const chartData = useMemo(() => {
    if (!leverageApplies || !leverageStrategy) {
      return isCombined ? combinedData : programData
    }
    if (isCombined) {
      return applyLeverageToCombinedSeries(combinedData, leverageStrategy, leverage)
    }
    return applyLeverageToProgramSeries(programData, leverageStrategy, leverage)
  }, [
    leverageApplies,
    leverageStrategy,
    leverage,
    isCombined,
    combinedData,
    programData,
  ])

  const data = chartData

  const legendProducts = useMemo(() => {
    if (!isCombined) return []
    if (provenance === 'backend') return programsWithData
    return PRODUCT_KEYS
  }, [isCombined, provenance, programsWithData])

  const programEntryCount = useMemo(
    () => (isCombined ? 0 : countProgramPoints(programData, mode as ProductKey)),
    [isCombined, programData, mode],
  )

  const displayState = useMemo(() => {
    if (isCombined) {
      const visible = programsWithData.filter((k) => !hiddenProducts.has(k))
      return resolveCombinedChartState(provenance, combinedData, visible)
    }
    return resolveProgramChartState(provenance, programData, mode as ProductKey)
  }, [
    isCombined,
    provenance,
    combinedData,
    programData,
    mode,
    programsWithData,
    hiddenProducts,
  ])

  const combinedDayTicks = useMemo(
    () => (isCombined ? getCombinedDayTicks(combinedData) : []),
    [isCombined, combinedData],
  )
  const monthTicks = useMemo(
    () => (isCombined ? [] : getMonthTicks(programData)),
    [isCombined, programData],
  )

  const lineKeys: SeriesKey[] = isCombined
    ? legendProducts.filter((k) => !hiddenProducts.has(k))
    : [
        mode as ProductKey,
        ...BENCHMARK_KEYS.filter((k) => enabledBenchmarks.has(k)),
      ]

  const canDrawChart =
    displayState !== 'loading' &&
    displayState !== 'empty' &&
    displayState !== 'needs_more' &&
    lineKeys.length > 0

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

  const activeLabel = isCombined ? '' : SERIES_BY_KEY.get(mode as ProductKey)?.label ?? mode
  const notice = provenanceNotice(provenance, mode, benchmarkSource, programDataSource)
  const subtitle = isCombined
    ? combinedModeSubtitle(provenance, programDataSource)
    : programModeSubtitle(
        activeLabel,
        provenance,
        programData,
        getSeriesStartDate(mode as ProductKey),
        formatLongDate,
        benchmarkSource,
        programEntryCount,
        programDataSource,
      )

  const emptyMessage = useMemo(() => {
    if (displayState === 'empty') {
      return isCombined ? combinedEmptyMessage() : programEmptyMessage(mode as ProductKey)
    }
    if (displayState === 'needs_more') {
      if (isCombined) return combinedNeedsMoreMessage()
      const firstDate = programData[0]?.date ?? ''
      return programNeedsMoreMessage(mode as ProductKey, formatLongDate(firstDate))
    }
    return null
  }, [displayState, isCombined, mode, programData])

  const { visible: visibleWarnings, diagnostic: diagnosticWarnings } = useMemo(
    () => partitionChartWarnings(warnings, mode),
    [warnings, mode],
  )

  const benchmarksVisible = showBenchmarkToggles(
    provenance,
    benchmarkSource,
    programEntryCount > 0,
  )
  const showDots = shouldShowDots(displayState)
  const lineType = chartLineType(displayState)
  const chartHeight = chartHeightPx(displayState)

  const seriesLabel = (key: SeriesKey): string => {
    if (
      leverageApplies &&
      leverageStrategy &&
      key === leverageStrategy &&
      (PRODUCT_KEYS as string[]).includes(key)
    ) {
      return leverageSimulatedLabel(leverageStrategy, leverage)
    }
    return seriesDisplayLabel(key, provenance, benchmarkSource)
  }

  const leverageSliderDisabled = !leverageStrategy

  return (
    <section className={styles.card}>
      <div className={styles.head}>
        <div className={styles.heading}>
          <h2 className={styles.title}>Performance of $100,000 Investment</h2>
          {subtitle && <p className={styles.subtitle}>{subtitle}</p>}
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

      {displayState === 'sparse' && (
        <p className={styles.sparseNote} role="note">
          {sparseDataNote()}
        </p>
      )}

      <div className={styles.leverageBar} aria-label="Leverage simulator">
        <span className={styles.leverageTitle}>Leverage simulator</span>
        <label className={styles.leverageField}>
          <span className={styles.leverageFieldLabel}>Strategy</span>
          <select
            className={styles.leverageSelect}
            value={leverageStrategy}
            onChange={(e) => {
              const v = e.target.value
              setLeverageStrategy(v === '' ? '' : (v as ProductKey))
              if (v === '') setLeverage(LEVERAGE_DEFAULT)
            }}
          >
            <option value="">None</option>
            {LEVERAGE_SIMULATOR_STRATEGIES.map((key) => (
              <option key={key} value={key}>
                {key}
              </option>
            ))}
          </select>
        </label>
        <label className={styles.leverageField}>
          <span className={styles.leverageFieldLabel}>
            {formatLeverageMultiple(leverage)}
          </span>
          <input
            className={styles.leverageRange}
            type="range"
            min={LEVERAGE_MIN}
            max={LEVERAGE_MAX}
            step={LEVERAGE_STEP}
            value={leverage}
            disabled={leverageSliderDisabled}
            onChange={(e) => setLeverage(Number(e.target.value))}
            aria-label="Leverage multiplier"
          />
        </label>
        <p className={styles.leverageNote}>{LEVERAGE_SIMULATOR_NOTE}</p>
      </div>

      <div className={styles.legend}>
        {isCombined
          ? legendProducts.map((key) => {
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
                  {seriesLabel(key)}
                </button>
              )
            })
          : (() => {
              const active = SERIES_BY_KEY.get(mode)!
              return (
                <>
                  <span className={styles.activeSeriesChip}>
                    <span className={styles.swatch} style={{ background: active.color }} />
                    {seriesLabel(mode as ProductKey)}
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

      {visibleWarnings.length > 0 && (
        <p className={styles.warningNote}>{visibleWarnings.join(' ')}</p>
      )}

      {diagnosticWarnings.length > 0 && (
        <details className={styles.diagnostics}>
          <summary>Data details ({diagnosticWarnings.length})</summary>
          <ul className={styles.diagnosticsList}>
            {diagnosticWarnings.map((w) => (
              <li key={w}>{w}</li>
            ))}
          </ul>
        </details>
      )}

      <div
        className={styles.chartWrap}
        style={{ height: chartHeight }}
        data-display-state={displayState}
      >
        {!canDrawChart ? (
          <div className={styles.emptyState}>
            {emptyMessage ??
              (lineKeys.length === 0
                ? 'No series selected — enable a strategy above to see the chart.'
                : 'Loading chart…')}
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
                  ticks={combinedDayTicks}
                  allowDecimals={false}
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
                    type={lineType}
                    dataKey={key}
                    name={seriesLabel(key)}
                    stroke={s.color}
                    strokeWidth={s.strokeWidth}
                    strokeDasharray={s.dashed ? '5 4' : undefined}
                    dot={showDots ? { r: 4, strokeWidth: 0 } : false}
                    activeDot={{ r: showDots ? 5 : 3.5, strokeWidth: 0 }}
                    connectNulls={false}
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
