import { useRef, useState, type CSSProperties, type FormEvent } from 'react'
import { MAX_PRODUCT_FIELD_COUNT } from '../config/products'
import type { ProductConfig, ProductId, ProductRow } from '../types'
import { makeRowId } from '../data/rows'
import { formatCurrency, formatShortDate } from '../lib/format'
import styles from './ProductCard.module.css'

interface Props {
  config: ProductConfig
  rows: ProductRow[]
  onAddRow: (productId: ProductId, row: ProductRow) => void
  onDeleteLast: (productId: ProductId) => void
}

type FormState = Record<string, string>

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
 * Subtle chip beside a field label showing a broker account number.
 * Click copies ONLY the account number; brief "Copied" / "Copy failed"
 * feedback replaces the chip text, then it reverts.
 */
function AccountChip({ account }: { account: string }) {
  const [state, setState] = useState<'idle' | 'copied' | 'error'>('idle')
  const timer = useRef<number | undefined>(undefined)

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
      title={`Copy account number ${account}`}
      aria-label={`Copy account number ${account} to clipboard`}
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

export function ProductCard({ config, rows, onAddRow, onDeleteLast }: Props) {
  const [form, setForm] = useState<FormState>(() => initialForm(config))

  const update = (key: string, value: string) =>
    setForm((prev) => ({ ...prev, [key]: value }))

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const row: ProductRow = { id: makeRowId(config.id) }
    for (const field of config.fields) {
      if (field.type === 'date') {
        row[field.key] = form[field.key] || todayISO()
      } else {
        const parsed = Number(form[field.key])
        row[field.key] = Number.isFinite(parsed) ? parsed : 0
      }
    }
    onAddRow(config.id, row)
    // Keep the date, clear the numeric inputs for the next entry.
    setForm((prev) => {
      const next = { ...prev }
      for (const field of config.fields) {
        if (field.type !== 'date') next[field.key] = ''
      }
      return next
    })
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
              <span className={styles.fieldLabelRow}>
                <span className={styles.fieldLabel}>{field.label}</span>
                {field.accountNumber && <AccountChip account={field.accountNumber} />}
              </span>
              {field.type === 'date' ? (
                <input
                  type="date"
                  required
                  className={styles.input}
                  value={form[field.key]}
                  onChange={(e) => update(field.key, e.target.value)}
                />
              ) : (
                <span
                  className={`${styles.currencyWrap} ${
                    field.tint === 'purple' ? styles.wrapPurple : ''
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
              )}
            </label>
          ))}
        </div>

        <div className={styles.actions}>
          <button type="submit" className={styles.enterBtn}>
            Enter
          </button>
          <button
            type="button"
            className={styles.deleteBtn}
            onClick={() => onDeleteLast(config.id)}
            disabled={rows.length === 0}
          >
            Delete Last Row
          </button>
        </div>
      </form>

      <div className={styles.tableWrap}>
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
      </div>
    </section>
  )
}
