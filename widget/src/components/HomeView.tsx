import { strings } from "../strings";
import type { Conversation } from "../types";
import styles from "./HomeView.module.css";

export interface HomeViewProps {
  greeting?: string;
  subtitle?: string;
  /** Varsa "son sohbetiniz" karti gosterilir. */
  recentConversation?: Conversation;
  /** Ekibin cevrimici olup olmadigi (spec: color.online). */
  isTeamOnline?: boolean;
  onStartConversation: () => void;
  onOpenConversation: (conversationId: string) => void;
  onOpenHelp: () => void;
}

export function HomeView({
  greeting = strings.home.greeting,
  subtitle = strings.home.subtitle,
  recentConversation,
  isTeamOnline = false,
  onStartConversation,
  onOpenConversation,
  onOpenHelp,
}: HomeViewProps) {
  return (
    <div className={styles.view} role="tabpanel" id="nm-panel-home" aria-labelledby="nm-tab-home">
      <h3 className={styles.greeting}>{greeting}</h3>
      <p className={styles.subtitle}>{subtitle}</p>

      {recentConversation && (
        <button
          type="button"
          className={styles.card}
          onClick={() => onOpenConversation(recentConversation.id)}
        >
          <span className={styles.cardLabel}>{strings.home.recentTitle}</span>
          <p className={styles.cardPreview}>{recentConversation.preview}</p>
          <span className={styles.cardFooter}>
            {isTeamOnline && <span className={styles.onlineDot} aria-hidden="true" />}
            <span className={styles.cardLabel}>{strings.home.continueConversation}</span>
            {recentConversation.unreadCount > 0 && (
              <span className={styles.badge}>{recentConversation.unreadCount}</span>
            )}
          </span>
        </button>
      )}

      <button type="button" className={styles.primary} onClick={onStartConversation}>
        {strings.home.startConversation}
      </button>

      <button type="button" className={styles.searchButton} onClick={onOpenHelp}>
        <SearchIcon />
        {strings.home.searchPlaceholder}
      </button>
    </div>
  );
}

function SearchIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <circle cx="11" cy="11" r="6.5" stroke="currentColor" strokeWidth="1.8" />
      <path d="m16 16 4 4" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
    </svg>
  );
}
