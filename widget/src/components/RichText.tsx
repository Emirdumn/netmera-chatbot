import type { ReactNode } from "react";
import styles from "./RichText.module.css";

/** Bot yanitlarindaki satir-ici markdown isaretlerini isler.
 *
 * NEDEN: LLM cevaplari markdown uretiyor ve Streamlit paneli bunu
 * `st.markdown` ile isliyor. Widget ise ham metin basiyordu, bu yuzden
 * ziyaretciye `**APNS .p8 Sertifikasi**` seklinde yildizlar gorunuyordu.
 *
 * KAPSAM BILEREK DAR: yalnizca `**kalin**` ve `` `kod` ``. Baslik, liste ve
 * bag desteklenmez — liste isaretlerini LLM zaten satir basina yaziyor ve
 * `white-space: pre-wrap` bunlari okunur birakiyor; kaynak baglantilari da
 * baloncugun altinda ayrica listeleniyor.
 *
 * HTML URETMIYORUZ. `dangerouslySetInnerHTML` yok — cikti React dugumu, yani
 * gomuldugumuz sitede model ciktisi hicbir kosulda isaretlemeye donusemez.
 */
const TOKEN = /(\*\*[^*\n]+\*\*|`[^`\n]+`)/g;

export function renderRichText(text: string): ReactNode[] {
  return text
    .split(TOKEN)
    .filter((part) => part !== "")
    .map((part, index) => {
      if (part.length > 4 && part.startsWith("**") && part.endsWith("**")) {
        return <strong key={index}>{part.slice(2, -2)}</strong>;
      }
      if (part.length > 2 && part.startsWith("`") && part.endsWith("`")) {
        return (
          <code key={index} className={styles.code}>
            {part.slice(1, -1)}
          </code>
        );
      }
      return part;
    });
}

export interface RichTextProps {
  text: string;
}

export function RichText({ text }: RichTextProps) {
  return <>{renderRichText(text)}</>;
}
