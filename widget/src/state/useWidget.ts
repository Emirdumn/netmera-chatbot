/** AŞAMA 4 — Tek state sahibi.
 *
 * Bilesenler saf kalir; TUM state, transport cagrilari ve yan etkiler
 * burada toplanir. Bu hook disinda hicbir yerde fetch/localStorage/timer
 * yoktur.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  type ChatTransport,
  type ConversationSnapshot,
  type Telemetry,
  type WidgetConfig,
  noopTelemetry,
} from "../ports/types";
import { strings } from "../strings";
import type { Article, Conversation, LoadState, TabId } from "../types";

const OPEN_KEY = "netmera.widget.open";
const DRAFT_KEY = "netmera.widget.draft";
const HELP_DEBOUNCE_MS = 300;
const EMAIL_RE = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;

/** localStorage gizli sekmede/kapali oldugunda patlamamali. */
function readStorage(key: string): string | null {
  try {
    return window.localStorage.getItem(key);
  } catch {
    return null;
  }
}

function writeStorage(key: string, value: string): void {
  try {
    window.localStorage.setItem(key, value);
  } catch {
    /* storage yoksa sessizce gec — widget yine calisir */
  }
}

export interface UseWidgetOptions {
  transport: ChatTransport;
  config: WidgetConfig;
  telemetry?: Telemetry;
}

