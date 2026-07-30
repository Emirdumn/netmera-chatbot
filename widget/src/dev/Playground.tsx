import { useState } from "react";
import { Composer } from "../components/Composer";
import { ConversationView } from "../components/ConversationView";
import { HelpView } from "../components/HelpView";
import { HomeView } from "../components/HomeView";
import { Launcher } from "../components/Launcher";
import { MessagesView } from "../components/MessagesView";
import { Panel } from "../components/Panel";
import { TabBar } from "../components/TabBar";
import { ArticleView } from "../components/ArticleView";
import { strings } from "../strings";
import type { LoadState, TabId } from "../types";
import { mockArticles, mockConversations, mockLongMessage, mockMessages } from "../mock/fixtures";
import styles from "./Playground.module.css";

/** AŞAMA 2 demo sayfasi.
 *
 * Butun state BURADA duruyor — bilesenler saf kaliyor. Hicbir ag cagrisi yok;
 * veri `src/mock/fixtures.ts` icinden geliyor. Gercek veri baglantisi
 * AŞAMA 3'te `ChatTransport` portu uzerinden yapilacak. */

type ScenarioId =
  | "home"
  | "home-unread"
  | "messages"
  | "messages-empty"
  | "messages-loading"
  | "messages-error"
  | "conversation"
  | "conversation-typing"
  | "conversation-long"
  | "conversation-waiting"
  | "conversation-loading"
  | "composer-multiline"
  | "composer-anonymous"
  | "help"
  | "help-empty"
  | "article"
  | "mobile";

interface Scenario {
  id: ScenarioId;
  label: string;
  group: string;
  note: string;
  /** Senaryo secilince widget'in acilacagi sekme. Boylece sol listedeki
   *  secim ile widget icerigi her zaman ayni seyi gosterir. */
  tab: TabId;
}

const SCENARIOS: Scenario[] = [
  { id: "home", label: "Varsayılan", group: "Ana sayfa", tab: "home", note: "Karşılama, son sohbet kartı ve yardım araması." },
  { id: "home-unread", label: "Okunmamış rozet", group: "Ana sayfa", tab: "home", note: "Launcher ve sekmede okunmamış sayacı görünür." },

  { id: "messages", label: "Dolu liste", group: "Mesajlar", tab: "messages", note: "İki sohbet; biri okunmamış ve temsilci bekliyor." },
  { id: "messages-empty", label: "Boş", group: "Mesajlar", tab: "messages", note: "Hiç sohbet yokken görünen boş durum." },
  { id: "messages-loading", label: "Yükleniyor", group: "Mesajlar", tab: "messages", note: "Liste iskeleti (skeleton)." },
  { id: "messages-error", label: "Hata", group: "Mesajlar", tab: "messages", note: "Bağlantı hatası ve tekrar dene." },

  { id: "conversation", label: "Normal", group: "Sohbet", tab: "messages", note: "Kullanıcı ve bot mesajları, kaynak bağlantılarıyla." },
  { id: "conversation-typing", label: "Yazıyor", group: "Sohbet", tab: "messages", note: "Üç noktalı yazıyor göstergesi (1200ms döngü)." },
  { id: "conversation-long", label: "Uzun mesaj", group: "Sohbet", tab: "messages", note: "Çok satırlı uzun cevap ve taşan URL davranışı." },
  { id: "conversation-waiting", label: "Temsilci bekliyor", group: "Sohbet", tab: "messages", note: "Aktarım bandı ve 'Bot ile devam et' butonu." },
  { id: "conversation-loading", label: "Yükleniyor", group: "Sohbet", tab: "messages", note: "Mesaj balonu iskeleti." },

  { id: "composer-multiline", label: "Çok satırlı", group: "Composer", tab: "messages", note: "Shift+Enter ile satır ekleyin; alan 5 satıra kadar büyür." },
  { id: "composer-anonymous", label: "Anonim + e-posta", group: "Composer", tab: "messages", note: "E-posta alanı yalnızca anonim kullanıcıda görünür; geçersiz değerde hata." },

  { id: "help", label: "Liste", group: "Yardım", tab: "help", note: "Popüler başlıklar ve arama alanı." },
  { id: "help-empty", label: "Sonuç yok", group: "Yardım", tab: "help", note: "Aramayla eşleşen başlık bulunamadı." },
  { id: "article", label: "Makale", group: "Yardım", tab: "help", note: "Başlık, paragraflar ve kaynağa giden bağlantı." },

  { id: "mobile", label: "Tam ekran", group: "Mobil", tab: "home", note: "Spec: 480px altında panel tam ekrana geçer. Tarayıcı penceresini 480px altına daraltarak görebilirsiniz." },
];

