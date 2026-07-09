import type { ExportUiState } from '../types'
import styles from './ExportActionBar.module.css'

interface Props {
  exportState: ExportUiState
  onExport: () => void
  onUndo: () => void
}

function CheckIcon() {
  return (
    <svg
      width="14"
      height="14"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2.5"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="M20 6 9 17l-5-5" />
    </svg>
  )
}

function formatExportTime(value: Date): string {
  return value.toLocaleString(undefined, {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  })
}

export function ExportActionBar({ exportState, onExport, onUndo }: Props) {
  const { lastExportAt, status, canUndo, rowCount } = exportState
  const showProcessed = status === 'processed'
  const showPending = status === 'pending'

  return (
    <section className={styles.section} aria-label="Export actions">
      <div className={styles.buttonRow}>
        <button type="button" className={styles.exportBtn} onClick={onExport}>
          Export All Changes
        </button>
        <button
          type="button"
          className={styles.undoBtn}
          onClick={onUndo}
          disabled={!canUndo}
          title={canUndo ? 'Undo the most recent mock export' : 'Available after an export'}
        >
          Undo Last Merge
        </button>
      </div>

      <div className={styles.statusRow}>
        {lastExportAt ? (
          <p className={styles.lastExport}>
            Last export: <time dateTime={lastExportAt.toISOString()}>{formatExportTime(lastExportAt)}</time>
          </p>
        ) : (
          <p className={styles.lastExportMuted}>No exports yet</p>
        )}

        {showPending && (
          <span className={styles.pendingBadge} role="status">
            Processing…
          </span>
        )}

        {showProcessed && (
          <>
            <span className={styles.processedBadge} role="status">
              <CheckIcon />
              Processed
            </span>
            <span className={styles.deliveredNote}>
              {rowCount} rows received by TKP, TCP, AGM &amp; Y&amp;Q
            </span>
          </>
        )}
      </div>
    </section>
  )
}
