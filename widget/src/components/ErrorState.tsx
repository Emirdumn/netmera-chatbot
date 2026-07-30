import { strings } from "../strings";
import styles from "./ErrorState.module.css";

export interface ErrorStateProps {
  title?: string;
  body?: string;
  onRetry?: () => void;
}

export function ErrorState({
  title = strings.error.title,
  body = strings.error.body,
  onRetry,
}: ErrorStateProps) {
  return (
    <div className={styles.wrap} role="alert">
      <span className={styles.icon} aria-hidden="true">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
          <path
            d="M12 8v5"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
          />
          <circle cx="12" cy="16.5" r="1.1" fill="currentColor" />
          <circle cx="12" cy="12" r="8.5" stroke="currentColor" strokeWidth="1.8" />
        </svg>
      </span>
      <h3 className={styles.title}>{title}</h3>
      <p className={styles.body}>{body}</p>
      {onRetry && (
        <button type="button" className={styles.retry} onClick={onRetry}>
          {strings.error.retry}
        </button>
      )}
    </div>
  );
}
