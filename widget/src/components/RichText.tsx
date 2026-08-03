import { splitInlineMarkdown } from "../markdown";
import styles from "./RichText.module.css";

/** Bot yanitlarindaki satir-ici markdown isaretlerini isaretlemeye cevirir.
 *
 * Isaretlerin nasil ayristirildigi ve kapsamin neden dar tutuldugu icin
 * bkz. `src/markdown.ts`.
 *
 * HTML URETMIYORUZ. `dangerouslySetInnerHTML` yok — cikti React dugumu, yani
 * gomuldugumuz sitede model ciktisi hicbir kosulda isaretlemeye donusemez.
 */
export interface RichTextProps {
  text: string;
}

export function RichText({ text }: RichTextProps) {
  return (
    <>
      {splitInlineMarkdown(text).map((part, index) => {
        if (part.kind === "bold") return <strong key={index}>{part.value}</strong>;
        if (part.kind === "code") {
          return (
            <code key={index} className={styles.code}>
              {part.value}
            </code>
          );
        }
        return part.value;
      })}
    </>
  );
}
