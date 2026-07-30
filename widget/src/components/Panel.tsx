import type { ReactNode } from "react";
import { strings } from "../strings";
import styles from "./Panel.module.css";

export interface PanelProps {
  isOpen: boolean;
  title: string;
  /** Verilirse baslikta geri oku cikar (ör. makale detayi, sohbet ici). */
  onBack?: () => void;
  onClose: () => void;
  children: ReactNode;
  /** TabBar gibi alt sabit alan. */
  footer?: ReactNode;
}

/** Widget kabugu: baslik + govde + (opsiyonel) alt bar.
 *  Saf bilesen — acilma/kapanma kararini vermez, sadece yansitir. */
export function Panel({ isOpen, title, onBack, onClose, children, footer }: PanelProps) {
  return (
    <section
      className={`${styles.panel} ${isOpen ? styles.open : styles.closed}`}
      role="region"
      aria-label={strings.panel.ariaLabel}
      aria-hidden={!isOpen}
      // Kapaliyken icerik klavye sirasindan tamamen cikmali.
      inert={!isOpen}
    >
      <header className={styles.header}>
        {onBack && (
          <button
            type="button"
            className={styles.iconButton}
            onClick={onBack}
            aria-label={strings.panel.back}
          >
            <BackIcon />
          </button>
        )}

        <h2 className={styles.headerTitle}>{title}</h2>

        <button
          type="button"
          className={styles.iconButton}
          onClick={onClose}
          aria-label={strings.panel.close}
        >
          <CloseIcon />
        </button>
      </header>

      <div className={styles.body}>{children}</div>

      {footer}
    </section>
  );
}

function BackIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path
        d="M15 5 8 12l7 7"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function CloseIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path d="m6 6 12 12M18 6 6 18" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
    </svg>
  );
}
