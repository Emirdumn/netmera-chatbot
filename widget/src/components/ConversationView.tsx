import type { ReactNode, RefObject } from "react";
import { ErrorState } from "./ErrorState";
import { MessageBubble } from "./MessageBubble";
import { SkeletonStates } from "./SkeletonStates";
import { TypingIndicator } from "./TypingIndicator";
import { strings } from "../strings";
import type { LoadState, Message } from "../types";
import styles from "./ConversationView.module.css";

export interface ConversationViewProps {
  messages: Message[];
  state?: LoadState;
  isTyping?: boolean;
  /** Musteri bir temsilciye aktarilmayi bekliyor. */
  waitingForHuman?: boolean;
  onContinueWithBot?: () => void;
  onRetry?: () => void;
  /** Composer disaridan verilir — bu bilesen girdi state'i tutmaz. */
  composer?: ReactNode;
  /**
   * Mesaj listesine baglanacak ref. Kaydirmayi BU BILESEN yapmaz; ref'i
   * veren state katmani (useWidget) yeni mesajda en alta kaydirir.
   * Boylece bilesen saf kalir, DOM olcumu/efekt icermez.
   */
  logRef?: RefObject<HTMLDivElement | null>;
}

export function ConversationView({
  messages,
  state = "idle",
  isTyping = false,
  waitingForHuman = false,
  onContinueWithBot,
  onRetry,
  composer,
  logRef,
}: ConversationViewProps) {
  if (state === "error") {
    return (
      <div className={styles.view}>
        <ErrorState onRetry={onRetry} />
      </div>
    );
  }

  return (
    <div className={styles.view}>
      {state === "loading" ? (
        <div className={styles.log}>
          <SkeletonStates variant="conversation" rows={4} />
        </div>
      ) : (
        <div
          className={styles.log}
          ref={logRef}
          role="log"
          aria-live="polite"
          aria-relevant="additions text"
        >
          {messages.map((message) => (
            <MessageBubble key={message.id} message={message} />
          ))}
          {isTyping && <TypingIndicator />}
        </div>
      )}

      {waitingForHuman && (
        <div className={styles.banner}>
          <span className={styles.bannerText}>{strings.conversation.waitingForHuman}</span>
          {onContinueWithBot && (
            <button type="button" className={styles.bannerAction} onClick={onContinueWithBot}>
              {strings.conversation.continueWithBot}
            </button>
          )}
        </div>
      )}

      {composer}
    </div>
  );
}
