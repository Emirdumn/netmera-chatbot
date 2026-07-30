# Destek Widget'ı — AŞAMA 1 Entegrasyon Planı

**Tarih:** 2026-07-30
**Durum:** Öneri — onay bekliyor. Kod yazılmadı.
**Girdi:** `docs/support-widget-discovery.md` (AŞAMA 0) + `.claude/tasks/docs/support-widget.spec.md`

---

## Alınan kararlar

| Karar | Seçim |
|---|---|
| Yol | **C** — dış sitelere gömülen bağımsız widget (React) + bu projeye HTTP API |
| Kapsam | **Üçüncü kanal** — canlıdaki `customer_app` ve `agent_console`'a dokunulmaz |
| Port tanımları | Mevcut `storage/repository.py` + `graph/workflow.py`'den **türetilecek**, AŞAMA 3'te onaya sunulacak |

**Bu kararların doğrudan sonucu:** Bu artık bir "widget entegrasyonu" değil, mevcut sisteme
**iki yeni servis** eklemek. Backend'de HTTP API (bu projede hiç yok — Streamlit var),
frontend'de ayrı bir React uygulaması. Planın geri kalanı bunun üzerine kurulu.

---

## ⚠️ ÖNCE: Onay gerektiren yeni bağımlılıklar (guardrail 2)

Yol C, bu projede bulunmayan iki toolchain'i zorunlu kılıyor. **Onayınız olmadan hiçbirini kurmam.**

### Backend (Python) — `requirements.txt`'e eklenecek

| Paket | Neden zorunlu | Alternatif |
|---|---|---|
| `fastapi` | Widget'ın konuşacağı HTTP API. Streamlit bir API sunucusu değil — dışarıdan JSON isteği alamaz. | `flask` (daha az bağımlılık ama async yok, tip doğrulama manuel). Pydantic v2 zaten kurulu olduğu için FastAPI daha uyumlu. |
| `uvicorn` | FastAPI'yi çalıştıran ASGI sunucusu. | — (FastAPI için fiilen zorunlu) |

> CORS için ek paket gerekmez, FastAPI'nin içinde geliyor.

### Frontend (Node/npm) — yeni `widget/` klasöründe, ayrı `package.json`

| Paket | Neden |
|---|---|
| `react`, `react-dom` | Spec bileşen mimarisi (Launcher/Panel/TabBar/…) React için yazılmış |
| `vite` | Build + dev sunucusu. Tek `.js` + `.css` dosyasına derleyip dış siteye `<script>` ile gömmek için. |
| `typescript` | Spec'in port arabirimleri (AŞAMA 3) TypeScript olarak isteniyor |
| `vitest` + `@testing-library/react` | AŞAMA 5'in "transport mock'lanmış etkileşim testleri" kriteri |

**Node.js kurulumu gerekir** — bu makinede/VM'de şu an npm toolchain'i yok.
Bu, projeye ikinci bir dil ekosistemi sokmak demek (bakım yükü: iki lockfile, iki güvenlik
güncelleme akışı, iki CI adımı).

> **Kararınızı bekliyorum.** Onaylamazsanız Yol A'ya (Streamlit primitifleri) dönmek
> gerekir — o durumda bu planın frontend yarısı tamamen değişir.

---

## Mimari — mevcut sisteme ne ekleniyor

```
                          ┌──────────────────────────────┐
  Netmera web sitesi ───► │  widget.js  (yeni, React)    │
  (dış site)              │  <script src=…/widget.js>    │
                          └──────────────┬───────────────┘
                                         │  HTTPS + CORS
                                         ▼
┌────────────────────────────────────────────────────────────────┐
│  nginx  (mevcut — sadece yeni bir location bloğu eklenir)      │
│    :80    /            → customer_app      (DOKUNULMAZ)        │
│    :80    /widget/     → widget statikleri (YENİ)              │
│    :80    /api/widget/ → widget_api        (YENİ)              │
│    :8082  /            → agent_console     (DOKUNULMAZ)        │
└────────────────────────────────────────────────────────────────┘
                                         │
                                         ▼
                          ┌──────────────────────────────┐
                          │  widget_api  (yeni, FastAPI) │
                          │  feature flag arkasında      │
                          └──────────────┬───────────────┘
                                         │  doğrudan import
                                         ▼
        ┌────────────────────────────────────────────────────┐
        │  MEVCUT ÇEKİRDEK — hiç değiştirilmiyor             │
        │  graph/workflow.py · storage/repository.py         │
        │  agents/ · tools/ · cache/                         │
        └────────────────────────────────────────────────────┘
                                         │
                          SQLite (sessions/messages/handoffs) · ChromaDB · Redis
```

