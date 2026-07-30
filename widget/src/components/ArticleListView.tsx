import { strings } from "../strings";
import type { Article } from "../types";
import styles from "./ArticleListView.module.css";

export interface ArticleListViewProps {
  articles: Article[];
  onOpenArticle: (articleId: string) => void;
  emptyText?: string;
}

export function ArticleListView({
  articles,
  onOpenArticle,
  emptyText = strings.help.empty,
}: ArticleListViewProps) {
  if (articles.length === 0) {
    return <p className={styles.empty}>{emptyText}</p>;
  }

  return (
    <ul className={styles.list}>
      {articles.map((article) => (
        <li key={article.id}>
          <button
            type="button"
            className={styles.item}
            onClick={() => onOpenArticle(article.id)}
          >
            <span className={styles.text}>
              <span className={styles.title}>{article.title}</span>
              <p className={styles.excerpt}>{article.excerpt}</p>
            </span>
            <span className={styles.chevron} aria-hidden="true">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
                <path
                  d="m9 5 7 7-7 7"
                  stroke="currentColor"
                  strokeWidth="1.8"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </svg>
            </span>
          </button>
        </li>
      ))}
    </ul>
  );
}
