# Destek Widget'ı

Netmera'nın (ya da başka bir sitenin) sayfasına `<script>` ile gömülen sohbet
widget'ı. Arkasında bu projedeki mevcut çok-ajanlı bot, RAG araması ve personel
paneli çalışır — widget ayrı bir mantık taşımaz.

> **Durum: canlıya açık DEĞİL.** `WIDGET_API_ENABLED` varsayılan olarak `false`.
> Açmadan önce HTTPS gerekiyor (bkz. [Canlıya almadan önce](#canlıya-almadan-önce)).

---

## Nasıl açılır

### 1. Backend'i etkinleştir

`.env` içine:

```bash
WIDGET_API_ENABLED=true
# En az 32 karakter. Uretmek icin:
#   python -c "import secrets; print(secrets.token_urlsafe(32))"
WIDGET_TOKEN_SECRET=<güçlü rastgele değer>
# Virgülle ayrık. BOŞ BIRAKILIRSA hiçbir dış site widget'ı kullanamaz.
WIDGET_ALLOWED_ORIGINS=https://www.netmera.com
# IP başına dakikalık mesaj sınırı (LLM maliyet koruması)
WIDGET_RATE_LIMIT_PER_MIN=20
```

`WIDGET_TOKEN_SECRET` verilmezse uygulama açılışta net bir hatayla durur —
sessizce zayıf bir varsayılana düşmez.

### 2. Servisleri kaldır

```bash
docker compose build
docker compose up -d
docker compose restart nginx
```

### 3. Gömen sitede

```html
<script src="https://destek.netmera.com/widget/widget.js"
        data-api-base="https://destek.netmera.com/api/widget"
        defer></script>
```

CSS ayrıca eklenmez — betik kendi `src`'sinden `widget.css` yolunu türetip
`<link>` etiketini kendisi ekler.

Elle başlatmak isterseniz `data-api-base` vermeyin ve şunu çağırın:

```js
window.NetmeraWidget.init({
  apiBaseUrl: "https://destek.netmera.com/api/widget",
  defaultOpen: false,
  pollIntervalMs: 2000,
});
// Kaldırmak için:
window.NetmeraWidget.destroy();
```

---

## Nasıl temalanır

Tüm görsel değerler `widget/src/styles/tokens.css` içinde CSS custom property
olarak durur ve `.nm-root` altına kapsanmıştır (gömen sitenin stilleriyle
çakışmasın diye). Kaynak: `.claude/tasks/docs/support-widget.spec.md`.

Bir değeri değiştirmek için **önce spec'i güncelleyin**, sonra `tokens.css`'i —
kodun içine elle renk/ölçü yazmayın.

Gömen site marka rengini ezmek isterse:

```css
#netmera-widget-root .nm-root {
  --nm-color-brand: #0a5c3e;
  --nm-color-brand-contrast: #ffffff;
}
```

Kullanıcıya görünen **tüm metinler** `widget/src/strings.ts` içindedir.

---

## Backend sözleşmesi

Tüm uçlar `/api/widget` altında. `POST /session` dışındakiler
`Authorization: Bearer <token>` ister.

| Metot | Yol | Ne yapar | Arkasındaki servis |
|---|---|---|---|
| `POST` | `/session` | Anonim oturum açar, token döner | `chat_service.create_session` |
| `GET` | `/conversation` | O anki tam durum (polling buradan) | `chat_service.load_conversation` |
| `POST` | `/messages` | Mesaj gönderir, botu çalıştırır | `chat_service.send_message` |
| `POST` | `/contact` | Devir için ad/e-posta verir | `chat_service.submit_contact` |
| `POST` | `/resume-bot` | Devri askıya alır, botla devam | `chat_service.resume_bot` |
| `GET` | `/articles?q=` | Yardım araması (LLM çağrısı yok). `q` boşsa popüler Netmera başlıkları | `rag_search` |
| `GET` | `/health` | Sağlık kontrolü (flag kapalıyken de çalışır) | — |

**Token modeli:** `<session_id>.<hmac_sha256(secret, session_id)>`. Sunucu tarafında
durum tutulmaz, yeni tablo gerekmez. Karşılığı: token **iptal edilemez** — anonim
destek oturumu için kabul edildi. Hesaplı/kalıcı kimlik gerekirse gerçek bir oturum
tablosu gerekir; o zaman yalnızca `widget_api/session.py` değişir.

**Bilerek dönülmeyen alanlar:** `tool_calls`, `orchestrator`, `flow_status`. Bunlar
sistemin iç işleyişi (hangi agent, hangi araç, hangi güven skoru) — Streamlit
panelinde şeffaflık için gösterilir ama dış siteye gömülü widget'ta yabancı
ziyaretçiye sızmamalıdır.

**Gerçek zamanlılık:** Yok. `subscribe()` polling üzerine kuruludur (varsayılan 2 sn,
mevcut Streamlit konvansiyonuyla aynı). SSE/WebSocket eklenirse yalnızca
`httpTransport.subscribe()` değişir; bileşenler etkilenmez.

---

## Mimari

```
widget/src/
  components/    saf sunum bileşenleri — ağ çağrısı YOK, state YOK
  state/         useWidget.ts — TEK state sahibi, tüm yan etkiler burada
  ports/         ChatTransport/ChatIdentity/WidgetConfig/Telemetry + iki adapter
  WidgetApp.tsx  bileşenleri state'e bağlar
  embed.tsx      window.NetmeraWidget.init()
```

Kural iki cümlede:

- **Sunum bileşenlerinde** `fetch`, `localStorage` veya `timer` **yoktur.**
  Veriyi prop'tan alır, olayı callback ile yukarı verirler.
- **Yan etkiler iki sınırda toplanır:** `state/useWidget.ts` (state, efektler,
  polling aboneliği, localStorage) ve `ports/httpTransport.ts` (ağ çağrısı,
  oturum token'ı, polling zamanlayıcısı).

Bu ayrım sayesinde transport mock'lanınca tüm UI durumları ağa çıkmadan
üretilebiliyor.

Backend tarafında `widget_api/` iş mantığı içermez; her uç `app_services/`
çağırır. Streamlit panelleri de aynı servisleri kullandığı için iki ön yüz
ayrışamaz.

---

## Geliştirme

```bash
cd widget
npm install
npm run dev          # demo sayfası — localhost:5174
npm test             # 15 etkileşim/erişilebilirlik testi
npm run build        # demo build
npm run build:embed  # gömülebilir paket -> dist-embed/
```

Demo sayfasının iki modu var (sağ üstteki düğme):
- **Bileşen kataloğu** — 17 senaryo, elle kurulmuş durumlar (boş, yükleniyor, hata, yazıyor, uzun mesaj, mobil…)
- **Canlı (mock)** — gerçek `WidgetApp` + `useWidget`, ağ yerine `mockTransport`

---

## Erişilebilirlik

- **Klavye:** `Tab` panel içinde döner (focus trap), `Esc` kapatır, kapanınca odak
  launcher'a geri döner. Composer'da `Enter` gönderir, `Shift+Enter` satır ekler.
- **Ekran okuyucu:** panel `role="region"` + `aria-label`, sekmeler `role="tablist"`,
  mesaj listesi `role="log"` + `aria-live="polite"`.
- **Panel kapalıyken** `inert` ile klavye sırasından tamamen çıkarılır.
- **`prefers-reduced-motion`** desteklenir — animasyonlar devre dışı kalır.

---

## Bilinen eksikler

1. **HTTPS olmadan canlıya açılamaz** (aşağıda).
2. **Oturum açmış kullanıcı akışı yok.** Widget kullanıcıları her zaman anonim;
   `ChatIdentity.isAnonymous` bugün daima `true`. Arayüz o günü destekleyecek
   şekilde tanımlı ama implementasyon yok.
3. **Okunmamış sayacı her zaman 0.** Backend "müşteri bu mesajı gördü mü"
   bilgisini tutmuyor; rozet bileşeni hazır, veri yok.
4. **Token iptal edilemez** (yukarıdaki token modeli notu).
5. **Rate limit Redis'e bağımlı.** Redis düşerse sınır uygulanmaz (fail-open) —
   widget çalışmaya devam eder ama maliyet koruması kalkar. Redis uzun süre
   düşerse widget'ı flag ile kapatın.
6. **Otomatik e-posta gönderimi yok.** Devir bilgileri personel panelinde görünür,
   dönüş manuel yapılır.

---

## Canlıya almadan önce

**HTTPS zorunlu.** Widget HTTPS bir siteye gömülürse tarayıcı `http://` API
çağrılarını *mixed content* olarak bloke eder — widget sessizce çalışmaz.
Yani canlıya açmak bir domain + TLS sertifikası gerektirir (`DEPLOY.md` §8).

Sıra:
1. Domain'i sunucuya yönlendir, TLS al (Caddy ya da certbot).
2. `WIDGET_ALLOWED_ORIGINS`'e gömecek sitenin origin'ini yaz
   (pilotta `https://netmera-helpdesk.<IP>.sslip.io` da eklenebilir).
3. `WIDGET_TOKEN_SECRET` üret (`python -c "import secrets; print(secrets.token_urlsafe(32))"`).
4. `WIDGET_API_ENABLED=true` yap, servisleri yeniden kaldır:
   `docker compose up -d --force-recreate widget_api widget_build caddy`
5. Kontrol: `python scripts/widget_go_live_check.py`
6. Smoke: `https://<HOSTNAME>/widget/embed-test.html`
7. Rate limit'i trafiğe göre gözden geçir.

---

## Geri alma (revert)

Widget'ı tamamen devre dışı bırakmak için **kod geri almaya gerek yok**:

```bash
# .env icinde
WIDGET_API_ENABLED=false
docker compose up -d --force-recreate widget_api
```

Flag kapalıyken `/api/widget/*` uçlarının tamamı `404` döner ve mevcut Streamlit
panelleri hiçbir şekilde etkilenmez.

Kodu da kaldırmak isterseniz, widget tamamen ayrı dosyalarda durur:

```
widget/          (frontend)
widget_api/      (backend)
```

Bunlar silinirse ek olarak şu üç dosyadan widget bölümleri çıkarılmalıdır:
`docker-compose.yml` (`widget_api`, `widget_build`, `widget_dist`),
`nginx/nginx.conf` (`/api/widget/` ve `/widget/` blokları),
`config/settings.py` (`WIDGET_*` sabitleri).
