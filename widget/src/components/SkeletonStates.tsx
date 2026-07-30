import { strings } from "../strings";
import styles from "./SkeletonStates.module.css";

export interface SkeletonStatesProps {
  /** Hangi gorunumun iskeleti cizilecek. */
  variant: "conversation" | "list" | "article";
  rows?: number;
}

export function SkeletonStates({ variant, rows = 3 }: SkeletonStatesProps) {
  return (
    <div className={styles.wrap} role="status" aria-label={strings.loading.label} aria-busy="true">
      {variant === "conversation" &&
        Array.from({ length: rows }).map((_, i) => (
          <span
            key={i}
            className={`${styles.bubble} ${i % 2 === 1 ? styles.bubbleOut : ""}`}
          />
        ))}

      {variant === "list" &&
        Array.from({ length: rows }).map((_, i) => <span key={i} className={styles.block} />)}

      {variant === "article" && (
        <>
          <span className={`${styles.line} ${styles.medium}`} />
          <span className={styles.line} />
          <span className={styles.line} />
          <span className={`${styles.line} ${styles.short}`} />
        </>
      )}
    </div>
  );
}
