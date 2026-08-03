/** AŞAMA 4 — Montaj.
 *
 * Saf bilesenleri `useWidget` state'ine baglar. Kendisi state tutmaz,
 * transport cagirmaz; yalnizca hangi gorunumun cizilecegine karar verir.
 */
import { ArticleView } from "./components/ArticleView";
import { Composer } from "./components/Composer";
import { ConversationView } from "./components/ConversationView";
import { ErrorState } from "./components/ErrorState";
import { HelpView } from "./components/HelpView";
import { HomeView } from "./components/HomeView";
import { Launcher } from "./components/Launcher";
import { MessagesView } from "./components/MessagesView";
import { Panel } from "./components/Panel";
import { TabBar } from "./components/TabBar";
import type { ChatTransport, Telemetry, WidgetConfig } from "./ports/types";
import { strings } from "./strings";
import { useWidget } from "./state/useWidget";

export interface WidgetAppProps {
  transport: ChatTransport;
  config: WidgetConfig;
  telemetry?: Telemetry;
}

export function WidgetApp({ transport, config, telemetry }: WidgetAppProps) {
  const w = useWidget({ transport, config, telemetry });

  const showArticle = w.openArticle !== null;
  const showConversation = w.inConversation && !showArticle;

  const title = showArticle
    ? strings.help.title
    : showConversation
      ? strings.messages.bot
      : w.tab === "messages"
        ? strings.messages.title
        : w.tab === "help"
          ? strings.help.title
          : strings.panel.ariaLabel;

  const onBack = showArticle
    ? w.closeArticle
    : showConversation
      ? w.leaveConversation
      : undefined;

  const composer = (
    <Composer
      value={w.draft}
      onChange={w.setDraft}
      onSend={w.needsContactForm ? w.submitContact : w.send}
      disabled={w.isSending}
      // Widget kullanicilari her zaman anonim; e-posta alani devir
      // beklerken gorunur (bkz. docs/support-widget-plan.md kapsam notu).
      isAnonymous={w.needsContactForm}
      email={w.email}
      onEmailChange={w.setEmail}
      emailError={w.emailTouched && !/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(w.email.trim())}
    />
  );

  return (
    <div className="nm-root">
      <Launcher isOpen={w.isOpen} onToggle={w.toggle} buttonRef={w.launcherRef} />

      <Panel
        panelRef={w.panelRef}
        isOpen={w.isOpen}
        title={title}
        onBack={onBack}
        onClose={w.close}
        footer={
          !showConversation && !showArticle ? (
            <TabBar active={w.tab} onChange={w.setTab} />
          ) : undefined
        }
      >
        {w.conversationState === "error" && !showArticle ? (
          <ErrorState onRetry={w.retry} />
        ) : showArticle ? (
          <ArticleView
            article={w.openArticle ?? undefined}
            state={w.articleState}
          />
        ) : showConversation ? (
          <ConversationView
            messages={w.messages}
            state={w.conversationState}
            isTyping={w.isSending}
            waitingForHuman={w.isWaiting}
            onContinueWithBot={w.resumeBot}
            onRetry={w.retry}
            onOpenSource={(source) => void w.openSource(source.url)}
            composer={composer}
            logRef={w.logRef}
          />
        ) : w.tab === "home" ? (
          <HomeView
            recentConversation={w.conversations[0]}
            onStartConversation={w.openConversation}
            onOpenConversation={w.openConversation}
            onOpenHelp={() => w.setTab("help")}
          />
        ) : w.tab === "messages" ? (
          <MessagesView
            conversations={w.conversations}
            state={w.conversationState}
            onOpenConversation={w.openConversation}
            onStartConversation={w.openConversation}
            onRetry={w.retry}
          />
        ) : (
          <HelpView
            query={w.helpQuery}
            onQueryChange={w.setHelpQuery}
            articles={w.articles}
            state={w.helpState}
            onOpenArticle={w.openArticleById}
            onRetry={w.retry}
          />
        )}
      </Panel>
    </div>
  );
}
