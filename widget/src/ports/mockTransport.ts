/** Ag kullanmayan ChatTransport — demo sayfasi ve testler icin.
 *
 * httpTransport ile AYNI sozlesmeyi karsilar; bilesenler ikisini
 * ayirt edemez. AŞAMA 5 testleri bunu mock'layarak tum UI durumlarini
 * uretebilir.
 */
import { mockArticles, mockMessages } from "../mock/fixtures";
import type { Article, Message } from "../types";
import type { ChatTransport, ConversationSnapshot } from "./types";

export interface MockTransportOptions {
  /** Baslangic mesajlari. */
  messages?: Message[];
  /** Her cagriya eklenen yapay gecikme (ms) — yukleniyor durumunu görmek icin. */
  latencyMs?: number;
  /** true ise her cagri hata firlatir (hata durumu testi). */
  failing?: boolean;
  startWaiting?: boolean;
  startNeedsContactForm?: boolean;
}

export function createMockTransport(options: MockTransportOptions = {}): ChatTransport {
  const latency = options.latencyMs ?? 0;
  let messages: Message[] = [...(options.messages ?? mockMessages)];
  let isWaiting = options.startWaiting ?? false;
  let needsContactForm = options.startNeedsContactForm ?? false;
  let nextId = messages.length + 1;

  const listeners = new Set<(s: ConversationSnapshot) => void>();

  const wait = () => (latency ? new Promise((r) => setTimeout(r, latency)) : Promise.resolve());

  function snapshot(): ConversationSnapshot {
    return {
      sessionId: 1,
      messages: [...messages],
      status: isWaiting ? "waiting_human" : "bot",
      isWaiting,
      needsContactForm,
    };
  }

  function emit() {
    const current = snapshot();
    listeners.forEach((fn) => fn(current));
  }

  async function guard<T>(produce: () => T): Promise<T> {
    await wait();
    if (options.failing) throw new Error("mock_transport_failure");
    return produce();
  }

  return {
    ensureSession: () => guard(() => 1),

    getConversation: () => guard(snapshot),

    sendMessage: (text) =>
      guard(() => {
        messages.push({
          id: `mock-${nextId++}`,
          author: "user",
          text,
          sentAt: new Date().toISOString(),
        });
        // Devir istegi gibi gorunuyorsa iletisim formunu tetikle —
        // gercek akisin (escalation -> contact form) taklidi.
        if (/temsilci|insan|yetkili/i.test(text)) {
          messages.push({
            id: `mock-${nextId++}`,
            author: "bot",
            authorName: "Netmera Asistan",
            text: "Sizi ilgili ekibimize aktarıyorum.",
            sentAt: new Date().toISOString(),
          });
          needsContactForm = true;
          isWaiting = true;
        } else {
          messages.push({
            id: `mock-${nextId++}`,
            author: "bot",
            authorName: "Netmera Asistan",
            text: "Bu bir mock cevaptır; gerçek RAG yanıtı AŞAMA 4'te bağlanacak.",
            sentAt: new Date().toISOString(),
          });
        }
        emit();
        return snapshot();
      }),

    submitContact: () =>
      guard(() => {
        needsContactForm = false;
        emit();
        return snapshot();
      }),

    resumeBot: () =>
      guard(() => {
        needsContactForm = false;
        isWaiting = false;
        emit();
        return snapshot();
      }),

    searchArticles: (query) =>
      guard<Article[]>(() => {
        const q = query.trim().toLowerCase();
        if (!q) return [...mockArticles];
        return mockArticles.filter(
          (a) => a.title.toLowerCase().includes(q) || a.excerpt.toLowerCase().includes(q),
        );
      }),

    getArticleByUrl: (url) =>
      guard<Article | null>(() => {
        const target = url.trim().toLowerCase();
        if (!target) return null;
        return (
          mockArticles.find(
            (a) =>
              a.url.toLowerCase() === target ||
              a.url.toLowerCase() === target.replace(/\.md$/, "") ||
              `${a.url.toLowerCase()}.md` === target,
          ) ?? null
        );
      }),

    subscribe(onChange) {
      listeners.add(onChange);
      return () => listeners.delete(onChange);
    },
  };
}
