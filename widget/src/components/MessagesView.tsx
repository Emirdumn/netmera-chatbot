import { ErrorState } from "./ErrorState";
import { SkeletonStates } from "./SkeletonStates";
import { strings } from "../strings";
import type { Conversation, LoadState } from "../types";
import styles from "./MessagesView.module.css";

export interface MessagesViewProps {
  conversations: Conversation[];
  state?: LoadState;
  onOpenConversation: (conversationId: string) => void;
  onStartConversation: () => void;
  onRetry?: () => void;
}

function formatRelative(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "";
  const diffMin = Math.round((Date.now() - date.getTime()) / 60000);
  if (diffMin < 1) return "şimdi";
  if (diffMin < 60) return `${diffMin} dk`;
  const diffHour = Math.round(diffMin / 60);
  if (diffHour < 24) return `${diffHour} sa`;
  return new Intl.DateTimeFormat("tr-TR", { day: "2-digit", month: "2-digit" }).format(date);
}

export function MessagesView({
  conversations,
  state = "idle",
  onOpenConversation,
  onStartConversation,
  onRetry,
}: MessagesViewProps) {
  const common = {
    role: "tabpanel" as const,
    id: "nm-panel-messages",
    "aria-labelledby": "nm-tab-messages",
  };

  if (state === "loading") {
    return (
      <div className={styles.view} {...common}>
        <SkeletonStates variant="list" rows={4} />
      </div>
    );
  }

  if (state === "error") {
    return (
      <div className={styles.view} {...common}>
        <ErrorState onRetry={onRetry} />
      </div>
    );
  }

  if (conversations.length === 0) {
    return (
      <div className={styles.view} {...common}>
        <div className={styles.empty}>
          <p className={styles.emptyText}>{strings.messages.empty}</p>
          <button type="button" className={styles.emptyAction} onClick={onStartConversation}>
            {strings.messages.emptyAction}
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className={styles.view} {...common}>
      <ul className={styles.list}>
        {conversations.map((conversation) => (
          <li key={conversation.id}>
            <button
              type="button"
              className={styles.item}
              onClick={() => onOpenConversation(conversation.id)}
            >
              <span className={styles.avatar} aria-hidden="true">
                N
              </span>

              <span className={styles.body}>
                <span className={styles.topRow}>
                  <span className={styles.name}>{strings.messages.bot}</span>
                  <span className={styles.time}>
                    {formatRelative(conversation.lastMessageAt)}
                  </span>
                </span>
                <p className={styles.preview}>{conversation.preview}</p>
                {conversation.waitingForHuman && (
                  <span className={styles.waitingPill}>
                    {strings.conversation.waitingForHuman}
                  </span>
                )}
              </span>

              {conversation.unreadCount > 0 && (
                <span
                  className={styles.badge}
                  aria-label={`${conversation.unreadCount} ${strings.launcher.unreadSuffix}`}
                >
                  {conversation.unreadCount}
                </span>
              )}
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
