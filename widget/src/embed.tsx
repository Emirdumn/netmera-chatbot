/** Gomulebilir giris noktasi (uretim).
 *
 * Dis site tek bir etiketle kullanir:
 *
 *   <script src="https://.../widget/widget.js"
 *           data-api-base="https://.../api/widget" defer></script>
 *
 * Ya da elle:
 *   window.NetmeraWidget.init({ apiBaseUrl: "..." })
 */
import { StrictMode } from "react";
import { createRoot, type Root } from "react-dom/client";
import { WidgetApp } from "./WidgetApp";
import { createHttpTransport } from "./ports/httpTransport";
import type { WidgetConfig } from "./ports/types";
import "./styles/tokens.css";

declare global {
  interface Window {
    NetmeraWidget?: {
      init: (config: WidgetConfig) => void;
      destroy: () => void;
    };
  }
}

const CONTAINER_ID = "netmera-widget-root";
let root: Root | null = null;

/** Betigin kendi src'sinden CSS yolunu turetir ve <link> ekler.
 *  Boylece gomen sitenin tek bir <script> etiketi yeterli olur. */
function injectStylesheet(): void {
  const current = document.currentScript as HTMLScriptElement | null;
  if (!current?.src) return;
  const href = current.src.replace(/\.js(\?.*)?$/, ".css");
  if (document.querySelector(`link[href="${href}"]`)) return;
  const link = document.createElement("link");
  link.rel = "stylesheet";
  link.href = href;
  document.head.appendChild(link);
}

function init(config: WidgetConfig): void {
  if (!config?.apiBaseUrl) {
    // Sessizce calismamaktansa gelistiriciye net soyle.
    console.error("[NetmeraWidget] apiBaseUrl zorunlu.");
    return;
  }
  if (root) return; // cift init'e karsi

  const container = document.createElement("div");
  container.id = CONTAINER_ID;
  document.body.appendChild(container);

  root = createRoot(container);
  root.render(
    <StrictMode>
      <WidgetApp transport={createHttpTransport(config)} config={config} />
    </StrictMode>,
  );
}

function destroy(): void {
  root?.unmount();
  root = null;
  document.getElementById(CONTAINER_ID)?.remove();
}

window.NetmeraWidget = { init, destroy };

// data-* nitelikleri verilmisse kendiliginden baslat.
(function autoInit() {
  const current = document.currentScript as HTMLScriptElement | null;
  const apiBaseUrl = current?.dataset.apiBase;
  injectStylesheet();
  if (!apiBaseUrl) return;

  const config: WidgetConfig = {
    apiBaseUrl,
    defaultOpen: current?.dataset.defaultOpen === "true",
  };
  const poll = Number(current?.dataset.pollInterval);
  if (Number.isFinite(poll) && poll > 0) config.pollIntervalMs = poll;

  // DOM hazir degilse bekle.
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", () => init(config), { once: true });
  } else {
    init(config);
  }
})();
