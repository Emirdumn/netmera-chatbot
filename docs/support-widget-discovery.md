# Destek Widget'ı — AŞAMA 0 Keşif Raporu

**Tarih:** 2026-07-30
**Kapsam:** `.claude/tasks/support-widget.md` AŞAMA 0 — sadece keşif, kod yazılmadı.

---

## ⛔ ÖNCE İKİ ENGELLEYİCİ BULGU

Aşağıdaki iki nokta netleşmeden AŞAMA 1'e geçilmemeli.

### 1. Spec geldi, ama yalnızca yarısı — port arabirimleri eksik

Görev dosyası `docs/support-widget.spec.md` yolunu işaret ediyor; dosya gerçekte
`.claude/tasks/docs/support-widget.spec.md` yolunda (1893 byte).

**İçinde olan** — AŞAMA 2 (sunum katmanı) için yeterli:

| Grup | Kapsam |
|---|---|
| `color` | 10 token. Marka `#5D1049`, kontrast `#FAFAFA`, metin `#14161A`/`#6C6F74`, yüzey `#FFFFFF`/`#F5F5F5`, kenar `#E5E5E5` + `rgba(9,14,21,.1)`, `danger` `#DF2020`, `online` `#22C55E` |
| `radius` | launcher `50%`, panel `24px`, bubble `20px`, card `12px`, composer `16px`, field `8px`, iconButton `10px`, pill `999px` |
| `shadow` | panel / card / nav — üçü de `rgba(9,14,21,…)` tabanlı |
| `size` | 16 ölçü. Panel `400px` genişlik, `calc(100vh - 104px)` yükseklik, launcher `48px`, header `64px`, tabBar `81px`, composer min `144px`, balon max %78 |
| `type` | `system-ui` yığını + 7 rol (greeting `600 28px/34px` → badge `700 11px/16px`) |
| `motion` | panelOpen `300ms cubic-bezier(.33,0,0,1)`, viewSlide `250ms translateX(8px)+fade`, typingDots `1200ms loop` vb. |
| `zIndex` | launcher `2147483000`, panel `2147483002` |
| `breakpoint` | `fullscreenBelow: 480` |
| `a11y` | panel `role=region` + `aria-label="Destek"`, `role=tablist`, mesaj listesi `role=log` + `aria-live=polite`, `aria-label="Kapat"` |

**İçinde OLMAYAN** — AŞAMA 3 (port & adapter) hâlâ yapılamaz:

> Görev dosyası AŞAMA 3'te şunu söylüyor: *"`ChatTransport`, `ChatIdentity`, `WidgetConfig`,
> `Telemetry` arabirimlerini spec içindeki **TypeScript tanımlarına göre** oluştur."*
> Spec'te **hiçbir TypeScript arabirim tanımı yok** — dosya baştan sona tek bir JSON token
> nesnesi. Bu dört portun metot imzaları, dönüş tipleri ve olay sözleşmesi bilinmiyor.

Ayrıca spec, bileşenlerin **görsel davranışını** değil yalnızca değerlerini veriyor:
hangi view'da ne gösterileceği, `HomeView`/`HelpView`/`ArticleListView` içerik düzeni,
boş/hata durumlarının kompozisyonu spec'te tarif edilmiyor. AŞAMA 2'de bunlar
görev dosyasındaki bileşen listesinden + token'lardan **türetilerek** yapılabilir,
ama "±1px tolerans" kriteri yalnızca token'ların geçtiği yerler için anlamlı olur.

**Not:** Başlıktaki *"kaynak: canlı widget'ın hesaplanmış CSS'i"* ifadesi ve
`2147483000` gibi maksimuma yakın z-index değerleri, token'ların üçüncü parti bir
destek widget'ından (Intercom benzeri) reverse-engineer edildiğini gösteriyor.
Bu, değerlerin tutarlı olduğu anlamına gelir; ama davranış/etkileşim kurallarının
hiçbirinin yazılı olmadığı anlamına da gelir.

### 2. Bu repo bir JS frontend projesi değil

