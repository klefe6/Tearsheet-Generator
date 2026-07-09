import { useState, type CSSProperties, type FormEvent } from 'react'
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
              <span className={styles.currencyWrap}>
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