export function Playground() {
  const [scenario, setScenario] = useState<ScenarioId>("home");
  const [isOpen, setIsOpen] = useState(true);
  const [tab, setTab] = useState<TabId>("home");
  const [draft, setDraft] = useState("");
  const [email, setEmail] = useState("");
  const [emailTouched, setEmailTouched] = useState(false);
  const [helpQuery, setHelpQuery] = useState("");
  const [openArticleId, setOpenArticleId] = useState<string | null>(null);

  const active = SCENARIOS.find((s) => s.id === scenario)!;

  // --- Senaryodan turetilen gorunum ayarlari ---
  const unreadCount = scenario === "home-unread" ? 3 : 0;

  const messagesState: LoadState =
    scenario === "messages-loading" ? "loading" : scenario === "messages-error" ? "error" : "idle";

  const conversationState: LoadState = scenario === "conversation-loading" ? "loading" : "idle";

  const conversations = scenario === "messages-empty" ? [] : mockConversations;

  const conversationMessages =
    scenario === "conversation-long" ? [...mockMessages, mockLongMessage] : mockMessages;

  const helpArticles = scenario === "help-empty" ? [] : mockArticles;

  const isConversationScenario = active.group === "Sohbet" || active.group === "Composer";
  const isAnonymous = scenario === "composer-anonymous";
  const emailInvalid = emailTouched && !email.includes("@");

  const openArticle = mockArticles.find((a) => a.id === openArticleId);

  // Sekme dogrudan state'ten okunur; senaryo secildiginde onClick icinde
  // s.tab ile set edilir. (Onceki turetilmis mantik "Mesajlar" grubunda
  // sekmeyi degistirmiyordu — sol listede secim yapip widget'in Ana
  // sayfa'da kalmasina yol aciyordu.)
  const effectiveTab = tab;

  const showConversation = isConversationScenario;
  const showArticle = scenario === "article" || openArticleId !== null;

  const panelTitle = showConversation
    ? strings.messages.bot
    : showArticle
      ? strings.help.title
      : effectiveTab === "messages"
        ? strings.messages.title
        : effectiveTab === "help"
          ? strings.help.title
          : strings.panel.ariaLabel;

  const composer = (
    <Composer
      value={draft}
      onChange={setDraft}
      onSend={() => {
        if (isAnonymous && !email.includes("@")) {
          setEmailTouched(true);
          return;
        }
        setDraft("");
      }}
      isAnonymous={isAnonymous}
      email={email}
      onEmailChange={(value) => {
        setEmail(value);
        setEmailTouched(true);
      }}
      emailError={isAnonymous && emailInvalid}
    />
  );

  return (
    // `nm-root` burada da var: tokenlar o kapsamda tanimli oldugu icin
    // dev chrome'u da sabit renk yazmadan ayni tokenlari kullanabiliyor.
    <div className={`nm-root ${styles.page}`}>
      <aside className={styles.sidebar}>
        <div>
          <p className={styles.brand}>Destek Widget'ı — AŞAMA 2</p>
          <p className={styles.brandNote}>
            Saf sunum bileşenleri, mock veri. Ağ çağrısı yok, backend'e bağlı değil.
          </p>
        </div>

        {[...new Set(SCENARIOS.map((s) => s.group))].map((group) => (
          <div className={styles.group} key={group}>
            <span className={styles.groupLabel}>{group}</span>
            {SCENARIOS.filter((s) => s.group === group).map((s) => (
              <button
                key={s.id}
                type="button"
                className={`${styles.scenario} ${s.id === scenario ? styles.scenarioActive : ""}`}
                onClick={() => {
                  setScenario(s.id);
                  setIsOpen(true);
                  setOpenArticleId(s.id === "article" ? mockArticles[0].id : null);
                  setDraft(s.id === "composer-multiline" ? "Merhaba,\nSDK kurulumunda\nbir sorun yaşıyoruz." : "");
                  setEmail("");
                  setEmailTouched(false);
                  setHelpQuery(s.id === "help-empty" ? "bulunmayan bir konu" : "");
                  setTab(s.tab);
                }}
              >
                {s.label}
              </button>
            ))}
          </div>
        ))}
      </aside>

      <main className={styles.stage}>
        <h1 className={styles.stageTitle}>
          {active.group} — {active.label}
        </h1>
        <p className={styles.stageNote}>{active.note}</p>

        <div className={styles.hint}>
          Değerlerin tamamı <code>src/styles/tokens.css</code> içinden geliyor ve
          spec dosyasıyla birebir eşleşiyor. Metinler <code>src/strings.ts</code> içinde.
          Klavye: <code>Tab</code> ile gezin, composer'da <code>Enter</code> gönderir,
          <code>Shift+Enter</code> satır ekler.
        </div>
      </main>

      {/* --- Widget --- */}
      <div className="nm-root">
        <Launcher
          isOpen={isOpen}
          unreadCount={unreadCount || (scenario === "messages" ? 2 : 0)}
          onToggle={() => setIsOpen((v) => !v)}
        />

        <Panel
          isOpen={isOpen}
          title={panelTitle}
          onBack={
            showConversation || showArticle
              ? () => {
                  setOpenArticleId(null);
                  setScenario(showArticle ? "help" : "messages");
                }
              : undefined
          }
          onClose={() => setIsOpen(false)}
          footer={
            !showConversation && !showArticle ? (
              <TabBar active={effectiveTab} unreadCount={unreadCount} onChange={setTab} />
            ) : undefined
          }
        >
          {showConversation ? (
            <ConversationView
              messages={conversationMessages}
              state={conversationState}
              isTyping={scenario === "conversation-typing"}
              waitingForHuman={scenario === "conversation-waiting"}
              onContinueWithBot={() => setScenario("conversation")}
              composer={composer}
            />
          ) : showArticle ? (
            <ArticleView article={openArticle} />
          ) : effectiveTab === "home" ? (
            <HomeView
              recentConversation={mockConversations[0]}
              isTeamOnline
              onStartConversation={() => setScenario("conversation")}
              onOpenConversation={() => setScenario("conversation")}
              onOpenHelp={() => setTab("help")}
            />
          ) : effectiveTab === "messages" ? (
            <MessagesView
              conversations={conversations}
              state={messagesState}
              onOpenConversation={() => setScenario("conversation")}
              onStartConversation={() => setScenario("conversation")}
              onRetry={() => setScenario("messages")}
            />
          ) : (
            <HelpView
              query={helpQuery}
              onQueryChange={setHelpQuery}
              articles={helpArticles}
              onOpenArticle={(id) => setOpenArticleId(id)}
            />
          )}
        </Panel>
      </div>
    </div>
  );
}
