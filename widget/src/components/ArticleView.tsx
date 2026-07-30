import { SkeletonStates } from "./SkeletonStates";
import { strings } from "../strings";
import type { Article, LoadState } from "../types";
import styles from "./ArticleView.module.css";

export interface ArticleViewProps {
  article?: Article;
  state?: LoadState;
}

export function ArticleView({ article, state = "idle" }: ArticleViewProps) {
  if (state === "loading" || !article) {
    return (
      <div className={styles.view}>
        <SkeletonStates variant="article" />
      </div>
    );
  }

  return (
    <article className={styles.view}>
      <h3 className={styles.title}>{article.title}</h3>
      {article.body.map((paragraph, index) => (
        <p key={index} className={styles.paragraph}>
          {paragraph}
        </p>
      ))}
      <a
        className={styles.sourceLink}
        href={article.url}
        target="_blank"
        rel="noreferrer noopener"
      >
        {strings.help.readMore}
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" aria-hidden="true">
          <path
            d="M14 5h5v5M19 5l-8 8M18 14v4a1 1 0 0 1-1 1H6a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h4"
            stroke="currentColor"
            strokeWidth="1.8"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      </a>
    </article>
  );
}
