import { useCallback, useEffect, useRef, useState } from 'react'
import {
  deleteLastRow,
  fetchHealth,
  fetchProgramMetadata,
  fetchProgramRows,
  postExportAll,
  postRow,
} from './api/client'
import { ExportActionBar } from './components/ExportActionBar'
import { PageHeader } from './components/PageHeader'
import { PerformanceChart } from './components/PerformanceChart'
import { ProductCard, type DateStepSignal } from './components/ProductCard'
import { Toast } from './components/Toast'
import { applyProgramMetadata, fromApiRow, PRODUCTS, toApiRowPayload } from './config/products'
import { INITIAL_ROWS } from './data/rows'
import { deriveExportState, exportToastMessage, offlineMockExportState } from './lib/exportStatus'
import type { ApiHealthResponse } from './api/client'
import type { ExportUiState, ProductConfig, ProductId, ProductRow } from './types'
import styles from './App.module.css'

const PRODUCTS_BY_ID = new Map(PRODUCTS.map((p) => [p.id, p]))

const APP_ENV = import.meta.env.VITE_APP_ENV || import.meta.env.MODE || 'sandbox'

const INITIAL_EXPORT_STATE: ExportUiState = {
  lastExportAt: null,
  overallStatus: 'idle',
  canUndo: false,
  rowCount: 0,
  programStatuses: [],
}

const INITIAL_DATE_STEP_SIGNAL: DateStepSignal = { delta: 1, nonce: 0 }

