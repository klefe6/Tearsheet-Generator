import type { ApiTradingDateStatus, ApiExportStatus } from '../api/client'
import { ExportModeBanner } from './ExportModeBanner'
import { formatLongDate } from '../lib/format'
import styles from './PageHeader.module.css'

interface Props {
  env: string
  tradingDates: ApiTradingDateStatus | null
  exportStatus: ApiExportStatus | null
  exportModeBanner: string | null
}

export function PageHeader({ env, tradingDates, exportStatus, exportModeBanner }: Props) {
  const isProd = env.toLowerCase() === 'production'

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

      <ExportModeBanner exportStatus={exportStatus} bannerMessage={exportModeBanner} />

      <div className={styles.dateStatus} aria-label="Market calendar dates">
        {tradingDates?.last_trading_date ? (
          <>
            <p className={styles.dateLine}>
              <span className={styles.dateLabel}>Today:</span>{' '}
              <time dateTime={tradingDates.today}>{formatLongDate(tradingDates.today)}</time>
            </p>
            <p className={styles.dateLine}>
              <span className={styles.dateLabel}>Last trading date:</span>{' '}
              <time dateTime={tradingDates.last_trading_date}>
                {formatLongDate(tradingDates.last_trading_date)}
              </time>
            </p>
          </>
        ) : tradingDates?.market_status === 'unavailable' ? (
          <p className={styles.dateError} role="alert">
            Trading calendar unavailable — last trading date could not be computed.
          </p>
        ) : (
          <p className={styles.dateMuted}>Loading market dates…</p>
        )}
      </div>
    </header>
  )
}
