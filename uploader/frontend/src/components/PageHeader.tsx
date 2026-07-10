import styles from './PageHeader.module.css'

interface Props {
  env: string
}

export function PageHeader({ env }: Props) {
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
    </header>
  )
}
