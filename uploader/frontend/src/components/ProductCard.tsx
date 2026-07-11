import { useEffect, useRef, useState, type CSSProperties, type FormEvent } from 'react'
import type { ApiDisplayRowsResponse } from '../api/client'
import { MAX_PRODUCT_FIELD_COUNT } from '../config/products'
import { displayColumnsFor, type DisplayColumn } from '../lib/displayColumns'
import {
  classifyPendingForm,
  type FormState,
} from '../lib/pendingRow'
import type { ProductConfig, ProductId, ProductRow } from '../types'
import { formatCurrency, formatShortDate } from '../lib/format'
import styles from './ProductCard.module.css'

/** One shift request from the global date-step buttons ("nonce" makes repeat clicks re-fire the effect even when `delta` repeats). */
export interface DateStepSignal {
  delta: -1 | 1
  nonce: number
}

interface Props {
  config: ProductConfig
  rows: ProductRow[]
  /** Latest merged manual + backfilled rows (GET /api/display-rows). null =
   *  backend unreachable — the table falls back to the local manual rows. */
  displayData?: ApiDisplayRowsResponse | null
  /** Persist one manual daily row. Resolves true only when the backend saved it. */
  onAddRow: (productId: ProductId, row: ProductRow) => Promise<boolean>
  onDeleteLast: (productId: ProductId) => void
  /** Reports in-progress form state so Export All can save pending rows first. */
  onPendingChange: (productId: ProductId, form: FormState) => void
  /** Bumped after Export All auto-saves pending forms — clears numeric inputs. */
  pendingClearNonce: number
  /** Shifts this card's current date input by ±1 day; local form state only. */
  dateStepSignal: DateStepSignal
}

/** Shift a YYYY-MM-DD string by `days`, safely across month/year boundaries (UTC-anchored to dodge local-timezone DST edge cases). Invalid input is returned unchanged. */
function shiftIsoDate(iso: string, days: number): string {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(iso)
  if (!match) return iso
  const [, y, m, d] = match
  const utc = new Date(Date.UTC(Number(y), Number(m) - 1, Number(d)))
  utc.setUTCDate(utc.getUTCDate() + days)
  return utc.toISOString().slice(0, 10)
}

/** Local date as YYYY-MM-DD, for the native date input default. */
function todayISO(): string {
  const now = new Date()
  const local = new Date(now.getTime() - now.getTimezoneOffset() * 60_000)
  return local.toISOString().slice(0, 10)
}

function initialForm(config: ProductConfig): FormState {
  const state: FormState = {}
  for (const field of config.fields) {
    state[field.key] = field.type === 'date' ? todayISO() : ''
  }
  return state
}

/** Legacy clipboard fallback for contexts without navigator.clipboard. */
function legacyCopy(text: string): void {
  const area = document.createElement('textarea')
  area.value = text
  area.setAttribute('readonly', '')
  area.style.position = 'fixed'
  area.style.opacity = '0'
  document.body.appendChild(area)
  area.select()
  const ok = document.execCommand('copy')
  document.body.removeChild(area)
  if (!ok) throw new Error('copy rejected')
}

/**
 * Clean a clipboard string into a plain numeric string for a currency input
 * ("$1,234.56" -> "1234.56", "(50.00)" -> "-50", "" / "abc" -> null).
 * Returns null when the clipboard doesn't hold a usable number, so the
 * caller can leave the existing input value untouched.
 */
function parsePastedCurrency(raw: string): string | null {
  const trimmed = raw.trim()
  if (!trimmed) return null
  const parenNegative = /^\(.*\)$/.test(trimmed)
  let cleaned = (parenNegative ? trimmed.slice(1, -1) : trimmed).replace(/[^0-9.-]/g, '')
  const negative = parenNegative || cleaned.startsWith('-')
  cleaned = cleaned.replace(/-/g, '')
  const [whole, ...rest] = cleaned.split('.')
  cleaned = rest.length > 0 ? `${whole}.${rest.join('')}` : whole
  if (!cleaned || cleaned === '.') return null
  const value = Number(`${negative ? '-' : ''}${cleaned}`)
  return Number.isFinite(value) ? String(value) : null
}

