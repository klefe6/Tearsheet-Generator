import type { ApiExportStatus } from '../api/client'
import styles from './ExportModeBanner.module.css'

interface Props {
  exportStatus: ApiExportStatus | null
  bannerMessage: string | null
}

export function ExportModeBanner({ exportStatus, bannerMessage }: Props) {
  if (!exportStatus || !bannerMessage) return null

  const mode = exportStatus.export_mode
  const className =
    mode === 'live'
      ? styles.live
      : mode === 'dry_run'
        ? styles.dryRun
        : styles.disabled

  return (
    <div
      className={`${styles.banner} ${className}`}
      role="status"
      aria-live="polite"
      aria-label="Export mode"
    >
      <p className={styles.title}>
        Export mode: {mode === 'live' ? 'LIVE' : mode === 'dry_run' ? 'DRY RUN' : 'DISABLED'}
      </p>
      <p className={styles.message}>{bannerMessage}</p>
      <p className={styles.meta}>
        Target: {exportStatus.target_environment === 'production' ? 'Production' : exportStatus.target_environment}
        {' · '}
        Downstream writes: {exportStatus.real_writes_enabled ? 'Enabled' : 'Disabled'}
      </p>
    </div>
  )
}
