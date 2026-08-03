import { strings } from "../strings";
import type { Message, Source } from "../types";
import styles from "./MessageBubble.module.css";

export interface MessageBubbleProps {
  message: Message;
  /** Kaynaga tiklaninca panel icinde makale acilir (RAG seffafligi). */
  onOpenSource?: (source: Source) => void;
}

function formatTime(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "";
  return new Intl.DateTimeFormat("tr-TR", {
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

function initials(name: string): string {
  const parts = name.trim().split(/\s+/).slice(0, 2);
  return parts.map((p) => p[0] ?? "").join("");
}

export function MessageBubble({ message, onOpenSource }: MessageBubbleProps) {
  const isOutgoing = message.author === "user";
  const displayName =
    message.authorName ??
    (message.author === "bot" ? strings.messages.bot : strings.messages.staffFallback);

  return (
    <div className={`${styles.row} ${isOutgoing ? styles.outgoing : styles.incoming}`}>
      {!isOutgoing && (
        <span className={styles.avatar} aria-hidden="true">
          {initials(displayName)}
        </span>
      )}

      <div className={styles.stack}>
        {!isOutgoing && <span className={styles.authorName}>{displayName}</span>}

        <div
          className={`${styles.bubble} ${
            isOutgoing ? styles.bubbleOutgoing : styles.bubbleIncoming
          }`}
        >
          {message.text}
        </div>

        {message.sources && message.sources.length > 0 && (
          <ul className={styles.sources}>
            <li className={styles.sourcesLabel}>{strings.conversation.sources}</li>
            {message.sources.map((source) => (
              <li key={source.url} className={styles.sourceItem}>
                {onOpenSource ? (
                  <button
                    type="button"
                    className={styles.sourceButton}
                    onClick={() => onOpenSource(source)}
                  >
                    <span className={styles.sourceTitle}>{source.title}</span>
                    {source.excerpt ? (
                      <span className={styles.sourceExcerpt}>{source.excerpt}</span>
                    ) : null}
                  </button>
                ) : (
                  <a
                    className={styles.sourceLink}
                    href={source.url}
                    target="_blank"
                    rel="noreferrer noopener"
                  >
                    {source.title}
                  </a>
                )}
              </li>
            ))}
          </ul>
        )}

        <span className={`${styles.time} ${isOutgoing ? styles.timeOutgoing : ""}`}>
          {formatTime(message.sentAt)}
        </span>
      </div>
    </div>
  );
}