**Kritik tasarım kararı:** `widget_api`, mevcut Python modüllerini **doğrudan import ediyor**
(HTTP üzerinden değil). Yani iş mantığı tek yerde kalıyor; widget yeni bir mantık kopyası
değil, mevcut çekirdeğin ikinci bir "ön yüzü". Streamlit uygulamaları da aynı çekirdeği
kullanmaya devam ediyor.

**Yan fayda:** Widget'tan gelen devirler aynı `handoffs` tablosuna düştüğü için,
`agent_console`'daki departman bazlı kuyruk **hiçbir değişiklik olmadan** çalışır.

---

## Dosya ağacı — oluşturulacak / dokunulacak TÜM dosyalar

### Yeni: Backend API

```
widget_api/
├── __init__.py
├── main.py                 # FastAPI app, CORS, feature flag guard
├── routes.py               # endpoint'ler (aşağıdaki sözleşme)
├── schemas.py              # Pydantic istek/yanıt modelleri
├── session.py              # anonim oturum token'ı üretimi/doğrulaması
└── deps.py                 # graph singleton, rate limit
```

### Yeni: Frontend widget

```
widget/
├── package.json            # ← yeni bağımlılıklar burada (onay sonrası)
├── vite.config.ts
├── tsconfig.json
├── index.html              # yalnızca yerel geliştirme için
├── src/
│   ├── main.tsx            # embed giriş noktası (window.NetmeraWidget.init)
│   ├── tokens.css          # spec'teki token'lar → CSS custom properties
│   ├── strings.ts          # TÜM metinler burada (guardrail 5)
│   ├── ports/
│   │   ├── types.ts        # ChatTransport / ChatIdentity / WidgetConfig / Telemetry
│   │   ├── httpTransport.ts    # gerçek implementasyon (widget_api'ye konuşur)
│   │   └── mockTransport.ts    # test + demo için
│   ├── components/         # SAF bileşenler — sıfır ağ çağrısı (guardrail 4)
│   │   ├── Launcher.tsx        TabBar.tsx         MessageBubble.tsx
│   │   ├── Panel.tsx           HomeView.tsx       TypingIndicator.tsx
│   │   ├── MessagesView.tsx    ConversationView.tsx  Composer.tsx
│   │   ├── HelpView.tsx        ArticleListView.tsx   ArticleView.tsx
│   │   └── SkeletonStates.tsx  ErrorState.tsx
│   ├── state/
│   │   └── useWidget.ts    # tek state sahibi; portları çağıran YEGANE yer
│   └── dev/
│       └── Playground.tsx  # mock veriyle tüm durumlar (AŞAMA 2 çıktısı)
└── tests/
    └── *.test.tsx
```

### Dokunulacak mevcut dosyalar — **toplam 4, hepsi toplama (additive)**

| Dosya | Değişiklik | Risk |
|---|---|---|
| `config/settings.py` | 3 yeni sabit ekle (aşağıda) | Yok — yalnızca ekleme |
| `docker-compose.yml` | `widget_api` servisi ekle | Düşük — mevcut servisler aynen kalır |
| `nginx/nginx.conf` | `:80` bloğuna 2 yeni `location` | **Orta** — mevcut `location /` etkilenmemeli (aşağıda) |
| `requirements.txt` | `fastapi`, `uvicorn` | Onay sonrası |

### Kesinlikle DOKUNULMAYACAK

```
ui/customer_app.py      ui/agent_console.py     graph/*        agents/*
tools/*                 storage/repository.py   storage/db.py  cache/*
```

> `storage/db.py` şeması da değişmiyor — **şema migration'ı yok**. (Bir istisna
> önerisi için "Açık sorular" #2'ye bakın.)

---

## Token eşleme tablosu

AŞAMA 0'da tespit edildiği gibi bu projede **eşlenecek mevcut token yok**. Yol C sayesinde
bu artık sorun değil: token'lar Streamlit'e enjekte edilmiyor, widget'ın **kendi** CSS
kapsamında yaşıyor. Eşleme birebir ve mekanik:

| Spec grubu | Hedef | Örnek |
|---|---|---|
| `color.*` | `widget/src/tokens.css` → `--nm-color-*` | `brand: #5D1049` → `--nm-color-brand: #5D1049` |
| `radius.*` | `--nm-radius-*` | `panel: 24px` → `--nm-radius-panel: 24px` |
| `shadow.*` | `--nm-shadow-*` | `panel: 0 5px 40px rgba(9,14,21,.16)` |
| `size.*` (sayısal) | `--nm-size-*`, `px` eklenerek | `launcher: 48` → `--nm-size-launcher: 48px` |
| `size.panelMaxHeight` | doğrudan string | `calc(100vh - 104px)` |
| `type.*` | `--nm-type-*` (CSS `font` kısayolu) | `greeting: "600 28px/34px"` → `font: var(--nm-type-greeting) var(--nm-font-family)` |
| `motion.*` | `--nm-motion-*` | `panelOpen: 300ms cubic-bezier(.33,0,0,1)` |
| `zIndex.*` | `--nm-z-*` | `launcher: 2147483000` |
| `breakpoint.fullscreenBelow` | media query sabiti | `@media (max-width: 479px)` |
| `a11y.*` | **CSS değil** — bileşen `aria-*` nitelikleri; metinler `strings.ts`'ten | `panelAriaLabel: "Destek"` |

