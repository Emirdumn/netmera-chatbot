import type { KeyboardEvent } from "react";
import { strings } from "../strings";
import styles from "./Composer.module.css";

export interface ComposerProps {
  value: string;
  onChange: (value: string) => void;
  onSend: () => void;
  /**
   * Gonderim surerken true olur. YALNIZCA gonder butonunu ve e-posta
   * alanini kilitler; yazma alanini KILITLEMEZ.
   *
   * Neden: `disabled` olan bir eleman odagi kaybeder. Textarea'yi da
   * kilitleseydik kullanici her mesajdan sonra tekrar tiklamak zorunda
   * kalirdi — sohbet arayuzunde kabul edilemez. Cift gonderim zaten
   * butonun kilitlenmesi ve useWidget.send() icindeki isSending kontrolu
   * ile engelleniyor.
   */
  disabled?: boolean;
  /** true ise e-posta alani gorunur (spec: yalnizca anonim kullanicida). */
  isAnonymous?: boolean;
  email?: string;
  onEmailChange?: (value: string) => void;
  /** Gonderim denendi ve e-posta gecersizdi. */
  emailError?: boolean;
}

const MAX_ROWS = 5;

export function Composer({
  value,
  onChange,
  onSend,
  disabled = false,
  isAnonymous = false,
  email = "",
  onEmailChange,
  emailError = false,
}: ComposerProps) {
  // Satir sayisi prop'tan turetiliyor — DOM olcumu yok, bilesen saf kaliyor.
  const rows = Math.min(MAX_ROWS, value.split("\n").length);
  const canSend = value.trim().length > 0 && !disabled;

  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    // Enter gonderir, Shift+Enter yeni satir acar.
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      if (canSend) onSend();
    }
  }

  return (
    <div className={styles.composer}>
      {isAnonymous && (
        <div className={styles.emailBlock}>
          <label className={styles.emailHint} htmlFor="nm-composer-email">
            {strings.composer.emailHint}
          </label>
          <input
            id="nm-composer-email"
            type="email"
            className={`${styles.field} ${emailError ? styles.fieldInvalid : ""}`}
            placeholder={strings.composer.emailPlaceholder}
            aria-label={strings.composer.emailLabel}
            aria-invalid={emailError}
            aria-describedby={emailError ? "nm-composer-email-error" : undefined}
            value={email}
            onChange={(e) => onEmailChange?.(e.target.value)}
            disabled={disabled}
          />
          {emailError && (
            <span className={styles.error} id="nm-composer-email-error" role="alert">
              {strings.composer.emailInvalid}
            </span>
          )}
        </div>
      )}

      <div className={styles.inputRow}>
        <textarea
          className={styles.textarea}
          rows={rows}
          value={value}
          placeholder={strings.composer.placeholder}
          aria-label={strings.composer.placeholder}
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={handleKeyDown}
        />
        <button
          type="button"
          className={styles.send}
          onClick={onSend}
          disabled={!canSend}
          aria-label={strings.composer.send}
        >
          <SendIcon />
        </button>
      </div>
    </div>
  );
}

function SendIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path
        d="M4.5 11.7 19 5l-6.7 14.5-1.9-6-5.9-1.8Z"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinejoin="round"
      />
    </svg>
  );
}
