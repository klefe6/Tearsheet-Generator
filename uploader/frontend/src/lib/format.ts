// Small display formatters shared across the UI.

const USD_TWO_DECIMALS = new Intl.NumberFormat('en-US', {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
})

/** Display-only: format a finite amount with thousands separators and exactly 2 decimals. */
function formatUsdTwoDecimals(amount: number): string {
  return USD_TWO_DECIMALS.format(amount)
}

/** Currency with thousands separators and two decimal places. Zero renders as
 *  an em dash to keep financial tables uncluttered. */
export function formatCurrency(value: string | number): string {
  const n = typeof value === 'number' ? value : Number(value)
  if (!Number.isFinite(n)) return '—'
  if (n === 0) return '—'
  const abs = formatUsdTwoDecimals(Math.abs(n))
  return n < 0 ? `-$${abs}` : `$${abs}`
}

/** Normalize a currency input string to two decimal places (blur/paste).
 *  Plain numeric string for `<input type="number">` — no thousands separators. */
export function formatCurrencyInput(raw: string): string {
  const trimmed = raw.trim()
  if (!trimmed) return ''
  const n = Number(trimmed)
  if (!Number.isFinite(n)) return raw
  return n.toFixed(2)
}

/** Compact axis label, e.g. 120000 -> "$120k". */
export function formatAxisCurrency(value: number): string {
  return `$${Math.round(value / 1000)}k`
}

/** Full-precision currency for tooltips, e.g. "$118,240.50". */
export function formatTooltipCurrency(value: number): string {
  if (!Number.isFinite(value)) return '—'
  return `$${formatUsdTwoDecimals(value)}`
}

/** ISO date (YYYY-MM-DD) -> compact "MM/DD/YY" for narrow tables. */
export function formatShortDate(iso: string): string {
  const [y, m, d] = iso.split('-')
  if (!y || !m || !d) return iso
  return `${m}/${d}/${y.slice(2)}`
}

/** ISO date -> "Mon 'YY" for chart axis ticks. */
export function formatAxisDate(iso: string): string {
  const dt = new Date(`${iso}T00:00:00Z`)
  if (Number.isNaN(dt.getTime())) return iso
  const month = dt.toLocaleString('en-US', { month: 'short', timeZone: 'UTC' })
  return `${month} '${String(dt.getUTCFullYear()).slice(2)}`
}

/** ISO date -> "Mon D, YYYY" for the tooltip heading. */
export function formatLongDate(iso: string): string {
  const dt = new Date(`${iso}T00:00:00Z`)
  if (Number.isNaN(dt.getTime())) return iso
  return dt.toLocaleString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    timeZone: 'UTC',
  })
}