/**
 * Subtle chip beside a field label showing a broker account number.
 * Click copies ONLY the account number; brief "Copied" / "Copy failed"
 * feedback replaces the chip text, then it reverts. `label` (broker name,
 * from backend account_label or the mock config) only enriches the
 * tooltip/aria text — the visible chip stays just the number.
 */
function AccountChip({ account, label }: { account: string; label?: string }) {
  const [state, setState] = useState<'idle' | 'copied' | 'error'>('idle')
  const timer = useRef<number | undefined>(undefined)
  const describe = label ? `${label} account number ${account}` : `account number ${account}`

  const handleCopy = async (event: React.MouseEvent<HTMLButtonElement>) => {
    // The chip sits inside the field <label>; don't focus/activate the input.
    event.preventDefault()
    event.stopPropagation()
    try {
      if (navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(account)
      } else {
        legacyCopy(account)
      }
      setState('copied')
    } catch {
      setState('error')
    }
    window.clearTimeout(timer.current)
    timer.current = window.setTimeout(() => setState('idle'), 1600)
  }

  return (
    <button
      type="button"
      className={`${styles.accountChip} ${
        state === 'copied' ? styles.accountChipCopied : ''
      } ${state === 'error' ? styles.accountChipError : ''}`}
      onClick={handleCopy}
      title={`Copy ${describe}`}
      aria-label={`Copy ${describe} to clipboard`}
    >
      {state === 'copied' ? (
        <>
          <svg
            width="10"
            height="10"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="3"
            strokeLinecap="round"
            strokeLinejoin="round"
            aria-hidden="true"
          >
            <path d="M20 6 9 17l-5-5" />
          </svg>
          Copied
        </>
      ) : state === 'error' ? (
        'Copy failed'
      ) : (
        <>
          {account}
          <svg
            width="10"
            height="10"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
            aria-hidden="true"
          >
            <rect x="9" y="9" width="12" height="12" rx="2" />
            <path d="M5 15V5a2 2 0 0 1 2-2h10" />
          </svg>
        </>
      )}
    </button>
  )
}

/**
 * Compact control (stacked under the account chip when one exists) that
 * reads the clipboard and fills THIS field only. Cleans common currency
 * formatting; if the clipboard doesn't hold a usable number, the input is
 * left untouched and a brief "Invalid" state shows instead.
 */
function PasteButton({ onPaste }: { onPaste: (value: string) => void }) {
  const [state, setState] = useState<'idle' | 'pasted' | 'error'>('idle')
  const timer = useRef<number | undefined>(undefined)

  const handlePaste = async (event: React.MouseEvent<HTMLButtonElement>) => {
    // The button sits inside the field <label>; don't focus/activate the input.
    event.preventDefault()
    event.stopPropagation()
    try {
      if (!navigator.clipboard?.readText) throw new Error('clipboard read unavailable')
      const raw = await navigator.clipboard.readText()
      const cleaned = parsePastedCurrency(raw)
      if (cleaned === null) throw new Error('clipboard has no usable number')
      onPaste(cleaned)
      setState('pasted')
    } catch {
      setState('error')
    }
    window.clearTimeout(timer.current)
    timer.current = window.setTimeout(() => setState('idle'), 1600)
  }

  return (
    <button
      type="button"
      className={`${styles.pasteBtn} ${state === 'pasted' ? styles.pasteBtnPasted : ''} ${
        state === 'error' ? styles.pasteBtnError : ''
      }`}
      onClick={handlePaste}
      title="Paste value from clipboard"
      aria-label="Paste value from clipboard"
    >
      {state === 'pasted' ? (
        <>
          <svg
            width="9"
            height="9"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="3"
            strokeLinecap="round"
            strokeLinejoin="round"
            aria-hidden="true"
          >
            <path d="M20 6 9 17l-5-5" />
          </svg>
          Pasted
        </>
      ) : state === 'error' ? (
        'Invalid'
      ) : (
        <>
          <svg
            width="9"
            height="9"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
            aria-hidden="true"
          >
            <rect x="8" y="2" width="8" height="4" rx="1" />
            <path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2" />
          </svg>
          Paste
        </>
      )}
    </button>
  )
}

/** Small financial glyph shown in the colored header. */
function CardGlyph() {
  return (
    <svg
      width="18"
      height="18"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="M4 19V10M9 19V5M14 19v-6M19 19V8" />
    </svg>
  )
}

