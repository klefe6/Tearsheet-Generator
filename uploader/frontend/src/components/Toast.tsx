import styles from './Toast.module.css'

interface Props {
  message: string | null
  onDismiss: () => void
}

export function Toast({ message, onDismiss }: Props) {
  if (!message) return null
  return (
    <div className={styles.toast} role="status" aria-live="polite">
      <span className={styles.icon} aria-hidden="true">
        ✓
      </span>
      <span className={styles.message}>{message}</span>
      <button
        type="button"
        className={styles.close}
        onClick={onDismiss}
        aria-label="Dismiss notification"
      >
        ×
      </button>
    </div>
  )
}
