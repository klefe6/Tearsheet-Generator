import type { ExportOverallStatus, ExportUiState } from '../types'
import { exportStatusIcon } from '../lib/exportStatus'
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

function FailIcon() {
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
      <circle cx="12" cy="12" r="9" />
      <path d="M15 9l-6 6M9 9l6 6" />
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
  { label: string; className: keyof typeof styles }
> = {
  offline_mock: { label: 'Backend Unreachable — Local Only', className: 'mutedBadge' },
  saved: { label: 'Saved to Uploader Backend', className: 'processedBadge' },
  dry_run: { label: 'Dry Run — Nothing Written', className: 'dryRunBadge' },
  downstream_dry_run: {
    label: 'Downstream Dry-Run Validated',
    className: 'dryRunBadge',
  },
  sandbox_success: { label: 'Exported to Sandbox', className: 'processedBadge' },
  pushed: { label: 'Exported and Verified', className: 'processedBadge' },
  pushed_pending_refresh: {
    label: 'Accepted — Awaiting Site Refresh',
    className: 'warnBadge',
  },
  partial_failure: { label: 'Partial Failure', className: 'warnBadge' },
  failed: { label: 'Failed', className: 'failBadge' },
  no_eligible: { label: 'No Eligible Rows', className: 'mutedBadge' },
}

const PROGRAM_LABEL: Record<string, string> = { TKP: 'TKP', TCP: 'TCP', AGM: 'AGM', YQ: 'Y&Q' }

function programStatusText(
  status: string,
  reason?: string,
  verification?: string,
): string {
  switch (status) {
    case 'success':
      return verification === 'verified' ? 'exported and verified' : 'exported'
    case 'pending_refresh':
      return 'accepted — awaiting refresh'
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

function programItemClass(status: string, verification?: string): string {
  if (status === 'failure' || status === 'partial_failure') return styles.programItemFail
  if (status === 'pending_refresh' || verification === 'pending_refresh') {
    return styles.programItemWarn
  }
  if (status === 'success') return styles.programItemOk
  if (status === 'skipped' || status === 'no_rows') return styles.programItemNeutral
  return styles.programItem
}

export function ExportActionBar({ exportState, onExport, onUndo }: Props) {
  const {
    lastExportAt,
    overallStatus,
    canUndo,
    rowCount,
    programStatuses,
    targetEnv,
    manualRowsByProgram,
    eligibleCount,
    excludedCount,
    exportedCount,
    dryRun,
    preflightNote,
  } = exportState
  const showPending = overallStatus === 'pending'
  const badge = showPending || overallStatus === 'idle' ? null : STATUS_BADGE[overallStatus]
  const icon = badge ? exportStatusIcon(overallStatus) : null

  const manualSummary = manualRowsByProgram
    ? (['TKP', 'TCP', 'AGM', 'YQ'] as const)
        .map((p) => `${PROGRAM_LABEL[p] ?? p} ${manualRowsByProgram[p] ?? 0}`)
        .join(' · ')
    : null

  const skipped = programStatuses.filter((p) => p.status === 'skipped' || p.status === 'no_rows')

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
            {icon === 'check' && <CheckIcon />}
            {icon === 'warn' && <WarnIcon />}
            {icon === 'fail' && <FailIcon />}
            {badge.label}
          </span>
        )}

        {overallStatus === 'saved' && (
          <span className={styles.deliveredNote}>
            {rowCount} row{rowCount === 1 ? '' : 's'} eligible — downstream export not enabled
          </span>
        )}

        {typeof dryRun === 'boolean' && overallStatus !== 'idle' && overallStatus !== 'pending' && (
          <span className={styles.deliveredNote}>
            {dryRun ? 'mode: dry-run (no target mutation)' : 'mode: real push'}
          </span>
        )}

        {targetEnv && overallStatus !== 'dry_run' && (
          <span className={styles.deliveredNote}>target: {targetEnv}</span>
        )}
      </div>

      {(manualSummary ||
        typeof eligibleCount === 'number' ||
        typeof excludedCount === 'number' ||
        typeof exportedCount === 'number' ||
        preflightNote) && (
        <div className={styles.summaryBlock} aria-label="Export row summary">
          {manualSummary && (
            <p className={styles.summaryLine}>Manual rows on backend: {manualSummary}</p>
          )}
          {typeof eligibleCount === 'number' && (
            <p className={styles.summaryLine}>
              Eligible for export: {eligibleCount}
              {typeof exportedCount === 'number' ? ` · already exported: ${exportedCount}` : ''}
              {typeof excludedCount === 'number' ? ` · historical/excluded: ${excludedCount}` : ''}
              {skipped.length > 0
                ? ` · skipped: ${skipped
                    .map((p) => `${PROGRAM_LABEL[p.program] ?? p.program}`)
                    .join(', ')}`
                : ''}
            </p>
          )}
          {preflightNote && <p className={styles.summaryNote}>{preflightNote}</p>}
        </div>
      )}

      {programStatuses.length > 0 && (
        <ul className={styles.programList} aria-label="Per-program export result">
          {programStatuses.map((p) => (
            <li key={p.program} className={`${styles.programItem} ${programItemClass(p.status, p.verification)}`}>
              <strong>{PROGRAM_LABEL[p.program] ?? p.program}</strong>:{' '}
              {programStatusText(p.status, p.reason, p.verification)}
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}