export function ProductCard({
  config,
  rows,
  displayData = null,
  onAddRow,
  onDeleteLast,
  onPendingChange,
  pendingClearNonce,
  dateStepSignal,
}: Props) {
  const [form, setForm] = useState<FormState>(() => initialForm(config))
  const [saving, setSaving] = useState(false)
  const [saveNote, setSaveNote] = useState<string | null>(null)
  const [saveError, setSaveError] = useState<string | null>(null)

  const update = (key: string, value: string) => {
    setSaveNote(null)
    setSaveError(null)
    setForm((prev) => ({ ...prev, [key]: value }))
  }

  // Keep App aware of unsaved form values (typing alone is never a backend save).
  useEffect(() => {
    onPendingChange(config.id, form)
  }, [config.id, form, onPendingChange])

  // Export All auto-saved this card's pending values — clear numerics so they
  // aren't treated as still-unsaved on the next export.
  useEffect(() => {
    if (pendingClearNonce === 0) return
    setForm((prev) => {
      const next = { ...prev }
      for (const field of config.fields) {
        if (field.type !== 'date') next[field.key] = ''
      }
      return next
    })
    setSaveNote(`Saved to backend via Export All · ${config.code}`)
    setSaveError(null)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pendingClearNonce])

  // Global date stepper: shift this card's own current date field by ±1 day.
  // Skipped on mount (nonce 0) and whenever this card has no date field.
  useEffect(() => {
    if (dateStepSignal.nonce === 0) return
    const dateField = config.fields.find((field) => field.type === 'date')
    if (!dateField) return
    setForm((prev) => ({
      ...prev,
      [dateField.key]: shiftIsoDate(prev[dateField.key], dateStepSignal.delta),
    }))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [dateStepSignal])

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setSaveError(null)
    setSaveNote(null)

    const dateKey = config.fields.find((f) => f.type === 'date')?.key ?? 'date'
    const formWithDate = { ...form, [dateKey]: form[dateKey] || todayISO() }
    const classified = classifyPendingForm(config, formWithDate)

    if (classified.status === 'empty') {
      setSaveError('Enter at least one NLV value before saving.')
      return
    }
    if (classified.status === 'incomplete') {
      setSaveError(`Fill required fields before saving: ${classified.missing.join(', ')}.`)
      return
    }
    if (classified.status === 'invalid') {
      setSaveError(classified.message)
      return
    }

    const row = classified.row
    setSaving(true)
    try {
      const ok = await onAddRow(config.id, row)
      if (!ok) {
        // App already toasted the failure; keep values so Glenn can retry.
        setSaveError('Save failed — values were NOT written to the backend.')
        return
      }
      setSaveNote(`Saved to backend · ${config.code} · ${String(row.date)}`)
      // Keep the date, clear the numeric inputs for the next entry.
      setForm((prev) => {
        const next = { ...prev }
        for (const field of config.fields) {
          if (field.type !== 'date') next[field.key] = ''
        }
        return next
      })
    } finally {
      setSaving(false)
    }
  }

  // Most recent 7 rows, newest first.
  const visibleRows = [...rows].slice(-7).reverse()

  const brandStyle = {
    '--brand': config.color,
    '--brand-soft': config.colorSoft,
  } as CSSProperties

  return (
    <section className={styles.card} style={brandStyle}>
      <header className={styles.head}>
        <span className={styles.icon}>
          <CardGlyph />
        </span>
        <span className={styles.code}>{config.code}</span>
        <span className={styles.account}>{config.account}</span>
      </header>

      <form className={styles.form} onSubmit={handleSubmit}>
        <div
          className={styles.fieldsRegion}
          style={{ '--field-slots': MAX_PRODUCT_FIELD_COUNT } as CSSProperties}
        >
          {config.fields.map((field) => (
            <label key={field.key} className={styles.field}>
              <span className={styles.fieldLabel}>{field.label}</span>
              {field.type === 'date' ? (
                <input
                  type="date"
                  required
                  className={styles.input}
                  value={form[field.key]}
                  onChange={(e) => update(field.key, e.target.value)}
                />
              ) : (
                <span className={styles.inputRow}>
                  <span
                    className={`${styles.currencyWrap} ${
                      field.tint === 'yellow' ? styles.wrapYellow : ''
                    } ${field.tint === 'pink' ? styles.wrapPink : ''}`}
                  >
                    <span className={styles.currencyPrefix}>$</span>
                    <input
                      type="number"
                      inputMode="decimal"
                      step="0.01"
                      className={`${styles.input} ${styles.currencyInput}`}
                      placeholder={field.placeholder}
                      value={form[field.key]}
                      onChange={(e) => update(field.key, e.target.value)}
                    />
                  </span>
                  <span className={styles.controlStack}>
                    {field.accountNumber && (
                      <AccountChip
                        account={field.accountNumber}
                        label={field.accountLabel}
                      />
                    )}
                    <PasteButton onPaste={(value) => update(field.key, value)} />
                  </span>
                </span>
              )}
            </label>
          ))}
        </div>

        <div className={styles.actions}>
          <button type="submit" className={styles.enterBtn} disabled={saving}>
            {saving ? 'Saving…' : 'Save Daily Row'}
          </button>
          <button
            type="button"
            className={styles.deleteBtn}
            onClick={() => onDeleteLast(config.id)}
            disabled={rows.length === 0 || saving}
          >
            Delete Last Row
          </button>
        </div>
        {saveNote && (
          <p className={styles.saveOk} role="status">
            {saveNote}
          </p>
        )}
        {saveError && (
          <p className={styles.saveErr} role="alert">
            {saveError}
          </p>
        )}
      </form>

      <div className={styles.tableWrap}>
        {displayData ? (
          <DisplayRowsTable config={config} data={displayData} />
        ) : (
          <table className={styles.table}>
            <thead>
              <tr>
                {config.columns.map((col) => (
                  <th
                    key={col.key}
                    className={col.format === 'currency' ? styles.num : undefined}
                  >
                    {col.label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {visibleRows.length === 0 ? (
                <tr>
                  <td className={styles.empty} colSpan={config.columns.length}>
                    No rows yet
                  </td>
                </tr>
              ) : (
                visibleRows.map((row) => (
                  <tr key={row.id}>
                    {config.columns.map((col) => (
                      <td
                        key={col.key}
                        className={col.format === 'currency' ? styles.num : undefined}
                      >
                        {col.format === 'date'
                          ? formatShortDate(String(row[col.key]))
                          : formatCurrency(row[col.key])}
                      </td>
                    ))}
                  </tr>
                ))
              )}
            </tbody>
          </table>
        )}
      </div>
    </section>
  )
}

/** Bottom table fed by GET /api/display-rows: latest merged values with a
 *  per-row source badge. Display-only — Export All never reads these rows.
 *  Columns come from displayColumnsFor(): TKP is the only program with both
 *  StoneX NLV and Plus500 NLV columns; AGM adds Fee (manual rows only). */
function DisplayRowsTable({
  config,
  data,
}: {
  config: ProductConfig
  data: ApiDisplayRowsResponse
}) {
  const columns = displayColumnsFor(config)

  const cell = (row: ApiDisplayRowsResponse['rows'][number], col: DisplayColumn) => {
    if (col.key === 'date') return formatShortDate(row.date)
    if (col.key === 'source') {
      return (
        <span
          className={`${styles.srcBadge} ${
            row.source_label === 'Manual' ? styles.srcManual : styles.srcBackfilled
          }`}
          title={row.source_detail ?? row.source_label}
        >
          {row.source_label}
        </span>
      )
    }
    const value = row[col.key]
    return value == null ? '—' : formatCurrency(value as number)
  }

  return (
    <table className={styles.table}>
      <thead>
        <tr>
          {columns.map((col) => (
            <th key={col.key} className={col.numeric ? styles.num : undefined}>
              {col.label}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {data.rows.length === 0 ? (
          <tr>
            <td className={styles.empty} colSpan={columns.length}>
              {data.empty_reason ?? 'No rows yet'}
            </td>
          </tr>
        ) : (
          data.rows.map((row) => (
            <tr key={row.date}>
              {columns.map((col) => (
                <td key={col.key} className={col.numeric ? styles.num : undefined}>
                  {cell(row, col)}
                </td>
              ))}
            </tr>
          ))
        )}
      </tbody>
    </table>
  )
}