export default function App() {
  // Product config renders immediately from the local mock; if the backend
  // answers the one optional metadata GET, its account-chip data overlays it.
  const [products, setProducts] = useState<ProductConfig[]>(PRODUCTS)
  const [health, setHealth] = useState<ApiHealthResponse | null>(null)
  const [rowsByProduct, setRowsByProduct] =
    useState<Record<ProductId, ProductRow[]>>(INITIAL_ROWS)
  const [exportState, setExportState] = useState<ExportUiState>(INITIAL_EXPORT_STATE)
  const [toast, setToast] = useState<string | null>(null)
  // Bumped after a backend-confirmed Enter/Delete/Export so the chart
  // refetches immediately, per the uploader-backend wiring contract.
  const [perfRefreshToken, setPerfRefreshToken] = useState(0)
  const toastTimer = useRef<number | undefined>(undefined)
  const exportTimer = useRef<number | undefined>(undefined)
  // Global date stepper: bumping "nonce" (re-)fires every card's shift
  // effect, even when "delta" repeats (e.g. two "-" clicks in a row). Frontend
  // form state only — never touches historical table rows or the backend.
  const [dateStepSignal, setDateStepSignal] = useState<DateStepSignal>(INITIAL_DATE_STEP_SIGNAL)

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
    fetchHealth().then((body) => {
      if (!cancelled && body) setHealth(body)
    })
    return () => {
      cancelled = true
    }
  }, [])

  // Best-effort initial rows load, per program, in parallel. Same
  // graceful-fallback shape as the metadata fetch above: a program whose
  // fetch fails (backend down, CORS, timeout) simply keeps its INITIAL_ROWS
  // mock seed — local preview never requires a running backend.
  useEffect(() => {
    let cancelled = false
    Promise.all(
      PRODUCTS.map(async (config) => {
        const fresh = await fetchProgramRows(config.id, 7)
        return { id: config.id, rows: fresh ? fresh.rows.map((r) => fromApiRow(config, r)) : null }
      }),
    ).then((results) => {
      if (cancelled) return
      setRowsByProduct((prev) => {
        const next = { ...prev }
        for (const r of results) if (r.rows) next[r.id] = r.rows
        return next
      })
    })
    return () => {
      cancelled = true
    }
  }, [])

  // Enter: try the real backend first (POST /api/rows/{program}); fall back
  // to the previous local-only append when the backend is unreachable so the
  // tool keeps working standalone. A backend that IS reachable but rejects
  // the row (validation error) is a real error — surfaced via toast, never
  // silently treated as success.
  const handleAddRow = useCallback(
    async (productId: ProductId, row: ProductRow) => {
      const config = PRODUCTS_BY_ID.get(productId)!
      const result = await postRow(productId, toApiRowPayload(config, row))

      if (result.ok) {
        const fresh = await fetchProgramRows(productId, 7)
        setRowsByProduct((prev) => ({
          ...prev,
          [productId]: fresh
            ? fresh.rows.map((r) => fromApiRow(config, r))
            : [...prev[productId], row],
        }))
        setPerfRefreshToken((t) => t + 1)
        return
      }

      if (result.reason === 'network') {
        setRowsByProduct((prev) => ({ ...prev, [productId]: [...prev[productId], row] }))
        return
      }

      const detail =
        result.detail && typeof result.detail === 'object' && 'errors' in result.detail
          ? JSON.stringify((result.detail as { errors: unknown }).errors)
          : `HTTP ${result.status}`
      showToast(`Could not save this ${config.code} row — ${detail}`)
    },
    [showToast],
  )

  // Delete Last Row: try the real backend first (DELETE .../last); fall back
  // to the previous local-only trim on network failure OR when the backend
  // says there's nothing to delete (e.g. this row was only ever local mock
  // data and never reached the backend).
  const handleDeleteLast = useCallback(async (productId: ProductId) => {
    const config = PRODUCTS_BY_ID.get(productId)!
    const result = await deleteLastRow(productId)

    if (result.ok) {
      const fresh = await fetchProgramRows(productId, 7)
      setRowsByProduct((prev) => ({
        ...prev,
        [productId]: fresh
          ? fresh.rows.map((r) => fromApiRow(config, r))
          : prev[productId].slice(0, -1),
      }))
      setPerfRefreshToken((t) => t + 1)
      return
    }

    setRowsByProduct((prev) =>
      prev[productId].length === 0 ? prev : { ...prev, [productId]: prev[productId].slice(0, -1) },
    )
  }, [])

  // Export All Changes: try the real backend's own dry-run-safe preview
  // (POST /api/export/all — that endpoint guarantees it never calls the four
  // TKP/TCP/AGM/Y&Q websites; nothing here adds, enables, or bypasses that).
  // Falls back to the previous purely-local simulation when unreachable.
  const handleExport = useCallback(async () => {
    const total = Object.values(rowsByProduct).reduce((sum, rows) => sum + rows.length, 0)
    const exportedAt = new Date()

    window.clearTimeout(exportTimer.current)
    setExportState({
      lastExportAt: exportedAt,
      overallStatus: 'pending',
      canUndo: false,
      rowCount: total,
      programStatuses: [],
    })

    const result = await postExportAll()

    if (result.ok) {
      const nextState = deriveExportState(result.data, exportedAt)
      showToast(exportToastMessage(result.data, APP_ENV))
      setExportState(nextState)
      setPerfRefreshToken((t) => t + 1)
      return
    }

    showToast(
      `Prepared ${total} rows across TKP, TCP, AGM and Y&Q for export — mock action ` +
        `(${APP_ENV}). Nothing was sent to the backend.`,
    )

    // Simulate a short processing window, then show the offline/mock result.
    exportTimer.current = window.setTimeout(() => {
      setExportState(offlineMockExportState(total, exportedAt))
    }, 1100)
  }, [rowsByProduct, showToast])

  const handleUndo = useCallback(() => {
    window.clearTimeout(exportTimer.current)
    setExportState(INITIAL_EXPORT_STATE)
    showToast('Last merge undone — mock action. No backend call was made.')
  }, [showToast])

  // Shift all 4 current (in-progress) date form inputs by one day. Purely
  // local form state — never touches the historical rows shown in the tables.
  const stepAllDates = useCallback((delta: -1 | 1) => {
    setDateStepSignal((prev) => ({ delta, nonce: prev.nonce + 1 }))
  }, [])

  return (
    <div className={styles.page}>
      <PageHeader env={APP_ENV} health={health} />

      <PerformanceChart refreshToken={perfRefreshToken} />

      <div className={styles.cardsSection}>
        <button
          type="button"
          className={styles.dateStepBtn}
          onClick={() => stepAllDates(-1)}
          aria-label="Shift all current dates back one day"
          title="Shift all current dates back 1 day"
        >
          -
        </button>

        <section className={styles.cardsRow} aria-label="Daily entry by product">
          {products.map((config) => (
            <ProductCard
              key={config.id}
              config={config}
              rows={rowsByProduct[config.id]}
              onAddRow={handleAddRow}
              onDeleteLast={handleDeleteLast}
              dateStepSignal={dateStepSignal}
            />
          ))}
        </section>

        <button
          type="button"
          className={styles.dateStepBtn}
          onClick={() => stepAllDates(1)}
          aria-label="Shift all current dates forward one day"
          title="Shift all current dates forward 1 day"
        >
          +
        </button>
      </div>

      <ExportActionBar
        exportState={exportState}
        onExport={handleExport}
        onUndo={handleUndo}
      />

      <Toast message={toast} onDismiss={() => setToast(null)} />
    </div>
  )
}
