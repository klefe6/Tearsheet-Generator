import type { ApiHealthResponse } from '../api/client'
import styles from './PageHeader.module.css'

interface Props {
  env: string
  health: ApiHealthResponse | null
}

export function PageHeader({ env, health }: Props) {
  const isProd = env.toLowerCase() === 'production'
  const liveExport =
    health?.export_downstream_enabled === true && health.export_dry_run === false
  const dryRunExport =
    health?.export_downstream_enabled === true && health.export_dry_run === true

  return (
    <header className={styles.header}>
      <div className={styles.titleRow}>
        <h1 className={styles.title}>Glenn Daily Uploader</h1>
        <span
          className={`${styles.envBadge} ${isProd ? styles.prod : styles.sandbox}`}
          title="Current build environment"
        >
          {env}
        </span>
      </div>
      <p className={styles.subtitle}>
        Enter daily NLVs, cash transfers, and fees for each product.
      </p>

      {liveExport && (
        <p className={styles.liveExportBanner} role="status">
          Live export enabled — Export All pushes to TKP/TCP/AGM. Y&Q is skipped.
        </p>
      )}

      {dryRunExport && (
        <p className={styles.dryRunBanner} role="status">
          Downstream dry-run — Export All computes targets but writes nothing (
          {health?.export_target_env ?? 'sandbox'}).
        </p>
      )}
    </header>
  )
}
