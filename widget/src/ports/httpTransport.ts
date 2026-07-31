/** widget_api'ye konusan gercek ChatTransport implementasyonu. */
import type { Article } from "../types";
import {
  type ChatTransport,
  type ConversationSnapshot,
  type RawConversation,
  type RawMessage,
  type Telemetry,
  type WidgetConfig,
  noopTelemetry,
} from "./types";

const TOKEN_KEY = "netmera.widget.sessionToken";
const DEFAULT_POLL_MS = 2000;

function toMessage(raw: RawMessage) {
  return {
    id: raw.id,
    author: raw.author,
    authorName: raw.author_name ?? undefined,
    text: raw.text,
    sentAt: raw.sent_at,
    sources: raw.sources ?? [],
  };
}

function toSnapshot(raw: RawConversation): ConversationSnapshot {
  return {
    sessionId: raw.session_id,
    messages: raw.messages.map(toMessage),
    status: raw.status,
    isWaiting: raw.is_waiting,
    needsContactForm: raw.needs_contact_form,
  };
}

export function createHttpTransport(
  config: WidgetConfig,
  telemetry: Telemetry = noopTelemetry,
): ChatTransport {
  const base = config.apiBaseUrl.replace(/\/$/, "");
  let token: string | null = readStoredToken();

  function readStoredToken(): string | null {
    try {
      return window.localStorage.getItem(TOKEN_KEY);
    } catch {
      // Gizli sekme / storage kapali: token bellekte tutulur, oturum
      // sekme kapaninca kaybolur. Widget yine calisir.
      return null;
    }
  }

  function storeToken(value: string) {
    token = value;
    try {
      window.localStorage.setItem(TOKEN_KEY, value);
    } catch {
      /* storage yoksa sessizce gec */
    }
  }

  async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
      ...(init.headers as Record<string, string> | undefined),
    };
    // Token ASLA prop olarak bilesenlere gecmez; yalnizca burada,
    // Authorization basliginda kullanilir.
    if (token) headers.Authorization = `Bearer ${token}`;

    const response = await fetch(`${base}${path}`, { ...init, headers });

    if (response.status === 401) {
      // Token gecersiz/eskimis — bir kez yeni oturum acip tekrar dene.
      token = null;
      try {
        window.localStorage.removeItem(TOKEN_KEY);
      } catch {
        /* yok say */
      }
      await ensureSession();
      const retryHeaders = { ...headers, Authorization: `Bearer ${token}` };
      const retry = await fetch(`${base}${path}`, { ...init, headers: retryHeaders });
      if (!retry.ok) throw await toError(retry);
      return (await retry.json()) as T;
    }

    if (!response.ok) throw await toError(response);
    return (await response.json()) as T;
  }

  async function toError(response: Response): Promise<Error> {
    telemetry.track("transport_error", { status: response.status });
    if (response.status === 429) {
      return new Error("rate_limited");
    }
    return new Error(`request_failed_${response.status}`);
  }

  async function ensureSession(): Promise<number> {
    if (token) {
      const [rawId] = token.split(".");
      const parsed = Number(rawId);
      if (Number.isFinite(parsed)) return parsed;
    }
    const created = await request<{ session_id: number; token: string }>("/session", {
      method: "POST",
    });
    storeToken(created.token);
    return created.session_id;
  }

  async function getConversation(): Promise<ConversationSnapshot> {
    await ensureSession();
    return toSnapshot(await request<RawConversation>("/conversation"));
  }

  return {
    ensureSession,
    getConversation,

    async sendMessage(text) {
      await ensureSession();
      telemetry.track("message_sent");
      return toSnapshot(
        await request<RawConversation>("/messages", {
          method: "POST",
          body: JSON.stringify({ text }),
        }),
      );
    },

    async submitContact(name, email) {
      await ensureSession();
      telemetry.track("contact_submitted");
      return toSnapshot(
        await request<RawConversation>("/contact", {
          method: "POST",
          body: JSON.stringify({ name, email }),
        }),
      );
    },

    async resumeBot() {
      await ensureSession();
      telemetry.track("resumed_bot");
      return toSnapshot(
        await request<RawConversation>("/resume-bot", { method: "POST" }),
      );
    },

    async searchArticles(query): Promise<Article[]> {
      if (!query.trim()) return [];
      await ensureSession();
      const raw = await request<
        { id: string; title: string; excerpt: string; url: string; body: string[] }[]
      >(`/articles?q=${encodeURIComponent(query)}`);
      return raw;
    },

    subscribe(onChange) {
      // Gercek zamanli altyapi yok -> polling. SSE/WebSocket eklenirse
      // YALNIZCA burasi degisir, cagiran bilesenler ayni kalir.
      const interval = config.pollIntervalMs ?? DEFAULT_POLL_MS;
      let stopped = false;
      let timer: ReturnType<typeof setTimeout>;

      const tick = async () => {
        if (stopped) return;
        try {
          onChange(await getConversation());
        } catch {
          // Gecici ag hatasinda sessizce bir sonraki tur denenir;
          // kalici hatayi cagiran taraf kendi istegi uzerinden gorur.
        }
        if (!stopped) timer = setTimeout(tick, interval);
      };

      timer = setTimeout(tick, interval);
      return () => {
        stopped = true;
        clearTimeout(timer);
      };
    },
  };
}