**İki not:**
- `type.family` spec'te `system-ui, "Segoe UI", Roboto, …` — sistem fontu, webfont yüklenmiyor. İyi: gömüldüğü sitenin yüklenme süresine ek yük yok.
- `a11y` metinleri (`"Destek"`, `"Kapat"`) guardrail 5 gereği `strings.ts`'e taşınacak, spec'teki token'a değil ona referans verilecek.

**Tüm widget CSS'i `.nm-widget` kök sınıfı altında kapsamlanacak** ve `all: initial` ile
başlayacak — gömüldüğü sitenin stilleri widget'a, widget'ınki siteye sızmasın.

---

## Bileşenler: yeniden kullanılan / yeni yazılan

### Frontend

**Yeniden kullanılan: hiçbiri.** Bu projede React bileşeni yok (AŞAMA 0). Spec'teki 14
bileşenin tamamı yeni yazılacak. Guardrail 1 ("yeni mimari dayatma") burada ihlal edilmiyor,
çünkü mevcut mimariye dokunmuyoruz — yanına ayrı bir uygulama koyuyoruz.

### Backend — mevcut mantığın tamamı yeniden kullanılıyor

| Widget ihtiyacı | Yeniden kullanılan mevcut kod | Yeni kod |
|---|---|---|
| Oturum açma | `repo.create_session(language)` | — |
| Mesaj gönderme | `graph.invoke({...}, config=thread_config)` | ince HTTP sarmalayıcı |
| Mesaj geçmişi | `repo.get_messages(session_id)` | — |
| Bekleme durumu | `repo.get_session(session_id)["status"]` | — |
| İletişim formu | `Command(resume={"name","email"})` → `contact_form_node` | — |
| "Bot ile devam et" | `repo.resume_bot_mode(session_id)` + interrupt drain | mevcut mantık taşınır |
| Yardım/makale arama | `tools/rag_search_tool.py:rag_search` | — |
| Personele düşme | `escalation_node` → `handoffs` (otomatik) | — |
| Telemetri | `tools/base.py` tool log'ları + `tool_logs` tablosu | — |

**Sıfır iş mantığı kopyalanmıyor.** `widget_api` yalnızca HTTP↔Python çevirisi yapıyor.

---

## API sözleşmesi (AŞAMA 3'te kesinleşecek)

Endpoint isimleri uydurulmadı — mevcut `repository.py`/`graph` fonksiyonlarından türetildi:

| Metot | Yol | Karşılığı |
|---|---|---|
| `POST` | `/api/widget/session` | `repo.create_session("tr")` → `{sessionId, token}` |
| `GET` | `/api/widget/session/{id}/messages` | `repo.get_messages` + `repo.get_session().status` |
| `POST` | `/api/widget/session/{id}/messages` | `graph.invoke(...)` |
| `POST` | `/api/widget/session/{id}/contact` | `Command(resume={name,email})` |
| `POST` | `/api/widget/session/{id}/resume-bot` | interrupt drain + `repo.resume_bot_mode` |
| `GET` | `/api/widget/articles?q=` | `rag_search.invoke(...)` |

`subscribe()` gerçek zamanlı altyapı olmadığı için **polling** ile başlayacak
(mevcut konvansiyon 2 sn — `ui/customer_app.py:POLL_SECONDS`). Arayüz `ChatTransport`
arkasında soyutlanacak, ileride SSE'ye geçmek bileşenleri değiştirmeyecek.

---

## Montaj ve feature flag

### Backend flag — `config/settings.py`

Mevcut konvansiyona (`os.environ.get(...)`) birebir uyumlu, 3 yeni sabit:

```python
WIDGET_API_ENABLED = os.environ.get("WIDGET_API_ENABLED", "false").lower() == "true"
WIDGET_ALLOWED_ORIGINS = os.environ.get("WIDGET_ALLOWED_ORIGINS", "")   # virgülle ayrık
WIDGET_RATE_LIMIT_PER_MIN = int(os.environ.get("WIDGET_RATE_LIMIT_PER_MIN", "20"))
```

