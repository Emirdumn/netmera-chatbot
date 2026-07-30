import { ArticleListView } from "./ArticleListView";
import { ErrorState } from "./ErrorState";
import { SkeletonStates } from "./SkeletonStates";
import { strings } from "../strings";
import type { Article, LoadState } from "../types";
import styles from "./HelpView.module.css";

export interface HelpViewProps {
  query: string;
  onQueryChange: (query: string) => void;
  articles: Article[];
  state?: LoadState;
  onOpenArticle: (articleId: string) => void;
  onRetry?: () => void;
}

export function HelpView({
  query,
  onQueryChange,
  articles,
  state = "idle",
  onOpenArticle,
  onRetry,
}: HelpViewProps) {
  return (
    <div className={styles.view} role="tabpanel" id="nm-panel-help" aria-labelledby="nm-tab-help">
      <div className={styles.searchWrap}>
        <div className={styles.field}>
          <span className={styles.searchIcon} aria-hidden="true">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
              <circle cx="11" cy="11" r="6.5" stroke="currentColor" strokeWidth="1.8" />
              <path d="m16 16 4 4" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
            </svg>
          </span>
          <input
            type="search"
            className={styles.searchField}
            value={query}
            placeholder={strings.help.searchPlaceholder}
            aria-label={strings.help.searchPlaceholder}
            onChange={(e) => onQueryChange(e.target.value)}
          />
        </div>
      </div>

      {state === "loading" && <SkeletonStates variant="list" rows={4} />}

      {state === "error" && <ErrorState onRetry={onRetry} />}

      {state === "idle" && (
        <>
          {query.trim().length === 0 && (
            <span className={styles.sectionLabel}>{strings.help.articlesTitle}</span>
          )}
          <ArticleListView articles={articles} onOpenArticle={onOpenArticle} />
        </>
      )}
    </div>
  );
}
