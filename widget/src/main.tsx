import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
// tokens.css bilesenlerden ONCE import edilir — reset/token katmani once
// gelsin diye. (Kurallar zaten :where() ile 0 ozgullukte, yani sira kritik
// degil; yine de dogru katman sirasi okunabilirlik icin korunuyor.)
import "./styles/tokens.css";
import { Playground } from "./dev/Playground";

/** Gelistirme girisi — AŞAMA 2'de yalnizca demo sayfasini acar.
 *  Gomulebilir embed girisi (window.NetmeraWidget.init) AŞAMA 4'te eklenecek. */
const container = document.getElementById("root");
if (container) {
  createRoot(container).render(
    <StrictMode>
      <Playground />
    </StrictMode>,
  );
}
