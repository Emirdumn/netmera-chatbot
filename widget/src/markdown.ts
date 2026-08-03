/** Satir-ici markdown isaretlerinin TEK bilgi kaynagi.
 *
 * NEDEN VAR: LLM cevaplari markdown uretiyor (Streamlit paneli bunu
 * `st.markdown` ile isliyor). Widget ham metin bastigi icin ziyaretciye
 * `**APNS .p8 Sertifikasi**` seklinde yildizlar gorunuyordu.
 *
 * KAPSAM BILEREK DAR: yalnizca `**kalin**` ve `` `kod` ``. Baslik/liste/bag
 * desteklenmez — liste isaretlerini LLM zaten satir basina yaziyor ve
 * baloncuktaki `white-space: pre-wrap` bunlari okunur birakiyor; kaynak
 * baglantilari da baloncugun altinda ayrica listeleniyor.
 *
 * Burasi saf metin isleme yapar; isaretleme uretimi RichText.tsx'te.
 */
export const INLINE_TOKEN = /(\*\*[^*\n]+\*\*|`[^`\n]+`)/g;

export type InlineKind = "bold" | "code" | "text";

export interface InlinePart {
  kind: InlineKind;
  /** Isaretler cikarilmis hali. */
  value: string;
}

/** Metni isaretli/isaretsiz parcalara ayirir. */
export function splitInlineMarkdown(text: string): InlinePart[] {
  return text
    .split(INLINE_TOKEN)
    .filter((part) => part !== "")
    .map((part) => {
      if (part.length > 4 && part.startsWith("**") && part.endsWith("**")) {
        return { kind: "bold" as const, value: part.slice(2, -2) };
      }
      if (part.length > 2 && part.startsWith("`") && part.endsWith("`")) {
        return { kind: "code" as const, value: part.slice(1, -1) };
      }
      return { kind: "text" as const, value: part };
    });
}

/** Onizleme satirlari icin: isaretleri islemeden SILER.
 *
 * Tek satira kirpilan bir ozette kalin metnin anlami yok; onemli olan
 * ziyaretcinin `**` gormemesi. Bu yuzden ayri bir fonksiyon. */
export function stripInlineMarkdown(text: string): string {
  return splitInlineMarkdown(text)
    .map((part) => part.value)
    .join("");
}
