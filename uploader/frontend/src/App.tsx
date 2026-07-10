import { useCallback, useEffect, useRef, useState } from 'react'
import { fetchProgramMetadata } from './api/client'
import { ExportActionBar } from './components/ExportActionBar'
import { PageHeader } from './components/PageHeader'
import { PerformanceChart } from './components/PerformanceChart'
import { ProductCard } from './components/ProductCard'
import { Toast } from './components/Toast'
import { applyProgramMetadata, PRODUCTS } from './config/products'
import { INITIAL_ROWS } from './data/rows'
import type { ExportUiState, ProductConfig, ProductId, ProductRow } from './types'
import styles from './App.module.css'

const APP_ENV = import.meta.env.VITE_APP_ENV || import.meta.env.MODE || 'sandbox'

const INITIAL_EXPORT_STATE: ExportUiState = {
  lastExportAt: null,
  status: 'idle',
  canUndo: false,
  rowCount: 0,
}

export default function App() {
  // Product config renders immediately from the local mock; if the backend
  // answers the one optional metadata GET, its account-chip data overlays it.
  const [products, setProducts] = useState<ProductConfig[]>(PRODUCTS)
  const [rowsByProduct, setRowsByProduct] =
    useState<Record<ProductId, ProductRow[]>>(INITIAL_ROWS)
  const [exportState, setExportState] = useState<ExportUiState>(INITIAL_EXPORT_STATE)
  const [toast, setToast] = useState<string | null>(null)
  const toastTimer = useRef<number | undefined>(undefined)
  const exportTimer = useRef<number | undefined>(undefined)

  const showToast = useCallback((message: string) => {
    setToast(message)
    window.clearTimeout(toastTimer.current)
    toastTimer.current = window.setTimeout(() => setToast(null), 4600)
  }, [])

  // Best-effort, read-only metadata load. On any failure (backend down,
  // CORS, timeout) fetchProgramMetadata resolves null and the mock config
  // stays — local preview never requires a running backend.
  useEffect(() => {
    let cancelled = false
    fetchProgramMetadata().then((programs) => {
      if (!cancelled && programs) {
        setProducts((prev) => applyProgramMetadata(prev, programs))
      }
    })
    return () => {
      cancelled = true
    }
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
    const exportedAt = new Date()

    window.clearTimeout(exportTimer.current)
    setExportState({
      lastExportAt: exportedAt,
      status: 'pending',
      canUndo: false,
      rowCount: total,
    })

    showToast(
      `Prepared ${total} rows across TKP, TCP, AGM and Y&Q for export — mock action ` +
        `(${APP_ENV}). Nothing was sent to the backend.`,
    )

    // Simulate a short processing window, then show a reassuring processed state.
    exportTimer.current = window.setTimeout(() => {
      setExportState({
        lastExportAt: exportedAt,
        status: 'processed',
        canUndo: true,
        rowCount: total,
      })
    }, 1100)
  }, [rowsByProduct, showToast])

  const handleUndo = useCallback(() => {
    window.clearTimeout(exportTimer.current)
    setExportState(INITIAL_EXPORT_STATE)
    showToast('Last merge undone — mock action. No backend call was made.')
  }, [showToast])

  return (
    <div className={styles.page}>
      <PageHeader env={APP_ENV} />

      <PerformanceChart />

      <section className={styles.cardsRow} aria-label="Daily entry by product">
        {products.map((config) => (
          <ProductCard
            key={config.id}
            config={config}
            rows={rowsByProduct[config.id]}
            onAddRow={handleAddRow}
            onDeleteLast={handleDeleteLast}
          />
        ))}
      </section>

      <ExportActionBar
        exportState={exportState}
        onExport={handleExport}
        onUndo={handleUndo}
      />

      <Toast message={toast} onDismiss={() => setToast(null)} />
    </div>
  )
}
