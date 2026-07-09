// Small display formatters shared across the UI.

/** Whole-dollar currency with thousands separators. Zero renders as an em dash
 *  to keep financial tables uncluttered. */
export function formatCurrency(value: string | number): string {
  const n = typeof value === 'number' ? value : Number(value)
  if (!Number.isFinite(n)) return '—'
  if (n === 0) return '—'
  const abs = Math.abs(n).toLocaleString('en-US', {
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  })
  return n < 0 ? `-$${abs}` : `$${abs}`
}

/** Compact axis label, e.g. 120000 -> "$120k". */
export function formatAxisCurrency(value: number): string {
  return `$${Math.round(value / 1000)}k`
}

/** Full-precision currency for tooltips, e.g. "$118,240". */
export function formatTooltipCurrency(value: number): string {
  return `$${Math.round(value).toLocaleString('en-US')}`
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
