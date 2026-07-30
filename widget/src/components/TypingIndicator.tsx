import { strings } from "../strings";
import styles from "./TypingIndicator.module.css";

export interface TypingIndicatorProps {
  /** Kim yaziyor — ekran okuyucuya bildirilir. */
  authorName?: string;
}

export function TypingIndicator({ authorName = strings.messages.bot }: TypingIndicatorProps) {
  return (
    <div className={styles.row}>
      <span className={styles.avatar} aria-hidden="true">
        {authorName.slice(0, 1)}
      </span>
      <div className={styles.bubble} role="status" aria-label={`${authorName} ${strings.conversation.typing}`}>
        <span className={styles.dot} aria-hidden="true" />
        <span className={styles.dot} aria-hidden="true" />
        <span className={styles.dot} aria-hidden="true" />
      </div>
    </div>
  );
}
