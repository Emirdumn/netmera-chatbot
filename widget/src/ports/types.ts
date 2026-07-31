/** AŞAMA 3 — Port arabirimleri.
 *
 * KAYNAK NOTU: spec dosyasi (support-widget.spec.md) yalnizca tasarim
 * token'lari iceriyor, TypeScript tanimi YOK. Bu yuzden bu arabirimler
 * kararlastirildigi gibi mevcut backend'den turetildi:
 *
 *   app_services/chat_service.py   -> ChatTransport
 *   graph/nodes.py:contact_form    -> submitContact
 *   widget_api/schemas.py          -> Message / Conversation bicimleri
 *
 * Bilesenler bu arabirimlerin ARKASINI bilmez; httpTransport da
 * mockTransport da ayni sozlesmeyi karsilar.
 */
import type { Article, Conversation, Message } from "../types";

/** Sunucudan donen sohbet durumu. */
export interface ConversationSnapshot {
  sessionId: number;
  messages: Message[];
  status: string;
  /** Musteri bir insani bekliyor — bot devrede degil. */
  isWaiting: boolean;
  /** Ad/e-posta formu gosterilmeli. */
  needsContactForm: boolean;
}

/**
 * Sohbet verisine erisim. TEK ag sinirimiz burasi — bilesenlerin
 * icinde fetch/axios cagrisi olmaz (guardrail 4).
 */
export interface ChatTransport {
  /** Oturum yoksa acar, varsa mevcut token'i kullanir. */
  ensureSession(): Promise<number>;

  /** O anki tam durumu getirir. */
  getConversation(): Promise<ConversationSnapshot>;

  /** Mesaj gonderir; donen deger gonderim SONRASI durumdur. */
  sendMessage(text: string): Promise<ConversationSnapshot>;

  /** Devir icin ad/e-posta verir. */
  submitContact(name: string, email: string): Promise<ConversationSnapshot>;

  /** "Bot ile devam et" — bekleyen devri askiya alir, talep acik kalir. */
  resumeBot(): Promise<ConversationSnapshot>;

  /** Yardim sekmesi aramasi. Bot cevabi uretmez, dokuman doner. */
  searchArticles(query: string): Promise<Article[]>;

  /**
   * Durum degisikliklerine abone olur; abonelikten cikaran fonksiyon doner.
   *
   * Bugun POLLING uzerine kurulu (projede gercek zamanli altyapi yok —
   * mevcut Streamlit konvansiyonu da 2 sn polling). Ileride SSE/WebSocket
   * eklenirse YALNIZCA bu metodun ici degisir; bilesenler etkilenmez.
   */
  subscribe(onChange: (snapshot: ConversationSnapshot) => void): () => void;
}

/**
 * Kullanici kimligi.
 *
 * Widget'a gomulu kullanicilar BUGUN her zaman anonimdir; oturum acmis
 * kullanici akisi kapsam disi birakildi (bkz. docs/support-widget-plan.md).
 * Arabirim yine de o gunu destekleyecek sekilde tanimli.
 */
export interface ChatIdentity {
  isAnonymous: boolean;
  name?: string;
  email?: string;
  avatarUrl?: string;
}

/** Gomuldugu sitenin verebilecegi ayarlar. */
export interface WidgetConfig {
  /** widget_api tabani, ör. "https://.../api/widget". */
  apiBaseUrl: string;
  locale?: "tr" | "en";
  /** Polling araligi (ms). Varsayilan 2000 — Streamlit ile ayni. */
  pollIntervalMs?: number;
  /** Acilista panel acik gelsin mi. */
  defaultOpen?: boolean;
}

/** Olcum/izleme. Sirlar ve kullanici verisi ASLA gecirilmez. */
export interface Telemetry {
  track(event: TelemetryEvent, payload?: Record<string, string | number | boolean>): void;
}

export type TelemetryEvent =
  | "widget_opened"
  | "widget_closed"
  | "message_sent"
  | "contact_submitted"
  | "resumed_bot"
  | "article_opened"
  | "transport_error";

/** Hicbir sey yapmayan varsayilan — telemetri opsiyonel olsun diye. */
export const noopTelemetry: Telemetry = { track: () => {} };

/** Sunucu bicimini (snake_case) widget bicimine (camelCase) cevirmek icin. */
export interface RawMessage {
  id: string;
  author: Message["author"];
  author_name?: string | null;
  text: string;
  sent_at: string;
  sources?: { title: string; url: string }[];
}

export interface RawConversation {
  session_id: number;
  messages: RawMessage[];
  status: string;
  is_waiting: boolean;
  needs_contact_form: boolean;
}

export type { Article, Conversation, Message };
