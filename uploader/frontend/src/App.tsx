import { useCallback, useRef, useState } from 'react'
import { PageHeader } from './components/PageHeader'
import { PerformanceChart } from './components/PerformanceChart'
import { ProductCard } from './components/ProductCard'
import { Toast } from './components/Toast'
import { PRODUCTS } from './config/products'
import { INITIAL_ROWS } from './data/rows'
import type { ProductId, ProductRow } from './types'
import styles from './App.module.css'

const APP_ENV = import.meta.env.VITE_APP_ENV || import.meta.env.MODE || 'sandbox'

export default function App() {
  const [rowsByProduct, setRowsByProduct] =
    useState<Record<ProductId, ProductRow[]>>(INITIAL_ROWS)
  const [toast, setToast] = useState<string | null>(null)
  const toastTimer = useRef<number | undefined>(undefined)

  const showToast = useCallback((message: string) => {
    setToast(message)
    window.clearTimeout(toastTimer.current)
    toastTimer.current = window.setTimeout(() => setToast(null), 4600)
  }, [])

  // Local-state-only mutations. No backend calls — this is the frontend PR.
  const handleAddRow = useCallback((productId: ProductId, row: ProductRow) => {
    setRowsByProduct((prev) => ({ ...prev, [productId]: [...prev[productId], row] }))
  }, [])

  const handleDeleteLast = useCallback((productId: ProductId) => {
    setRowsByProduct((prev) =>
      prev[productId].length === 0
        ? prev
        : { ...prev, [productId]: prev[productId].slice(0, -1) },
    )
  }, [])

  const handleExport = useCallback(() => {
    const total = Object.values(rowsByProduct).reduce((sum, rows) => sum + rows.length, 0)
    showToast(
      `Prepared ${total} rows across TKP, TCP, AGM and Y&Q for export — mock action ` +
        `(${APP_ENV}). Nothing was sent to the backend.`,
    )
  }, [rowsByProduct, showToast])

  return (
    <div className={styles.page}>
      <PageHeader env={APP_ENV} />

      <PerformanceChart />

      <section className={styles.cardsRow} aria-label="Daily entry by product">
        {PRODUCTS.map((config) => (
          <ProductCard
            key={config.id}
            config={config}
            rows={rowsByProduct[config.id]}
            onAddRow={handleAddRow}
            onDeleteLast={handleDeleteLast}
          />
        ))}
      </section>

      <button type="button" className={styles.exportBtn} onClick={handleExport}>
        Export All Changes
      </button>

      <Toast message={toast} onDismiss={() => setToast(null)} />
    </div>
  )
}
