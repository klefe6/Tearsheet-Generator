import { useMemo, useState } from 'react'
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import {
  DEFAULT_RANGE_KEY,
  RANGE_OPTIONS,
  SERIES,
  getMonthTicks,
  getNormalizedData,
  type SeriesKey,
} from '../data/performance'
import {
  formatAxisCurrency,
  formatAxisDate,
  formatLongDate,
  formatTooltipCurrency,
} from '../lib/format'
import styles from './PerformanceChart.module.css'

// Concrete hex (not CSS vars): Recharts writes these as SVG presentation
// attributes, which don't resolve var().
const AXIS_MUTED = '#8a8f98'
const GRID = '#eef0f3'
const BORDER = '#e6e8ec'
const CURSOR = '#c9ced6'

interface TooltipEntry {
  dataKey: SeriesKey
  name: string
  value: number
  color: string
}

interface ChartTooltipProps {
  active?: boolean
  payload?: TooltipEntry[]
  label?: string
}

function ChartTooltip({ active, payload, label }: ChartTooltipProps) {
  if (!active || !payload || payload.length === 0) return null
  const rows = [...payload].sort((a, b) => b.value - a.value)
  return (
    <div className={styles.tooltip}>
      <div className={styles.tooltipDate}>{formatLongDate(label ?? '')}</div>
      <ul className={styles.tooltipList}>
        {rows.map((entry) => (
          <li key={entry.dataKey} className={styles.tooltipRow}>
            <span className={styles.tooltipDot} style={{ background: entry.color }} />
            <span className={styles.tooltipName}>{entry.name}</span>
            <span className={styles.tooltipVal}>{formatTooltipCurrency(entry.value)}</span>
          </li>
        ))}
      </ul>
    </div>
  )
}

export function PerformanceChart() {
  const [rangeKey, setRangeKey] = useState(DEFAULT_RANGE_KEY)
  const [hidden, setHidden] = useState<Set<SeriesKey>>(() => new Set())

  const range =
    RANGE_OPTIONS.find((r) => r.key === rangeKey) ?? RANGE_OPTIONS[RANGE_OPTIONS.length - 1]
  const data = useMemo(() => getNormalizedData(range.days), [range.days])
  const monthTicks = useMemo(() => getMonthTicks(data), [data])

  const toggleSeries = (key: SeriesKey) => {
    setHidden((prev) => {
      const next = new Set(prev)
      if (next.has(key)) next.delete(key)
      else next.add(key)
      return next
    })
  }

  return (
    <section className={styles.card}>
      <div className={styles.head}>
        <div className={styles.heading}>
          <h2 className={styles.title}>Performance of $100,000 Investment</h2>
          <p className={styles.subtitle}>
            All series are normalized to a $100,000 starting investment.
          </p>
        </div>
        <div className={styles.rangePill} role="group" aria-label="Date range">
          {RANGE_OPTIONS.map((r) => (
            <button
              key={r.key}
              type="button"
              className={`${styles.rangeBtn} ${r.key === rangeKey ? styles.rangeBtnActive : ''}`}
              onClick={() => setRangeKey(r.key)}
              aria-pressed={r.key === rangeKey}
            >
              {r.label}
            </button>
          ))}
        </div>
      </div>

      <ul className={styles.legend}>
        {SERIES.map((s) => {
          const off = hidden.has(s.key)
          const swatch = s.dashed
            ? `repeating-linear-gradient(90deg, ${s.color} 0 6px, transparent 6px 10px)`
            : s.color
          return (
            <li key={s.key}>
              <button
                type="button"
                className={`${styles.legendItem} ${off ? styles.legendOff : ''}`}
                onClick={() => toggleSeries(s.key)}
                aria-pressed={!off}
              >
                <span className={styles.swatch} style={{ background: swatch }} />
                {s.label}
              </button>
            </li>
          )
        })}
      </ul>

      <div className={styles.chartWrap}>
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 8, right: 18, bottom: 4, left: 4 }}>
            <CartesianGrid stroke={GRID} vertical={false} />
            <XAxis
              dataKey="date"
              ticks={monthTicks}
              tickFormatter={formatAxisDate}
              tick={{ fill: AXIS_MUTED, fontSize: 12 }}
              tickMargin={10}
              minTickGap={28}
              axisLine={{ stroke: BORDER }}
              tickLine={false}
            />
            <YAxis
              tickFormatter={formatAxisCurrency}
              tick={{ fill: AXIS_MUTED, fontSize: 12 }}
              width={58}
              axisLine={false}
              tickLine={false}
              domain={['auto', 'auto']}
            />
            <Tooltip
              content={<ChartTooltip />}
              cursor={{ stroke: CURSOR, strokeWidth: 1 }}
            />
            {SERIES.map((s) => (
              <Line
                key={s.key}
                type="monotone"
                dataKey={s.key}
                name={s.label}
                stroke={s.color}
                strokeWidth={s.strokeWidth}
                strokeDasharray={s.dashed ? '5 4' : undefined}
                dot={false}
                activeDot={{ r: 3.5, strokeWidth: 0 }}
                hide={hidden.has(s.key)}
                isAnimationActive={false}
                connectNulls
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>
    </section>
  )
}
