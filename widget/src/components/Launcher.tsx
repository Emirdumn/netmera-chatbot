import { strings } from "../strings";
import styles from "./Launcher.module.css";

export interface LauncherProps {
  isOpen: boolean;
  unreadCount?: number;
  onToggle: () => void;
}

/** Sag altta duran yuvarlak buton. Saf: sadece prop okur, callback cagirir. */
export function Launcher({ isOpen, unreadCount = 0, onToggle }: LauncherProps) {
  const label = isOpen ? strings.launcher.close : strings.launcher.open;
  const showBadge = !isOpen && unreadCount > 0;

  return (
    <button
      type="button"
      className={styles.launcher}
      onClick={onToggle}
      aria-label={
        showBadge
          ? `${label} — ${unreadCount} ${strings.launcher.unreadSuffix}`
          : label
      }
      aria-expanded={isOpen}
    >
      <span
        className={`${styles.iconLayer} ${isOpen ? styles.iconExit : styles.iconEnter}`}
        aria-hidden="true"
      >
        <ChatIcon />
      </span>
      <span
        className={`${styles.iconLayer} ${isOpen ? styles.iconEnter : styles.iconExit}`}
        aria-hidden="true"
      >
        <CloseIcon />
      </span>

      {showBadge && (
        <span className={styles.badge} aria-hidden="true">
          {unreadCount > 99 ? "99+" : unreadCount}
        </span>
      )}
    </button>
  );
}

function ChatIcon() {
  return (
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path
        d="M4 5.5A1.5 1.5 0 0 1 5.5 4h13A1.5 1.5 0 0 1 20 5.5v9a1.5 1.5 0 0 1-1.5 1.5H9l-4 3.5V16H5.5A1.5 1.5 0 0 1 4 14.5v-9Z"
        fill="currentColor"
      />
    </svg>
  );
}

function CloseIcon() {
  return (
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path
        d="m6 6 12 12M18 6 6 18"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
      />
    </svg>
  );
}
