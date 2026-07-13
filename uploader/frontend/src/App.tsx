import { useCallback, useEffect, useRef, useState } from 'react'
import {
  deleteLastRow,
  fetchDisplayRows,
  fetchProgramMetadata,
  fetchProgramRows,
  fetchTradingDateStatus,
  postExportAll,
  postRow,
  type ApiDisplayRowsResponse,
  type ApiTradingDateStatus,
} from './api/client'
import { ExportActionBar } from './components/ExportActionBar'
import { PageHeader } from './components/PageHeader'
import { PerformanceChart } from './components/PerformanceChart'
import { ProductCard, type DateStepSignal } from './components/ProductCard'
import { Toast } from './components/Toast'
import { applyProgramMetadata, fromApiRow, PRODUCTS, toApiRowPayload } from './config/products'
import { classifyPendingForm, type FormState } from './lib/pendingRow'
import { deriveExportState, exportToastMessage, offlineMockExportState } from './lib/exportStatus'
import type { ExportUiState, ProductConfig, ProductId, ProductRow } from './types'
import styles from './App.module.css'

const PRODUCTS_BY_ID = new Map(PRODUCTS.map((p) => [p.id, p]))

const APP_ENV = import.meta.env.VITE_APP_ENV || import.meta.env.MODE || 'sandbox'

const EMPTY_ROWS: Record<ProductId, ProductRow[]> = {
  TKP: [],
  TCP: [],
  AGM: [],
  YQ: [],
}

const EMPTY_FORMS: Record<ProductId, FormState | null> = {
  TKP: null,
  TCP: null,
  AGM: null,
  YQ: null,
}

const INITIAL_EXPORT_STATE: ExportUiState = {
  lastExportAt: null,
  overallStatus: 'idle',
  canUndo: false,
  rowCount: 0,
  programStatuses: [],
}

const INITIAL_DATE_STEP_SIGNAL: DateStepSignal = { delta: 1, nonce: 0 }

function mutationErrorDetail(result: {
  reason: 'rejected' | 'network'
  status?: number
  detail?: unknown
}): string {
  if (result.reason === 'network') {
    return 'backend unreachable (network/CORS/timeout) — values were NOT saved'
  }
  if (result.detail && typeof result.detail === 'object' && 'errors' in result.detail) {
    return JSON.stringify((result.detail as { errors: unknown }).errors)
  }
  return `HTTP ${result.status ?? '?'}`
}