Görev dosyası boyunca React/Next/Vue/Svelte/Angular, TypeScript, Tailwind/CSS-Modules,
Redux/Zustand, React Query, Storybook, Jest/Vitest/Playwright varsayılıyor.
Bu repoda bunların **hiçbiri yok**:

```
package.json          → yok
tsconfig.json         → yok
tailwind.config.*     → yok
node_modules/         → yok
.ts/.tsx/.jsx/.vue/.svelte dosya sayısı → 0
```

Proje: **Python 3.12 + Streamlit 1.60 + LangGraph 1.2.10** ile yazılmış, sunucu tarafında
render edilen çok-ajanlı bir yardım masası uygulaması. Tarayıcıya giden HTML'i Streamlit
üretiyor; JSX/bileşen ağacı, prop/callback modeli, client-side router ya da bundler yok.

**Sonuç:** Spec bir React/Vue widget'ı için yazıldıysa bu repoya "taşınamaz", ancak
**yeniden yorumlanabilir** (bkz. Riskli Nokta #1).

---

## Keşif soruları — bulgular

Görev dosyasındaki sırayla; her madde bu repodaki **gerçek** karşılığıyla yanıtlandı.

### Framework + sürüm, router, SSR

| Soru | Bulgu |
|---|---|
| Framework | **Streamlit 1.60.0** (Python 3.12.13). React/Next/Vue/Svelte/Angular yok. |
| Router tipi | Yok. İki ayrı Streamlit süreci = iki ayrı uygulama: `ui/customer_app.py` (:8501), `ui/agent_console.py` (:8502). Sayfa geçişi `st.rerun()` ile tüm scriptin baştan çalışmasıyla oluyor. |
| SSR var mı? | Etkin olarak **her şey sunucu tarafında**. Streamlit her etkileşimde Python scriptini yukarıdan aşağı yeniden çalıştırıp DOM'u websocket üzerinden günceller. "Hydration" kavramı yok, dolayısıyla AŞAMA 4'teki "SSR varsa yalnızca client'ta render et" maddesi bu projede karşılıksız. |

### TypeScript, strict, path alias

**Yok.** Tip sistemi olarak Python type hint'leri + **Pydantic v2** modelleri kullanılıyor
(ör. `agents/base.py:AgentResponse`, `agents/memory_agent.py:ExtractedFacts`).
`mypy`/`pyright` konfigürasyonu yok, tip kontrolü CI'da zorlanmıyor.
Path alias yok; importlar repo kökünden mutlak (`from storage import repository as repo`).
Script doğrudan çalıştırıldığında kök dizini `sys.path`'e ekleyen bir kalıp var:

```python
if __name__ == "__main__" and not __package__:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
```

### Stil sistemi ve tema tokenları

**Tasarım sistemi ya da token dosyası yok.** Stil, Streamlit'in kendi varsayılan temasından
geliyor. `.streamlit/config.toml` yalnızca bir performans ayarı içeriyor, tema tanımı yok:

```toml
[server]
fileWatcherType = "none"
```

Renk/spacing/radius için CSS değişkeni, SCSS, Tailwind ya da styled-components **yok**.
Görsel ayrım tamamen Streamlit primitifleriyle yapılıyor: `st.container(border=True)`,
`st.columns`, `st.expander`, `st.caption`, emoji öntakılar.

> **AŞAMA 1'deki token eşleme tablosu bu projede boş çıkar.** Spec 40+ token getiriyor
> (`--brand: #5D1049` vb.) ama karşısına yazılacak **hiçbir mevcut proje tokeni yok** —
> eşleme değil, **sıfırdan token katmanı kurma** işi. Streamlit'te bunun tek yolu
> `st.markdown(unsafe_allow_html=True)` ile `:root { --brand: … }` enjekte etmek;
> bu da guardrail 3'ün ("global CSS'e yıkıcı değişiklik yapma") sınırında bir hamle
> ve feature flag'in **içinde** kalmak zorunda.

### Mevcut tasarım sistemi bileşenleri

Proje-içi yeniden kullanılabilir bileşen kütüphanesi **yok**. Streamlit'in yerleşik
primitifleri kullanılıyor; görev dosyasındaki listeyle karşılığı:

| İstenen | Bu projedeki karşılığı |
|---|---|
| Button | `st.button`, `st.form_submit_button` |
| Input | `st.text_input`, `st.text_area`, `st.selectbox`, `st.toggle` |
| Avatar | `st.chat_message(role, avatar="👤")` |
| Modal / Sheet | **Yok** (Streamlit `st.dialog` mevcut ama projede kullanılmıyor) |
| Badge / Spinner | **Yok** / `st.progress`, `st.status` kullanılmıyor |
| Icon seti | **Yok** — emoji kullanılıyor (💬 🧑‍💼 📋 🧠 🔄 🔧) |

Proje-içi tek "bileşen" kalıbı: `ui/*.py` içindeki `_render_*` yardımcı fonksiyonları
(`_render_message`, `_render_sidebar`, `_render_customer_notes`, `_render_sources`).
Bunlar prop alıp callback dönen saf bileşenler değil; doğrudan `st.*` çağırıp yan etki üretiyorlar.

### State yönetimi / sunucu verisi

- **Client state:** `st.session_state` (Redux/Zustand/Context yok). Kullanılan anahtarlar:
  `session_id`, `staff_id`, `staff_name`, `department`, `active_handoff_id`, `online_toggle`.
- **Konuşma state'i:** LangGraph `HelpdeskState` (`graph/state.py`), `SqliteSaver`
  checkpointer ile `storage/data/checkpoints.db`'de kalıcı. `customer_profile`/`case_notes`
  için özel `merge_dict` reducer'ı var (boş değer eskiyi silmez).
- **Sunucu verisi:** React Query/SWR **yok**. Veri her rerun'da doğrudan SQLite'tan
  yeniden okunuyor; cache katmanı olarak `@st.cache_resource` yalnızca graph nesnesi için.

### API katmanı, hata yönetimi, auth token

- HTTP client **yok** — bu uygulama bir API tüketicisi değil. Veri erişimi tek kapıdan:
  **`storage/repository.py`** (SQLite üzerinde düz fonksiyonlar: `create_session`,
  `add_message`, `get_messages`, `create_handoff`, `list_pending_handoffs`,
  `claim_handoff`, `post_human_reply`, `upsert_notes`, `get_notes` …).
- Dış çağrı yapan tek katman: **`llm/client.py`** (`get_llm()` → Gemini ya da OpenRouter,
  `LLM_PROVIDER` env değişkeniyle seçiliyor).
- Merkezi hata yönetimi yok. Tek istisna `cache/qa_cache.py`: Redis erişilemezse tek sefer
  uyarı loglayıp sessizce devre dışı kalıyor (uygulamayı düşürmüyor).
- API auth token'ı yok; sırlar `.env` üzerinden `config/settings.py`'ye yükleniyor.

### Gerçek zamanlı altyapı

WebSocket/SSE/Pusher/Socket.io **yok**. Streamlit'in kendi websocket'i var ama uygulama
kodu ona erişmiyor. Canlı güncelleme **polling** ile:

```python
# ui/customer_app.py  (POLL_SECONDS = 2)
if is_waiting:
    time.sleep(POLL_SECONDS)
    st.rerun()

# ui/agent_console.py — bekleyen kuyruk ekranında
time.sleep(2)
st.rerun()
```

> AŞAMA 3'ün "gerçek zamanlı altyapı varsa `subscribe()` onun üzerine kurulsun, yoksa
> 5 sn polling" maddesi bu projeye **uyumlu**: zaten polling var, üstelik 2 sn.

### Auth / kullanıcı modeli

İki farklı ve birbirinden bağımsız kimlik kavramı var:

1. **Müşteri (anonim):** `ui/customer_app.py` oturum açtırmıyor.
   `repo.create_session("tr")` ile anonim bir `session_id` üretiliyor.
   Ad/e-posta yalnızca (a) konuşma sırasında `memory_agent` çıkarımıyla ya da
   (b) devir anında `contact_form_node`'un açtığı formla toplanıyor.
   → Görev dosyasındaki `identity.isAnonymous` akışı bu projenin **varsayılan** durumu.
2. **Personel (şifreli):** `ui/agent_console.py` içinde uygulama-içi giriş.
   `repo.verify_staff_password(staff_id, password)` → SHA-256 (`staff_id` tuzlu) +
   `hmac.compare_digest`. Başarılıysa kimlik `st.session_state`'e yazılıyor ve
   **departman kimlikten türetiliyor** (serbest seçilemiyor).
   Ayrıca dış katmanda nginx HTTP Basic Auth var (`:8082`).

Merkezi bir `useUser()` hook'u / selector yok; personel kimliği doğrudan
`st.session_state.staff_id / staff_name / department` üzerinden okunuyor.

### i18n

**i18n kütüphanesi yok, çeviri dosyası yok.** Kullanıcıya görünen metinlerin büyük kısmı
Türkçe olarak **koda gömülü** (görev dosyasının 5. guardrail'i ile doğrudan çelişiyor —
bkz. Riskli Nokta #3).

Dil yönetimi ikiye ayrılıyor:
- **Arayüz metinleri:** sabit Türkçe string'ler (`ui/*.py`, `agents/*.py` içindeki
  `LEAD_COMPLETE_MESSAGE`, `CANNOT_ANSWER_MESSAGE`, `OFF_TOPIC_MESSAGE` vb.).
- **Bot yanıtları:** çalışma zamanında `orchestrator` tarafından belirlenen
  `language: "tr" | "en"` alanına göre LLM'e "müşteriyle aynı dilde yaz" talimatı veriliyor.
- Tek yapılandırılmış ikidilli kalıp: `flows/base.py:Slot.question(language)` →
  `question_tr` / `question_en`.

### Portal / overlay konvansiyonu ve z-index

**Yok.** Streamlit DOM'u kendisi yönettiği için portal/overlay katmanı ya da
z-index ölçeği tanımlanmamış. Repoda özel `z-index` değeri **hiç geçmiyor**
(projede en yüksek z-index diye bir şey yok — Streamlit'in kendi iç değerleri geçerli).

Spec ise `launcher: 2147483000`, `panel: 2147483002` istiyor — yani 32-bit signed int
tavanına (`2147483647`) yakın, "her şeyin üstünde" anlamına gelen değerler. Bu, spec'in
**başka bir sitenin içine gömülen** bir widget için yazıldığını doğruluyor.

Streamlit'te bir öğeyi bu şekilde konumlandırmanın yolu yok: `st.*` çağrıları Streamlit'in
kendi yerleşim akışına yazıyor, `position: fixed` bir katman ancak `unsafe_allow_html`
ile CSS enjekte edilerek kurulabilir. Sonuç: spec'in `zIndex` + `panelOffsetRight/Bottom` +
`fullscreenBelow: 480` üçlüsü, Streamlit'in yerleşik düzen sistemiyle **karşılanamaz**;
CSS enjeksiyonu gerektirir (bkz. Riskli Nokta #1, yol A/B/C).

### Test altyapısı

pytest/unittest **requirements.txt'te yok**. `tests/` altındaki dosyalar
`assert` kullanan ama doğrudan `python tests/x.py` ile çalıştırılan **script**'ler:

```
tests/demo_scenarios.py      # 6 senaryo + run_orchestrator_regression() (asıl regresyon testi)
tests/test_tools.py          # devir araçları uçtan uca
tests/test_orchestrator.py   tests/test_flows.py
tests/test_react_loop.py     tests/test_router.py
tests/retrieval_benchmark.py # arama kalitesi ölçümü
```

Testler gerçek LLM'e ve gerçek SQLite'a vuruyor — **mock yok**. Testing Library /
Playwright / Storybook yok. Lint ya da typecheck adımı yok, CI dosyası yok.

> AŞAMA 5'in "transport mock'lanmış birim/etkileşim testleri" ve kabul kriterinin
> "lint + typecheck + testler geçiyor" maddesi için bu projede **altyapı kurulması** gerekir.

### Zaten bir chat/destek entegrasyonu var mı?

Intercom/Crisp/Zendesk gibi üçüncü parti **yok**. Ama en kritik bulgu:

> **Bu projenin kendisi zaten tam işlevli bir destek/chat sistemi.**

| Görev dosyasının istediği | Bu projede zaten var |
|---|---|
| ConversationView, MessageBubble | `ui/customer_app.py:_render_message` + `st.chat_message` |
| Composer | `st.chat_input` |
| MessagesView / okunmamış | `repo.get_messages(session_id)`, `ui/agent_console.py` kuyruğu |
| HelpView / ArticleView | RAG araması: `tools/rag_search_tool.py` (BM25 + vektör + rerank, ChromaDB) |
| Anonim kullanıcı + e-posta alanı | `graph/nodes.py:contact_form_node` (ad soyad + e-posta formu) |
| İnsana devir / agent inbox | `escalation_node` → `handoffs` tablosu → `ui/agent_console.py` |
| Typing / bekleme durumu | `human_wait_node` interrupt + "⏳ aktarılıyor" bilgilendirmesi |
| Telemetry | `tools/base.py` tool log'ları + `tool_logs` tablosu + `session_notes` |

İlgili dosyalar: `ui/customer_app.py`, `ui/agent_console.py`, `graph/workflow.py`,
`graph/nodes.py`, `agents/`, `tools/`, `storage/repository.py`.

---

## Spec'i bu projeye taşırken 3 riskli nokta

### 1. Hedef teknoloji uyuşmuyor — spec'in "birebir uygulanması" mümkün değil

Görev, prop alan / callback dönen / yan etkisiz **saf React bileşenleri** tarif ediyor
(AŞAMA 2). Streamlit'te böyle bir bileşen modeli yok: her fonksiyon çağrıldığı anda
doğrudan DOM'a yazıyor, dönüş değeri render edilmiyor. "Sunum bileşenlerinde tek bir
ağ çağrısı yok" kriteri Python fonksiyonlarında disiplinle sağlanabilir, ama
"±1px tolerans" ve `Panel/TabBar/Launcher` gibi overlay bileşenleri Streamlit'in
düzen modeliyle karşılanamaz.

**Üç gerçekçi yol var, biri seçilmeli:**

| Yol | Ne demek | Maliyet / risk |
|---|---|---|
| **A. Yeniden yorumla** | Spec'i "gömülebilir destek widget'ı" gereksinim listesi olarak okuyup Streamlit'in kendi primitifleriyle karşıla. | En düşük risk, mevcut mimariyle uyumlu. Piksel-birebir sonuç **vermez** → kabul kriteri gevşetilmeli. |
| **B. Streamlit custom component** | Widget'ı gerçek bir React bileşeni olarak yaz, `streamlit-components` ile iframe içinde göm. | Spec birebir uygulanabilir. Ama **yeni bağımlılık + Node/npm toolchain** gerekir (guardrail 2 → onay şart) ve iframe sınırı yüzünden "sayfa üstünde yüzen launcher" davranışı kısıtlı. |
| **C. Ayrı frontend** | Widget'ı bağımsız bir React uygulaması yapıp bu projeye HTTP API ekle. | Spec'e tam uyum. Ama bu artık "entegrasyon" değil **yeni bir servis** — mevcut Streamlit UI'ıyla ikili bakım yükü doğar. |

### 2. Widget, zaten var olan işlevle çakışma riski taşıyor

Bu proje **halihazırda canlıda** (PortvMind VM, `43.229.92.6`, Docker Compose ile 4 servis)
ve yukarıdaki tabloda görüldüğü gibi widget'ın vaat ettiği neredeyse her yeteneğe
kendi karşılığıyla sahip. Dikkatli bir kapsam çizilmezse ortaya **iki paralel sohbet arayüzü**
çıkar: aynı `sessions`/`messages`/`handoffs` tablolarına yazan, ama farklı state ve
farklı devir mantığı taşıyan iki yol.

Özellikle kırılgan iki nokta:

- **LangGraph interrupt akışı.** Devir sırasında konuşma `human_wait_node`'da `interrupt()`
  ile duruyor ve yalnızca `Command(resume=...)` ile devam ediyor. Widget bu akışın dışından
  mesaj yazarsa thread kilitli kalabilir ya da iki kez resume edilmeye çalışılabilir.
- **Oturum durumu (`sessions.status`).** `bot` / `waiting_human` / `with_human` geçişleri
  hem hangi arayüzün yazacağını hem de müşterinin bot ile konuşup konuşamayacağını
  belirliyor. İkinci bir arayüz bu durumu bağımsız değiştirirse, canlıda test edilmiş
  "bot ile devam et" ve "departman bazlı kuyruk" davranışları bozulur.

**Önerilen:** AŞAMA 1'de "widget mevcut `customer_app`'in **yerini mi alacak**, yanında mı
duracak, yoksa yalnızca dış sitelere gömülecek üçüncü bir kanal mı?" sorusu net karara bağlanmalı.

### 3. Guardrail'ler ile projenin bugünkü hali çelişiyor

Üç guardrail, mevcut kod tabanında karşılığı olmadığı için ya kapsam genişletir ya da
sessizce ihlal edilir:

- **Guardrail 5 ("hiçbir metni koda gömme"):** Projede i18n yok ve *mevcut* tüm kullanıcı
  metinleri koda gömülü. Üstelik **spec'in kendisi de** Türkçe metni token olarak taşıyor
  (`panelAriaLabel: "Destek"`, `closeAriaLabel: "Kapat"`) — yani spec bu guardrail'i
  varsaymıyor. Widget için tek bir `strings` dosyası açmak kolay; ama bu, projenin
  geri kalanıyla **tutarsız** iki ayrı yaklaşım demek. Karar gerekiyor: sadece widget mi
  `strings`'e taşınsın, yoksa proje geneli için bir i18n katmanı mı planlansın (ayrı iş).
- **Guardrail 1 ("yeni mimari dayatma"):** Bu proje bir tasarım sistemi, bileşen kütüphanesi,
  test koşucusu ve tip kontrolü **barındırmıyor**. AŞAMA 2 ve 5'in istedikleri
  (Storybook/demo sayfası, mock'lanmış birim testleri, typecheck) bunları kurmayı gerektiriyor —
  yani tanım gereği yeni altyapı. Nerede durulacağı önceden çizilmeli.
- **Kabul kriteri "flag kapalıyken uygulama davranışı hiç değişmiyor":** Streamlit'te
  feature flag genelde `if` bloğu; bu sağlanabilir. Ancak `st.markdown(unsafe_allow_html=True)`
  ile global CSS enjekte edilirse flag kapalı olsa bile stil sızıntısı olabilir — CSS
  enjeksiyonu flag'in **içinde** kalmalı.

---

## AŞAMA 0 sonucu — bekleniyor

Kod yazılmadı. AŞAMA 1'e geçmeden önce üç karar gerekiyor:

1. **Yol seçimi (Riskli Nokta #1): A / B / C.** Spec'in `zIndex: 2147483000`,
   `position:fixed` panel, `fullscreenBelow: 480` gibi gereksinimleri Streamlit'in
   yerleşim modeliyle karşılanamadığı için bu karar her şeyi belirliyor.
2. **Kapsam (Riskli Nokta #2):** widget mevcut `customer_app`'in **yerine mi** geçecek,
   yanında mı duracak, yoksa dış sitelere gömülecek **üçüncü bir kanal** mı?
   (Spec'in "başka siteye gömülen widget" karakteri 3. seçeneğe işaret ediyor.)
3. **Port arabirimleri:** `ChatTransport` / `ChatIdentity` / `WidgetConfig` / `Telemetry`
   tanımları spec'te yok. Ya bunlar paylaşılmalı ya da AŞAMA 3'te mevcut
   `storage/repository.py` fonksiyonlarından türetmem onaylanmalı.

Yol **A** seçilirse (Streamlit primitifleriyle yeniden yorumla): yeni bağımlılık gerekmez,
ama "±1px tolerans" kabul kriteri gevşetilmeli.
Yol **B/C** seçilirse: Node/npm toolchain ya da ayrı servis gerekir — guardrail 2 gereği
önce onayınızı isteyeceğim.