**Varsayılan kapalı.** `WIDGET_API_ENABLED=false` iken `widget_api` konteyneri ayağa kalksa
bile tüm endpoint'ler `404` döner; nginx `/api/widget/` yolu da o zaman bir şeye hizmet
etmez. Mevcut `:80/` ve `:8082/` davranışı **hiçbir koşulda** değişmez → kabul kriteri
"flag kapalıyken uygulama davranışı hiç değişmiyor" sağlanır.

### Frontend gömme (dış sitede)

```html
<script src="https://.../widget/widget.js"
        data-api-base="https://.../api/widget"
        defer></script>
```

`main.tsx` kendi kök `<div>`'ini oluşturup React'i oraya mount eder. SSR yok — zaten
tarayıcıda çalışıyor, hydration riski yok.

### localStorage anahtarları

Projede localStorage konvansiyonu yok (Streamlit `st.session_state` kullanıyor).
Widget kendi ad alanını kullanacak, gömüldüğü sitenin anahtarlarıyla çakışmasın:

```
netmera.widget.sessionToken     netmera.widget.open     netmera.widget.draft
```

---

## Kapsam dışı (bu iş paketinde YAPILMAYACAK)

1. **Mevcut Streamlit arayüzlerine hiçbir değişiklik** — `customer_app`, `agent_console` aynen kalır.
2. **Şema migration'ı yok** — `sessions`/`messages`/`handoffs` olduğu gibi kullanılır.
3. **Otomatik e-posta gönderimi yok** — daha önce kararlaştırıldığı gibi, iletişim bilgisi
   panelde görünür, personel manuel döner.
4. **Projeye genel i18n katmanı kurulmuyor** — yalnızca widget'ın kendi `strings.ts`'i.
   Mevcut Python tarafındaki gömülü Türkçe metinler olduğu gibi kalır.
5. **Gerçek zamanlı (SSE/WebSocket) altyapı yok** — polling ile başlanır.
6. **HTTPS/sertifika kurulumu yok** — `DEPLOY.md`'de opsiyonel olarak duruyor.
   *Ancak:* widget dış sitelere gömüleceği için, o siteler HTTPS ise tarayıcı
   HTTP API'ye isteği **mixed content** olarak engeller (bkz. Açık sorular #1).
7. **Kimlik doğrulamalı (oturum açmış) kullanıcı akışı yok** — widget kullanıcıları
   her zaman anonim. Spec'in `identity.isAnonymous` dalı hep `true`.
8. **Storybook kurulmuyor** — bunun yerine `widget/src/dev/Playground.tsx` (görev dosyası
   "Storybook varsa" diyor; yok, o yüzden demo sayfası).

---

## Açık sorular — AŞAMA 2'ye geçmeden yanıt gerekiyor

1. **HTTPS zorunlu hale geliyor.** Widget HTTPS bir siteye gömülürse, tarayıcı
   `http://43.229.92.6/api/widget/` çağrılarını mixed-content olarak **bloke eder**.
   Yani bu iş paketi pratikte bir domain + TLS sertifikası gerektiriyor.
   → Domain var mı, yoksa Let's Encrypt kurulumu bu işe dahil mi?
2. **Personel talebin nereden geldiğini görecek mi?** Şu an `handoffs` tablosunda kanal
   bilgisi yok; widget'tan gelen talep panelde Streamlit'ten gelenle aynı görünür.
   Ayırt edilmesi isteniyorsa `handoffs`'a `channel TEXT DEFAULT 'web'` kolonu eklemek
   gerekir (küçük, geriye uyumlu bir migration — ama "şema değişmeyecek" kapsamını deler).
   → Gerekli mi?
3. **Kötüye kullanım koruması.** Widget internete tamamen açık bir LLM uç noktası demek;
   her mesaj OpenRouter'a para harcıyor. Planda basit bir IP başına rate limit var
   (`WIDGET_RATE_LIMIT_PER_MIN=20`). Yeterli mi, yoksa CAPTCHA / origin allowlist
   zorunluluğu / günlük kota da mı istiyorsunuz?
4. **Widget nerede host edilecek?** Plan, aynı VM'de nginx'in `/widget/` yolundan statik
   servis etmeyi varsayıyor. Ayrı bir CDN/statik host tercih ediyor musunuz?

---

## Onay sonrası ilk adım

Onaylarsanız AŞAMA 2'ye geçerim: **yalnızca saf sunum bileşenleri** + mock transport'lu
demo sayfası. O aşamada hiçbir ağ çağrısı, hiçbir backend kodu olmayacak — spec'teki
ölçü/renk/animasyon/a11y değerleri birebir uygulanmış 14 bileşen ve tüm durumların
(boş, yükleniyor, hata, yazıyor, okunmamış, uzun mesaj, çok satırlı composer, mobil
tam ekran) görülebildiği bir `Playground`.

Backend (`widget_api`) AŞAMA 3'te yazılacak.
