import type { ExportOverallStatus, ExportUiState } from '../types'
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

function WarnIcon() {
  return (
    <svg
      width="13"
      height="13"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2.5"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="M12 9v4M12 17h.01M10.3 3.9 2.5 18a1.5 1.5 0 0 0 1.3 2.2h16.4a1.5 1.5 0 0 0 1.3-2.2L13.7 3.9a1.5 1.5 0 0 0-2.6 0Z" />
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

/** Badge copy + visual class per truthful overall status. Never hides a
 *  failure behind a reassuring label — see docs/downstream_export_contract.md. */
const STATUS_BADGE: Record<
  Exclude<ExportOverallStatus, 'idle' | 'pending'>,
  { label: string; className: keyof typeof styles; icon: 'check' | 'warn' | null }
> = {
  offline_mock: { label: 'Backend Unreachable — Local Only', className: 'mutedBadge', icon: null },
  saved: { label: 'Saved to Uploader Backend', className: 'processedBadge', icon: 'check' },
  dry_run: { label: 'Dry Run — Nothing Written', className: 'dryRunBadge', icon: null },
  sandbox_success: { label: 'Exported to Sandbox', className: 'processedBadge', icon: 'check' },
  partial_failure: { label: 'Partial Failure', className: 'warnBadge', icon: 'warn' },
  failed: { label: 'Failed', className: 'failBadge', icon: 'warn' },
}

const PROGRAM_LABEL: Record<string, string> = { TKP: 'TKP', TCP: 'TCP', AGM: 'AGM', YQ: 'Y&Q' }

function programStatusText(status: string, reason?: string): string {
  switch (status) {
    case 'success':
      return 'exported'
    case 'failure':
      return 'failed'
    case 'partial_failure':
      return 'partial failure'
    case 'skipped':
      return reason ? `skipped — ${reason}` : 'skipped'
    case 'dry_run':
      return 'dry run'
    case 'no_rows':
      return 'nothing to export'
    default:
      return status
  }
}

export function ExportActionBar({ exportState, onExport, onUndo }: Props) {
  const { lastExportAt, overallStatus, canUndo, rowCount, programStatuses, targetEnv } = exportState
  const showPending = overallStatus === 'pending'
  const badge = showPending || overallStatus === 'idle' ? null : STATUS_BADGE[overallStatus]

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

        {badge && (
          <span className={styles[badge.className]} role="status">
            {badge.icon === 'check' && <CheckIcon />}
            {badge.icon === 'warn' && <WarnIcon />}
            {badge.label}
          </span>
        )}

        {overallStatus === 'saved' && (
          <span className={styles.deliveredNote}>
            {rowCount} row{rowCount === 1 ? '' : 's'} saved — downstream export not enabled
          </span>
        )}

        {targetEnv && overallStatus !== 'dry_run' && (
          <span className={styles.deliveredNote}>target: {targetEnv}</span>
        )}
      </div>

      {programStatuses.length > 0 && (
        <ul className={styles.programList} aria-label="Per-program export result">
          {programStatuses.map((p) => (
            <li
              key={p.program}
              className={`${styles.programItem} ${
                p.status === 'failure' || p.status === 'partial_failure'
                  ? styles.programItemFail
                  : p.status === 'skipped'
                    ? styles.programItemSkipped
                    : styles.programItemOk
              }`}
            >
              <strong>{PROGRAM_LABEL[p.program] ?? p.program}</strong>: {programStatusText(p.status, p.reason)}
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}