export function useWidget({ transport, config, telemetry = noopTelemetry }: UseWidgetOptions) {
  const [isOpen, setIsOpen] = useState<boolean>(
    () => readStorage(OPEN_KEY) === "1" || Boolean(config.defaultOpen),
  );
  const [tab, setTab] = useState<TabId>("home");
  const [draft, setDraft] = useState<string>(() => readStorage(DRAFT_KEY) ?? "");
  const [email, setEmail] = useState("");
  const [emailTouched, setEmailTouched] = useState(false);

  const [snapshot, setSnapshot] = useState<ConversationSnapshot | null>(null);
  const [conversationState, setConversationState] = useState<LoadState>("idle");
  const [isSending, setIsSending] = useState(false);
  const [inConversation, setInConversation] = useState(false);

  const [helpQuery, setHelpQuery] = useState("");
  const [articles, setArticles] = useState<Article[]>([]);
  const [helpState, setHelpState] = useState<LoadState>("idle");
  const [openArticle, setOpenArticle] = useState<Article | null>(null);

  /** Mesaj listesi elemani — auto-scroll icin. */
  const logRef = useRef<HTMLDivElement>(null);

  // --- Kalicilik -----------------------------------------------------------
  useEffect(() => {
    writeStorage(OPEN_KEY, isOpen ? "1" : "0");
  }, [isOpen]);

  useEffect(() => {
    writeStorage(DRAFT_KEY, draft);
  }, [draft]);

  // --- Ilk yukleme ---------------------------------------------------------
  const refresh = useCallback(async () => {
    try {
      setSnapshot(await transport.getConversation());
      setConversationState("idle");
    } catch {
      setConversationState("error");
    }
  }, [transport]);

  useEffect(() => {
    if (!isOpen || snapshot) return;
    setConversationState("loading");
    void refresh();
  }, [isOpen, snapshot, refresh]);

  // --- Canli guncelleme (polling; SSE'ye gecilirse transport degisir) ------
  useEffect(() => {
    if (!isOpen) return;
    const unsubscribe = transport.subscribe(setSnapshot);
    return unsubscribe;
  }, [isOpen, transport]);

  // --- Auto-scroll ---------------------------------------------------------
  // AŞAMA 2'de bilinerek yapilmamisti: saf bilesende DOM olcumu olmamali.
  // Dogru yer burasi — sohbet acildiginda ve yeni mesaj geldiginde log
  // en alta kaydirilir.
  const messageCount = snapshot?.messages.length ?? 0;
  useEffect(() => {
    const node = logRef.current;
    if (!node || !inConversation) return;
    node.scrollTop = node.scrollHeight;
  }, [messageCount, inConversation, isSending]);

  // --- Yardim aramasi (debounce'lu) ---------------------------------------
  useEffect(() => {
    if (tab !== "help") return;
    const query = helpQuery.trim();
    if (!query) {
      setArticles([]);
      setHelpState("idle");
      return;
    }
    setHelpState("loading");
    const timer = setTimeout(async () => {
      try {
        setArticles(await transport.searchArticles(query));
        setHelpState("idle");
      } catch {
        setHelpState("error");
      }
    }, HELP_DEBOUNCE_MS);
    return () => clearTimeout(timer);
  }, [helpQuery, tab, transport]);

  // --- Turetilmis gorunum modeli ------------------------------------------
  /** Backend'de gomulu widget basina TEK anonim oturum var; "Mesajlar"
   *  listesi de bu yuzden en fazla bir kayit gosterir. */
  const conversations: Conversation[] = useMemo(() => {
    if (!snapshot || snapshot.messages.length === 0) return [];
    const last = snapshot.messages[snapshot.messages.length - 1];
    return [
      {
        id: String(snapshot.sessionId),
        preview: last.text,
        lastMessageAt: last.sentAt,
        unreadCount: 0,
        waitingForHuman: snapshot.isWaiting,
        messages: snapshot.messages,
      },
    ];
  }, [snapshot]);

  const messages = snapshot?.messages ?? [];
  const isWaiting = snapshot?.isWaiting ?? false;
  const needsContactForm = snapshot?.needsContactForm ?? false;

  // --- Aksiyonlar ----------------------------------------------------------
  const toggle = useCallback(() => {
    setIsOpen((open) => {
      telemetry.track(open ? "widget_closed" : "widget_opened");
      return !open;
    });
  }, [telemetry]);

  const openConversation = useCallback(() => {
    setInConversation(true);
    setTab("messages");
  }, []);

  const send = useCallback(async () => {
    const text = draft.trim();
    if (!text || isSending) return;
    setIsSending(true);
    setDraft("");
    try {
      setSnapshot(await transport.sendMessage(text));
      setInConversation(true);
    } catch {
      // Gonderilemedi: taslagi geri koy ki kullanici yazdigini kaybetmesin.
      setDraft(text);
      setConversationState("error");
    } finally {
      setIsSending(false);
    }
  }, [draft, isSending, transport]);

  const submitContact = useCallback(async () => {
    const mail = email.trim();
    if (!EMAIL_RE.test(mail)) {
      setEmailTouched(true);
      return;
    }
    try {
      setSnapshot(await transport.submitContact(strings.composer.anonymousName, mail));
      setEmail("");
      setEmailTouched(false);
    } catch {
      setConversationState("error");
    }
  }, [email, transport]);

  const submitContactWithName = useCallback(
    async (name: string, mail: string) => {
      try {
        setSnapshot(await transport.submitContact(name, mail));
      } catch {
        setConversationState("error");
      }
    },
    [transport],
  );

  const resumeBot = useCallback(async () => {
    try {
      setSnapshot(await transport.resumeBot());
    } catch {
      setConversationState("error");
    }
  }, [transport]);

  const openArticleById = useCallback(
    (articleId: string) => {
      const found = articles.find((a) => a.id === articleId) ?? null;
      setOpenArticle(found);
      telemetry.track("article_opened");
    },
    [articles, telemetry],
  );

  return {
    // durum
    isOpen,
    tab,
    draft,
    email,
    emailTouched,
    messages,
    conversations,
    isWaiting,
    needsContactForm,
    conversationState,
    isSending,
    inConversation,
    helpQuery,
    articles,
    helpState,
    openArticle,
    logRef,
    // aksiyonlar
    toggle,
    close: () => setIsOpen(false),
    setTab,
    setDraft,
    setEmail: (value: string) => {
      setEmail(value);
      setEmailTouched(true);
    },
    openConversation,
    leaveConversation: () => setInConversation(false),
    send,
    submitContact,
    submitContactWithName,
    resumeBot,
    setHelpQuery,
    openArticleById,
    closeArticle: () => setOpenArticle(null),
    retry: refresh,
  };
}

export type WidgetController = ReturnType<typeof useWidget>;