export default function App() {
  // Product config renders immediately from the local mock; if the backend
  // answers the one optional metadata GET, its account-chip data overlays it.
  const [products, setProducts] = useState<ProductConfig[]>(PRODUCTS)
  const [tradingDates, setTradingDates] = useState<ApiTradingDateStatus | null>(null)
  // Manual daily_rows only — start empty so mock seed never looks "saved".
  const [rowsByProduct, setRowsByProduct] =
    useState<Record<ProductId, ProductRow[]>>(EMPTY_ROWS)
  // Bottom-table data: latest merged manual + labeled backfilled rows from
  // GET /api/display-rows. null = backend unreachable — the card falls back
  // to rendering the local manual rows exactly as before this feature.
  const [displayByProduct, setDisplayByProduct] = useState<
    Record<ProductId, ApiDisplayRowsResponse | null>
  >({ TKP: null, TCP: null, AGM: null, YQ: null })
  const [pendingForms, setPendingForms] =
    useState<Record<ProductId, FormState | null>>(EMPTY_FORMS)
  const [exportState, setExportState] = useState<ExportUiState>(INITIAL_EXPORT_STATE)
  const [toast, setToast] = useState<string | null>(null)
  // Bumped after a backend-confirmed Save/Delete/Export so the chart
  // refetches immediately, per the uploader-backend wiring contract.
  const [perfRefreshToken, setPerfRefreshToken] = useState(0)
  const toastTimer = useRef<number | undefined>(undefined)
  const exportTimer = useRef<number | undefined>(undefined)
  // Global date stepper: bumping "nonce" (re-)fires every card's shift
  // effect, even when "delta" repeats (e.g. two "-" clicks in a row). Frontend
  // form state only — never touches historical table rows or the backend.
  const [dateStepSignal, setDateStepSignal] = useState<DateStepSignal>(INITIAL_DATE_STEP_SIGNAL)
  const [pendingClearByProduct, setPendingClearByProduct] = useState<Record<ProductId, number>>({
    TKP: 0,
    TCP: 0,
    AGM: 0,
    YQ: 0,
  })

  const showToast = useCallback((message: string) => {
    setToast(message)
    window.clearTimeout(toastTimer.current)
    toastTimer.current = window.setTimeout(() => setToast(null), 5200)
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
    fetchTradingDateStatus().then((body) => {
      if (!cancelled && body) setTradingDates(body)
    })
    return () => {
      cancelled = true
    }
  }, [])

  // Refresh the display tables (all programs, or just one after a mutation).
  const refreshDisplayRows = useCallback(async (productId?: ProductId) => {
    const targets = productId ? [productId] : PRODUCTS.map((p) => p.id)
    const results = await Promise.all(
      targets.map(async (id) => ({ id, data: await fetchDisplayRows(id, 7) })),
    )
    setDisplayByProduct((prev) => {
      const next = { ...prev }
      for (const r of results) if (r.data) next[r.id] = r.data
      return next
    })
  }, [])

  useEffect(() => {
    refreshDisplayRows()
  }, [refreshDisplayRows])

  // Best-effort initial rows load. Empty server => empty tables (never pretend
  // mock seed rows were saved). Failed fetch leaves that program empty too.
  useEffect(() => {
    let cancelled = false
    Promise.all(
      PRODUCTS.map(async (config) => {
        const fresh = await fetchProgramRows(config.id, 7)
        return { id: config.id, rows: fresh ? fresh.rows.map((r) => fromApiRow(config, r)) : [] }
      }),
    ).then((results) => {
      if (cancelled) return
      setRowsByProduct(() => {
        const next = { ...EMPTY_ROWS }
        for (const r of results) next[r.id] = r.rows
        return next
      })
    })
    return () => {
      cancelled = true
    }
  }, [])

  const handlePendingChange = useCallback((productId: ProductId, form: FormState) => {
    setPendingForms((prev) => ({ ...prev, [productId]: form }))
  }, [])

  // Save Daily Row: POST /api/rows/{program}. Network/rejection failures are
  // ALWAYS visible — never silently append local-only rows (that made Glenn
  // think values were saved while /api/rows stayed empty).
  const handleAddRow = useCallback(
    async (
      productId: ProductId,
      row: ProductRow,
      opts?: { quiet?: boolean },
    ): Promise<boolean> => {
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
        refreshDisplayRows(productId)
        setPerfRefreshToken((t) => t + 1)
        if (!opts?.quiet) {
          showToast(`Saved to backend · ${config.code} · ${String(row.date)}`)
        }
        return true
      }

      showToast(`Could not save this ${config.code} row — ${mutationErrorDetail(result)}`)
      return false
    },
    [showToast, refreshDisplayRows],
  )

  // Delete Last Row: try the real backend first (DELETE .../last).
  const handleDeleteLast = useCallback(
    async (productId: ProductId) => {
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
        refreshDisplayRows(productId)
        setPerfRefreshToken((t) => t + 1)
        return
      }

      showToast(
        `Could not delete last ${config.code} row — ${mutationErrorDetail(result)}`,
      )
    },
    [refreshDisplayRows, showToast],
  )

  /**
   * Export All Changes:
   *  1. Save any pending valid card forms to backend daily_rows first.
   *  2. Re-read /api/rows/{program} counts.
   *  3. POST /api/export/all (dry-run/real per server flags).
   * Incomplete pending forms or save failures block the export.
   */
  const handleExport = useCallback(async () => {
    const exportedAt = new Date()
    window.clearTimeout(exportTimer.current)

    setExportState({
      lastExportAt: exportedAt,
      overallStatus: 'pending',
      canUndo: false,
      rowCount: 0,
      programStatuses: [],
      preflightNote: 'Checking unsaved form values…',
    })

    // --- 1. Save pending forms first ---------------------------------
    const pendingReady: { productId: ProductId; row: ProductRow }[] = []
    for (const config of PRODUCTS) {
      const form = pendingForms[config.id]
      if (!form) continue
      const classified = classifyPendingForm(config, form)
      if (classified.status === 'empty') continue
      if (classified.status === 'incomplete') {
        const msg =
          `You have unsaved ${config.code} values missing required fields ` +
          `(${classified.missing.join(', ')}). Fill them and click Save Daily Row, or clear the inputs.`
        showToast(msg)
        setExportState({
          ...INITIAL_EXPORT_STATE,
          lastExportAt: exportedAt,
          overallStatus: 'failed',
          preflightNote: msg,
        })
        return
      }
      if (classified.status === 'invalid') {
        const msg = `Unsaved ${config.code} row is invalid: ${classified.message}`
        showToast(msg)
        setExportState({
          ...INITIAL_EXPORT_STATE,
          lastExportAt: exportedAt,
          overallStatus: 'failed',
          preflightNote: msg,
        })
        return
      }
      pendingReady.push({ productId: classified.productId, row: classified.row })
    }

    let savedPending = 0
    for (const item of pendingReady) {
      const ok = await handleAddRow(item.productId, item.row, { quiet: true })
      if (!ok) {
        const msg =
          `Export blocked — could not save pending ${item.productId} row to the backend. ` +
          `Fix the error and try again.`
        showToast(msg)
        setExportState({
          ...INITIAL_EXPORT_STATE,
          lastExportAt: exportedAt,
          overallStatus: 'failed',
          preflightNote: msg,
        })
        return
      }
      savedPending += 1
    }

    if (savedPending > 0) {
      setPendingClearByProduct((prev) => {
        const next = { ...prev }
        for (const item of pendingReady) next[item.productId] += 1
        return next
      })
    }

    // --- 2. Re-read manual daily_rows --------------------------------
    const manualRowsByProgram: Partial<Record<ProductId, number>> = {}
    await Promise.all(
      PRODUCTS.map(async (config) => {
        const fresh = await fetchProgramRows(config.id, 50)
        const rows = fresh ? fresh.rows.map((r) => fromApiRow(config, r)) : []
        manualRowsByProgram[config.id] = rows.length
        setRowsByProduct((prev) => ({ ...prev, [config.id]: rows }))
      }),
    )
    const manualTotal = Object.values(manualRowsByProgram).reduce(
      (sum, n) => sum + (n ?? 0),
      0,
    )

    if (manualTotal === 0) {
      const msg =
        'Export All found 0 manual rows on the backend. ' +
        'Type values and click Save Daily Row (or leave valid values in the form — Export will save them first). ' +
        'Backfilled display-table history is never exported.'
      showToast(msg)
      setExportState({
        lastExportAt: exportedAt,
        overallStatus: 'saved',
        canUndo: false,
        rowCount: 0,
        programStatuses: [],
        manualRowsByProgram,
        eligibleCount: 0,
        preflightNote: msg,
      })
      return
    }

    // --- 3. Run export -----------------------------------------------
    setExportState((prev) => ({
      ...prev,
      overallStatus: 'pending',
      manualRowsByProgram,
      preflightNote:
        savedPending > 0
          ? `Saved ${savedPending} pending row${savedPending === 1 ? '' : 's'} first; exporting…`
          : `Found ${manualTotal} manual row${manualTotal === 1 ? '' : 's'}; exporting…`,
    }))

    const result = await postExportAll()

    if (result.ok) {
      const nextState = deriveExportState(result.data, exportedAt)
      nextState.manualRowsByProgram = manualRowsByProgram
      nextState.preflightNote =
        savedPending > 0
          ? `Saved ${savedPending} pending form row${savedPending === 1 ? '' : 's'} before export.`
          : undefined
      if (result.data.total_rows === 0) {
        showToast(
          `Export completed with 0 eligible rows (manual rows on backend: ${manualTotal}). ` +
            `Already-exported rows are skipped. (${APP_ENV})`,
        )
      } else {
        showToast(exportToastMessage(result.data, APP_ENV))
      }
      setExportState(nextState)
      setPerfRefreshToken((t) => t + 1)
      refreshDisplayRows()
      return
    }

    showToast(
      `Export failed — backend unreachable. Manual rows on server: ${manualTotal}. ` +
        `Nothing was sent downstream. (${APP_ENV})`,
    )
    exportTimer.current = window.setTimeout(() => {
      setExportState({
        ...offlineMockExportState(0, exportedAt),
        manualRowsByProgram,
        eligibleCount: 0,
        preflightNote: 'Backend unreachable during Export All.',
      })
    }, 400)
  }, [pendingForms, handleAddRow, showToast, refreshDisplayRows])

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

  const defaultEntryDate = tradingDates?.last_trading_date ?? null

  return (
    <div className={styles.page}>
      <PageHeader env={APP_ENV} tradingDates={tradingDates} />

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
              displayData={displayByProduct[config.id]}
              onAddRow={handleAddRow}
              onDeleteLast={handleDeleteLast}
              onPendingChange={handlePendingChange}
              pendingClearNonce={pendingClearByProduct[config.id]}
              dateStepSignal={dateStepSignal}
              defaultEntryDate={defaultEntryDate}
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

      <p className={styles.tablesNote} role="note">
        Latest values include historical backfill where available. Export All
        only includes rows manually saved to the backend (Save Daily Row). Typing
        alone does not save. Export will auto-save any valid unfinished form
        values first.
      </p>

      <ExportActionBar
        exportState={exportState}
        onExport={handleExport}
        onUndo={handleUndo}
      />

      <Toast message={toast} onDismiss={() => setToast(null)} />
    </div>
  )
}
