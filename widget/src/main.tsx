import { StrictMode, useState } from "react";
import { createRoot } from "react-dom/client";
import { Playground } from "./dev/Playground";
import { WidgetApp } from "./WidgetApp";
import { createMockTransport } from "./ports/mockTransport";
// tokens.css bilesenlerden ONCE import edilir — reset/token katmani once
// gelsin diye. (Kurallar zaten :where() ile 0 ozgullukte, yani sira kritik
// degil; yine de dogru katman sirasi okunabilirlik icin korunuyor.)
import "./styles/tokens.css";

/** Gelistirme girisi. Iki mod:
 *  - "Bilesen katalogu" : saf bilesenler, elle kurulmus senaryolar (AŞAMA 2)
 *  - "Canli (mock)"     : gercek WidgetApp + useWidget, mock transport (AŞAMA 4)
 */
function DevRoot() {
  const [live, setLive] = useState(false);
  const [transport] = useState(() => createMockTransport({ messages: [], latencyMs: 250 }));

  return (
    <>
      <button
        type="button"
        onClick={() => setLive((v) => !v)}
        style={{
          position: "fixed",
          top: 12,
          right: 12,
          zIndex: 2147483040,
          padding: "8px 14px",
          borderRadius: 999,
          border: "1px solid #3b3663",
          background: live ? "#3b3663" : "#fff",
          color: live ? "#fff" : "#3b3663",
          font: '600 13px Rubik, system-ui, sans-serif',
          cursor: "pointer",
        }}
      >
        {live ? "← Bileşen kataloğu" : "Canlı (mock transport) →"}
      </button>

      {live ? (
        <div style={{ padding: 40, font: "400 15px/22px Rubik, system-ui, sans-serif" }}>
          <h1 style={{ font: "600 20px/26px Rubik, system-ui, sans-serif" }}>
            Canlı mod — mock transport
          </h1>
          <p style={{ color: "#696687", maxWidth: "60ch" }}>
            Gerçek <code>WidgetApp</code> + <code>useWidget</code> çalışıyor; ağ yerine
            <code> mockTransport</code> var. Mesaj yazıp gönderin. "temsilci" kelimesini
            içeren bir mesaj devir akışını (iletişim formu → bot ile devam et) tetikler.
          </p>
          <WidgetApp
            transport={transport}
            config={{ apiBaseUrl: "mock://", defaultOpen: true, pollIntervalMs: 0 }}
          />
        </div>
      ) : (
        <Playground />
      )}
    </>
  );
}

const container = document.getElementById("root");
if (container) {
  createRoot(container).render(
    <StrictMode>
      <DevRoot />
    </StrictMode>,
  );
}
