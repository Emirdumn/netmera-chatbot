/** Sunum katmani view-model'leri.
 *
 * DIKKAT: Bunlar AŞAMA 3'teki `ChatTransport` / `ChatIdentity` /
 * `WidgetConfig` / `Telemetry` PORT arabirimleri DEGILDIR. Bunlar yalnizca
 * saf bilesenlerin prop olarak aldigi bicimlerdir. Portlar AŞAMA 3'te
 * mevcut backend mantigindan (storage/repository.py, graph/workflow.py)
 * turetilecek ve bu tiplere donusturulecek.
 */

export type TabId = "home" | "messages" | "help";

export type MessageAuthor = "user" | "bot" | "staff";

export interface Message {
  id: string;
  author: MessageAuthor;
  /** staff icin temsilci adi, bot icin agent etiketi; user icin bos. */
  authorName?: string;
  text: string;
  /** ISO 8601 */
  sentAt: string;
  /** Bot cevabinin dayandigi dokuman baglantilari. */
  sources?: Source[];
}

export interface Source {
  title: string;
  url: string;
  /** RAG parcasindan kisa ozet — kaynak neden secildigini gosterir. */
  excerpt?: string;
}

export interface Conversation {
  id: string;
  /** Listede gosterilecek son mesaj ozeti. */
  preview: string;
  lastMessageAt: string;
  unreadCount: number;
  /** true ise musteri bir insana aktarilmayi bekliyor. */
  waitingForHuman: boolean;
  messages: Message[];
}

export interface Article {
  id: string;
  title: string;
  excerpt: string;
  /** ArticleView icinde gosterilen tam metin (duz paragraflar). */
  body: string[];
  url: string;
  /** user_guide | dev_guide | website */
  source?: string;
}

/** Async veri tasiyan her gorunum bu uc durumdan birindedir. */
export type LoadState = "idle" | "loading" | "error";
