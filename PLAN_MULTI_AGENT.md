# Netmera Multi-Agent Help Desk — Faz Planı

> **Bu dosya nasıl kullanılır:** VS Code terminalinde Claude'u aç ve her faz için şunu yaz:
> ```
> PLAN_MULTI_AGENT.md dosyasindaki FAZ 2 bolumunu oku ve adim adim uygula.
> ```
> Her fazın sonunda **doğrulama komutu** ve **bitti kriteri** var. O kriter sağlanmadan
> sonraki faza geçme. Fazlar sırayla bağımlıdır.

---

## 1. Neden Yeniden Yapıyoruz

Mevcut v1 (`app.py`) tek-agent RAG. Çalışıyor ama üç yapısal sorunu var:

| Sorun | Etkisi | Çözüm fazı |
|---|---|---|
| **Developer Guide (190 sayfa) veri setinde yok** | iOS/Android/Web SDK, API, entegrasyon sorularının hiçbiri cevaplanamıyor | FAZ 1 |
| **Kör chunking** (1200 karakterde keser) | Markdown başlıkları ortadan bölünüyor, retrieval isabetsiz | FAZ 1 |
| **Tek agent, tek prompt** | Satış sorusuyla SDK sorusu aynı muameleyi görüyor; bilmediğinde uyduruyor veya susuyor | FAZ 3-5 |
| **Çıkış yolu yok** | Bot çözemezse sohbet çıkmaza giriyor, insana devir mekanizması yok | FAZ 4-7 |

**Veri envanteri (doğrulanmış):**

| Kaynak | Sayfa | Durum |
|---|---|---|
| `user.netmera.com/netmera-user-guide` | 218 | ✅ mevcut (217) |
| `user.netmera.com/netmera-developer-guide` | 190 | ❌ **eksik** → FAZ 1 |
| `netmera.com` (sitemap) | 185 | ✅ mevcut |
| **Toplam** | **~593** | |

> Not: `docs/support/help/sdk/blog.netmera.com` alt alan adlarının hepsi ana siteye
> yönleniyor — ek kaynak değiller. İki gerçek GitBook space var, ikisi de `.md` uçlu
> sayfa sunuyor ve `llms.txt` ile tam sayfa listesi veriyor.

---

## 2. Hedef Mimari

```
                          ┌──────────────────┐
   Müşteri  ──────────►   │  customer_app    │  (Streamlit :8501)
                          └────────┬─────────┘
                                   │
                          ┌────────▼─────────┐
                          │  LangGraph       │
                          │  workflow.py     │
                          └────────┬─────────┘
                                   │
                         ┌─────────▼──────────┐
                         │   ROUTER AGENT     │  niyet + dil + departman
                         └─────────┬──────────┘
              ┌──────────┬─────────┼─────────┬──────────┐
              ▼          ▼         ▼         ▼          ▼
          ┌───────┐ ┌────────┐ ┌────────┐ ┌───────┐ ┌──────────┐
          │ SALES │ │SUPPORT │ │TECHNICAL│ │GENERAL│ │ESCALATION│
          └───┬───┘ └───┬────┘ └───┬────┘ └───┬───┘ └────┬─────┘
              │         │          │          │          │
              └─────────┴────┬─────┴──────────┘          │
                             ▼                            │
                    ┌─────────────────┐                   │
                    │  TOOL KATMANI   │                   │
                    │ rag_search      │                   │
                    │ glossary        │                   │
                    │ lead_capture    │                   │
                    │ demo_booking    │                   │
                    │ sentiment       │                   │
                    └─────────────────┘                   │
                             │                            │
                    ┌────────▼────────┐                   │
                    │ GÜVEN KONTROLÜ  │───düşük güven────►┤
                    └────────┬────────┘                   │
                             │ yeterli                     │
                             ▼                    ┌────────▼────────┐
                        Müşteriye cevap           │  interrupt()    │
                                                  │  graf DONAR     │
                                                  └────────┬────────┘
                                                           │ SQLite
                                                  ┌────────▼────────┐
                          Personel ──────────►    │  agent_console  │ (:8502)
                                                  └─────────────────┘
```

### Devir (escalation) tetikleyicileri

Bunlardan **herhangi biri** doğruysa `escalation_agent` devreye girer:

| # | Tetikleyici | Nasıl ölçülür |
|---|---|---|
| 1 | RAG hiç ilgili doküman bulamadı | En iyi sonucun benzerliği `< CONFIDENCE_THRESHOLD` (0.35) |
| 2 | Agent kendi cevabından emin değil | LLM yapılandırılmış çıktıda `can_answer: false` döndü |
| 3 | Müşteri açıkça insan istedi | Router `intent = handoff_request` |
| 4 | Müşteri sinirlenmiş | `sentiment_tool` → `frustrated` |
| 5 | Üst üste başarısız denemeler | `failed_attempts >= 2` |

### Departman yönlendirmesi

| Niyet | Departman | Örnek |
|---|---|---|
| `sales` | Satış | "Satın almak istiyorum", "fiyat nedir", "demo" |
| `support` | Müşteri Başarı | "Segment oluşturamıyorum", "push gitmiyor" |
| `technical` | Teknik Destek / SDK | "iOS SDK entegrasyonu", "API 401 veriyor" |
| `general` | — (devir yok) | "Netmera nedir", "hangi sektörlere hizmet veriyor" |

---

## 3. Klasör Yapısı

Mevcut `data/` ve `chroma_db/` **korunuyor** (4.3 MB veri + 63 MB indeks boşa gitmesin).
v1 dosyaları `v1_legacy/` altına taşınıyor — sunumda "önce/sonra" karşılaştırması için duruyor.

```
netmera-helpdesk/
├── .env                          # GEMINI_API_KEY + ayarlar (git'e girmez)
├── requirements.txt
├── README.md
├── run_customer.sh               # müşteri arayüzünü başlat
├── run_console.sh                # personel panelini başlat
│
├── config/
│   ├── settings.py               # tüm sabitler tek yerde
│   └── departments.py            # departman + personel dizini
│
├── llm/
│   └── client.py                 # tek LLM giriş noktası (Gemini)
│
├── data_pipeline/
│   ├── scraper_user_guide.py     # 218 sayfa   (User Guide)
│   ├── scraper_dev_guide.py      # 190 sayfa   (Developer Guide) ★ YENİ
│   ├── scraper_website.py        # 185 sayfa   (netmera.com)
│   ├── chunker.py                # başlık-duyarlı Markdown bölme ★ YENİ
│   └── indexer.py                # ChromaDB'ye yaz (source metadata ile)
│
├── tools/                        ★ HER TOOL AYRI DOSYA
│   ├── base.py                   # @netmera_tool decorator + ToolResult
│   ├── registry.py               # tool kaydı ve keşfi
│   ├── rag_search_tool.py        # vektör arama (kaynak filtreli)
│   ├── glossary_tool.py          # Netmera terim sözlüğü
│   ├── sentiment_tool.py         # memnuniyetsizlik tespiti
│   ├── lead_capture_tool.py      # satış lead bilgisi toplama
│   ├── demo_booking_tool.py      # demo talebi kaydı
│   ├── availability_tool.py      # departmanda müsait personel var mı
│   ├── handoff_tool.py           # canlı devir başlat
│   └── ticket_tool.py            # kayıt aç (kimse müsait değilse)
│
├── agents/                       ★ HER AGENT AYRI DOSYA
│   ├── base.py                   # ortak agent davranışı
│   ├── router_agent.py           # niyet + dil tespiti
│   ├── sales_agent.py
│   ├── support_agent.py
│   ├── technical_agent.py
│   ├── general_agent.py
│   └── escalation_agent.py
│
├── graph/
│   ├── state.py                  # LangGraph state şeması
│   ├── nodes.py                  # agent → düğüm sarmalayıcıları
│   └── workflow.py               # graf kurulumu + interrupt + checkpointer
│
├── storage/
│   ├── db.py                     # SQLite şema + bağlantı
│   └── repository.py             # okuma/yazma fonksiyonları
│
├── ui/
│   ├── customer_app.py           # müşteri sohbeti (:8501)
│   └── agent_console.py          # personel paneli (:8502)
│
├── tests/
│   ├── test_tools.py
│   ├── test_router.py
│   └── demo_scenarios.py         # sunum senaryolarını otomatik oynatır
│
├── data/                         # (mevcut, korunuyor)
├── chroma_db/                    # (yeniden inşa edilecek)
└── v1_legacy/                    # eski app.py / scrape.py / ingest.py
```

---

## 4. Teknoloji Kararları

| Katman | Seçim | Gerekçe |
|---|---|---|
| Orkestrasyon | **LangGraph** | State machine, koşullu dallanma, `interrupt()` ile yerleşik human-in-the-loop, SQLite checkpointing |
| LLM | **Gemini** (`langchain-google-genai`) | Ücretsiz kota; multi-agent'ta 1 soru = 3-5 LLM çağrısı, lokal model bunu dakikalara çıkarır |
| Embedding | `paraphrase-multilingual-MiniLM-L12-v2` | **Lokal ve ücretsiz** — TR soru / EN doküman eşleşmesi için çok dilli |
| Vektör DB | ChromaDB | Lokal, kurulum gerektirmez |
| Kalıcı depo | SQLite | İki Streamlit süreci arasında paylaşım için yeterli |
| Arayüz | Streamlit ×2 | Müşteri + personel, aynı DB üzerinden |

**Maliyet:** Embedding ve vektör arama tamamen lokal. Sadece LLM çağrıları Gemini'ye
gidiyor ve ücretsiz kotada kalıyor. Kredi kartı bağlı değil.

---

# FAZLAR

## FAZ 0 — İskelet ve Temel

**Amaç:** Klasör yapısı, bağımlılıklar, config ve LLM istemcisi. Hiç iş mantığı yok.

**Adımlar:**

- **a)** `v1_legacy/` klasörü oluştur; `app.py`, `scrape.py`, `ingest.py` dosyalarını
  oraya taşı (`git mv` ile — geçmiş korunsun). `data/` ve `chroma_db/` yerinde kalsın.
- **b)** Yukarıdaki klasör ağacını boş `__init__.py` dosyalarıyla oluştur.
- **c)** `requirements.txt` güncelle:
  `langgraph`, `langchain-google-genai`, `langgraph-checkpoint-sqlite`,
  `chromadb`, `sentence-transformers`, `streamlit`, `requests`,
  `beautifulsoup4`, `lxml`, `python-dotenv`, `pydantic`
- **d)** `.env.example` yaz (`GEMINI_API_KEY=`, `GEMINI_MODEL=`, `LOG_TOOL_CALLS=true`);
  gerçek `.env` dosyasını mevcut `KEYLER` dosyasındaki key ile oluştur.
  `.gitignore`'a `.env` eklendiğini doğrula.
- **e)** `config/settings.py`: tüm sabitler tek yerde — model adı, `TOP_K=5`,
  `CONFIDENCE_THRESHOLD=0.35`, `MAX_FAILED_ATTEMPTS=2`, yol sabitleri.
- **f)** `config/departments.py`: departman dizini —
  `sales`, `customer_success`, `engineering`; her biri için ad, e-posta, çalışma saati,
  ve demo amaçlı 2'şer sahte personel kaydı.
- **g)** `llm/client.py`: `get_llm(temperature=0.2)` → yapılandırılmış
  `ChatGoogleGenerativeAI` nesnesi döndürür. Tüm proje LLM'e **sadece buradan** erişir.

**Doğrulama:**
```bash
python -c "from llm.client import get_llm; print(get_llm().invoke('Merhaba, tek kelime cevap ver').content)"
```

**Bitti kriteri:** Komut Gemini'den cevap yazdırıyor, hata yok. `.env` git'e girmiyor.

---

## FAZ 1 — Veri Katmanı (en kritik faz)

**Amaç:** 190 eksik Developer Guide sayfasını eklemek ve chunking'i düzeltmek.
Bu faz tamamlanmadan agent'ların cevap kalitesi artmaz.

**Adımlar:**

- **a)** `data_pipeline/scraper_dev_guide.py` yaz:
  `https://user.netmera.com/netmera-developer-guide/llms.txt` adresinden 190 `.md`
  linkini çek, her sayfayı indir, `data/dev_guide/` altına kaydet.
  Kaydedilen dosyanın ilk satırı `URL: <adres>` olsun (mevcut formatla uyumlu).
  İstekler arası 0.3 sn bekleme koy.
- **b)** Mevcut `scrape.py` mantığını ikiye böl: `scraper_user_guide.py` ve
  `scraper_website.py`. Var olan `data/docs/` → `data/user_guide/`,
  `data/site/` → `data/website/` olarak yeniden adlandır (yeniden indirmeye gerek yok).
- **c)** `data_pipeline/chunker.py` yaz — **bu fazın kalbi**:
  - Markdown'ı `#`/`##`/`###` başlıklarına göre böl.
  - Her parçanın başına başlık zincirini ekle
    (örn. `iOS > Push Notifications > Media Push` — retrieval isabetini ciddi artırır).
  - Bir bölüm 1500 karakteri aşarsa paragraf sınırından alt-parçalara ayır,
    150 karakter örtüşme bırak.
  - Kod bloklarını (` ``` `) asla ortadan bölme.
  - 80 karakterden kısa anlamsız parçaları at.
- **d)** `data_pipeline/indexer.py` yaz: tüm `data/*` klasörlerini okur, `chunker` ile
  böler, embed eder, **tek** `netmera` koleksiyonuna yazar. Metadata:
  `{"url", "source", "heading_path", "title"}` — burada `source` ∈
  `user_guide | dev_guide | website`. Bu alan agent'ların kendi alanlarında
  arama yapmasını sağlayacak.
- **e)** Eski `chroma_db/` klasörünü sil ve indeksi sıfırdan kur.

**Doğrulama:**
```bash
python data_pipeline/scraper_dev_guide.py && python data_pipeline/indexer.py
```
```bash
python -c "
import chromadb
c = chromadb.PersistentClient(path='chroma_db').get_collection('netmera')
print('toplam chunk:', c.count())
for s in ['user_guide','dev_guide','website']:
    print(s, c.get(where={'source': s}, limit=1, include=[])['ids'][:1] and 'VAR' or 'YOK')
"
```

**Bitti kriteri:** Toplam chunk sayısı 6000+; üç kaynağın üçü de `VAR`;
`"iOS SDK integration"` sorgusu `dev_guide` kaynaklı sonuç döndürüyor.

---

## FAZ 2 — Tool Katmanı

**Amaç:** Tool altyapısı ve bilgi araçları. Her tool ayrı dosyada, açıkça işaretli.

**Adımlar:**

- **a)** `tools/base.py` — `@netmera_tool` decorator'ı. Görevleri:
  1. Tool'u global registry'ye kaydeder,
  2. Tip ipuçlarından LangChain tool şemasını otomatik üretir,
  3. Her çağrıda terminale görünür log basar:
     `🔧 TOOL → rag_search(query="push nasıl gönderilir", source="user_guide")`
  4. Çağrıyı `state["tool_calls"]` listesine ekler → **arayüzde rozet olarak gösterilecek**.

  > Bu madde senin "tool kullanılıyorsa belirtilsin" isteğinin karşılığı: hem terminalde
  > hem müşteri ekranında hangi tool'un çalıştığı görünür olacak.

- **b)** `tools/base.py` içine `ToolResult` modeli (pydantic): `ok`, `data`,
  `summary`, `sources`. Bütün tool'lar bunu döndürür — tek tip sonuç sözleşmesi.
- **c)** `tools/registry.py` — `get_tools_for(department)` ile bir agent'a hangi
  tool'ların verileceğini döndürür.
- **d)** `tools/rag_search_tool.py` — **en önemli tool**:
  - Parametreler: `query`, `source` (`user_guide|dev_guide|website|all`), `top_k`.
  - Chroma'dan mesafe döner; `similarity = 1 - distance` olarak güven skoru hesapla.
  - `ToolResult.data` içinde parçalar + `heading_path` + `url`,
    `ToolResult.summary` içinde en yüksek benzerlik skoru bulunsun.
- **e)** `tools/glossary_tool.py` — `data/website/glossary_*` sayfalarından terim
  araması (37 terim var: churn rate, LTV, deep linking...). Genel/pazarlama
  sorularında RAG'dan daha keskin cevap verir.
- **f)** `tools/sentiment_tool.py` — LLM ile tek çağrı:
  `neutral | confused | frustrated`. `frustrated` → devir tetikleyici #4.

**Doğrulama:**
```bash
python -c "
from tools.rag_search_tool import rag_search
r = rag_search.invoke({'query':'iOS SDK nasil entegre edilir','source':'dev_guide','top_k':3})
print(r)
"
```

**Bitti kriteri:** Terminalde `🔧 TOOL →` logu görünüyor; sonuçlar `dev_guide`
kaynaklı ve benzerlik skoru 0.35 üzerinde.

---

## FAZ 3 — Agent Katmanı

**Amaç:** Beş uzman agent + router. Her biri ayrı dosya, ayrı sistem promptu, ayrı tool seti.

**Adımlar:**

- **a)** `agents/base.py` — ortak `BaseAgent` sınıfı:
  `name`, `department`, `system_prompt`, `tools`, `search_source` alanları ve
  `run(state) -> dict` metodu. Her agent cevabını **yapılandırılmış** döndürür:
  `{answer, can_answer: bool, confidence: float, sources: list, needs_human: bool}`.
  `can_answer=false` → devir tetikleyici #2.
- **b)** `agents/router_agent.py` — tool kullanmaz, tek LLM çağrısıyla döner:
  `intent` (`sales|support|technical|general|handoff_request`), `language` (`tr|en`),
  `department`, `urgency`. Az-örnekli (few-shot) örneklerle kararlılığını artır.
- **c)** `agents/general_agent.py` — "Netmera nedir", "hangi sektörler", "neden Netmera".
  Kaynak: `website` + `glossary_tool`. **Devir yok** — bu sorular her zaman cevaplanır.
- **d)** `agents/support_agent.py` — panel kullanımı, "nasıl yapılır".
  Kaynak: `user_guide`. Cevaplarında adım adım talimat ve kaynak linki ver.
- **e)** `agents/technical_agent.py` — SDK, API, entegrasyon, hata ayıklama.
  Kaynak: `dev_guide` (+ gerekirse `user_guide`). Kod bloklarını koruyarak cevapla.
- **f)** `agents/sales_agent.py` — fiyat, paket, demo, satın alma.
  Tool'lar: `rag_search(website)`, `lead_capture_tool`, `demo_booking_tool`.
  **Özel kural:** Netmera fiyat listesini public yayınlamıyor → agent fiyat sorusunda
  uydurmaz, lead bilgisi toplayıp satışa yönlendirir.
- **g)** `agents/escalation_agent.py` — cevap üretmez, **devri yönetir**:
  sohbeti özetler, departmanı belirler, aciliyet atar, `availability_tool` ile
  müsait personel arar, `handoff_tool` veya `ticket_tool` çağırır.

**Doğrulama:**
```bash
python -c "
from agents.router_agent import RouterAgent
r = RouterAgent()
for q in ['Netmera kac para, satin almak istiyorum',
          'Android SDK push token alamiyorum',
          'Segment olusturamiyorum yardim edin',
          'Bir yetkiliyle gorusmek istiyorum']:
    print(q, '->', r.classify(q))
"
```

**Bitti kriteri:** Dört soru sırasıyla `sales`, `technical`, `support`,
`handoff_request` olarak sınıflanıyor.

---

## FAZ 4 — Kalıcı Katman (SQLite)

**Amaç:** Müşteri arayüzü ile personel panelinin konuşabileceği ortak zemin.

**Adımlar:**

- **a)** `storage/db.py` — şema:

  | Tablo | Alanlar |
  |---|---|
  | `sessions` | id, created_at, language, status(`bot`/`waiting_human`/`with_human`/`closed`) |
  | `messages` | id, session_id, role(`user`/`assistant`/`human_agent`), content, agent_name, created_at |
  | `handoffs` | id, session_id, department, reason, summary, urgency, status(`pending`/`claimed`/`closed`), assigned_to, created_at, claimed_at |
  | `staff` | id, name, department, is_online |
  | `tool_logs` | id, session_id, tool_name, args_json, summary, created_at |

- **b)** `storage/repository.py` — fonksiyonlar: `create_session`, `add_message`,
  `get_messages`, `create_handoff`, `list_pending_handoffs`, `claim_handoff`,
  `post_human_reply`, `close_handoff`, `log_tool_call`, `set_staff_online`.
- **c)** Tablolar yoksa otomatik oluşturan başlatma; `config/departments.py`
  içindeki sahte personeli `staff` tablosuna ekleyen seed fonksiyonu.
- **d)** Streamlit iki süreçten yazacağı için SQLite'ı WAL moduna al
  (`PRAGMA journal_mode=WAL`) — kilitlenme yaşanmasın.

**Doğrulama:**
```bash
python -c "
from storage import repository as r
r.init_db(); s = r.create_session('tr')
r.add_message(s,'user','test'); h = r.create_handoff(s,'sales','test','ozet','normal')
print('bekleyen devirler:', r.list_pending_handoffs())
"
```

**Bitti kriteri:** `helpdesk.db` oluştu, devir kaydı listede görünüyor.

---

## FAZ 5 — LangGraph Orkestrasyonu

**Amaç:** Tüm parçaları tek bir akışa bağlamak.

**Adımlar:**

- **a)** `graph/state.py` — `HelpdeskState` (TypedDict):
  ```
  messages          (add_messages ile birikimli)
  session_id, language, intent, department
  retrieved, confidence, tool_calls
  escalate, escalation_reason, failed_attempts
  handoff_id, lead
  ```
- **b)** `graph/nodes.py` — her agent'ı bir düğüm fonksiyonuna sar
  (`router_node`, `sales_node`, `support_node`, `technical_node`, `general_node`,
  `escalation_node`, `human_wait_node`).
- **c)** `graph/workflow.py` — grafı kur:
  - `START → router_node`
  - `router_node` sonrası **koşullu dallanma**: intent'e göre uzman düğüme;
    `intent == handoff_request` ise doğrudan `escalation_node`.
  - Uzman düğümlerden sonra **ikinci koşullu dallanma** (`should_escalate`):
    Bölüm 2'deki 5 tetikleyiciden biri doğruysa `escalation_node`, değilse `END`.
  - `escalation_node → human_wait_node`
- **d)** `human_wait_node` içinde `interrupt()` çağır — graf tam bu noktada donar,
  state SQLite checkpointer'a yazılır. Personel cevap yazınca
  `Command(resume=<insan_cevabi>)` ile kaldığı yerden devam eder.
- **e)** Checkpointer olarak `SqliteSaver` kullan, `thread_id = session_id`.
- **f)** `failed_attempts` sayacını düğümlerde doğru artır/sıfırla
  (başarılı cevap → sıfırla).

**Doğrulama:**
```bash
python -c "
from graph.workflow import build_graph
g = build_graph()
print(g.get_graph().draw_ascii())
"
```

**Bitti kriteri:** ASCII graf çiziliyor ve tüm düğümler/dallar beklendiği gibi bağlı.

---

## FAZ 6 — İnsana Devir Araçları

**Amaç:** Devir mekanizmasının çalışan parçaları.

**Adımlar:**

- **a)** `tools/availability_tool.py` — departmanda `is_online=1` personel var mı?
  Varsa listesini döndür.
- **b)** `tools/handoff_tool.py` — `handoffs` tablosuna `pending` kayıt açar,
  oturumun durumunu `waiting_human` yapar, müşteriye gösterilecek bilgilendirme
  metnini döndürür ("Sizi Satış ekibimize aktarıyorum, birazdan bağlanacaklar").
- **c)** `tools/ticket_tool.py` — kimse müsait değilse asenkron kayıt açar,
  `TICKET-0042` formatında numara üretir ve tahmini dönüş süresi bildirir.
- **d)** `tools/lead_capture_tool.py` — satış senaryosunda ad, şirket, e-posta,
  uygulama türü, tahmini kullanıcı sayısı toplar; eksikleri agent'ın sorması için
  `missing_fields` döndürür.
- **e)** `tools/demo_booking_tool.py` — demo talebi kaydı (tarih tercihi + iletişim).
- **f)** `escalation_agent`'ı bu tool'larla bağla: **önce** `availability_tool`,
  müsait varsa `handoff_tool`, yoksa `ticket_tool`.

**Doğrulama:**
```bash
python tests/test_tools.py
```

**Bitti kriteri:** Müsait personel varken devir kaydı, yokken ticket açılıyor.

---

## FAZ 7 — Arayüzler

**Amaç:** Sunumda göstereceğin iki ekran.

**Adımlar:**

- **a)** `ui/customer_app.py` (:8501) — müşteri sohbeti:
  - Sohbet geçmişi + akıtmalı (streaming) cevap.
  - **Her cevabın üstünde hangi agent'ın cevapladığı rozeti:**
    `🤖 Teknik Destek Agent`, `💼 Satış Agent`...
  - **Kullanılan tool'lar rozeti:** `🔧 rag_search (dev_guide) · 🔧 sentiment`
    — açılır panelde parametreler ve dönen kaynaklar.
  - Kaynak linkleri (`heading_path` + URL) her cevabın altında.
  - Devir olduğunda: `⏳ Satış temsilcisine aktarılıyorsunuz...` durumu ve
    2 saniyede bir DB'yi yoklayan otomatik yenileme; insan yazınca mesaj
    `👤 Ayşe (Satış)` etiketiyle sohbete düşer.
- **b)** `ui/agent_console.py` (:8502) — personel paneli:
  - Kenar çubuğunda departman seçimi + `Çevrimiçi ol` anahtarı.
  - Bekleyen devir kuyruğu: aciliyet, konu özeti, bekleme süresi.
  - `Devral` düğmesi → sohbetin tamamı ve bot'un ne denediği görünür.
  - Yanıt kutusu → mesaj müşteriye gider, LangGraph `Command(resume=...)` ile devam eder.
  - `Kapat` düğmesi → oturum bot'a geri döner veya kapanır.
- **c)** `run_customer.sh` ve `run_console.sh` — tek komutla başlatma.
- **d)** İki pencereyi yan yana açtığında gecikmenin fark edilmemesi için
  yoklama aralığını ayarla (`st.rerun` + 2 sn).

**Doğrulama:**
```bash
./run_customer.sh
```
```bash
./run_console.sh
```

**Bitti kriteri:** İki tarayıcı penceresi yan yana; müşteri "satış temsilcisiyle
görüşmek istiyorum" yazınca talep konsolda beliriyor, personel cevap yazınca
müşteri ekranına düşüyor.

---

## FAZ 8 — Test, Demo Senaryoları ve Sunum

**Amaç:** Salı sunumuna hazır hale getirmek.

**Adımlar:**

- **a)** `tests/demo_scenarios.py` — aşağıdaki 6 senaryoyu otomatik oynatır,
  hangi agent'ın devreye girdiğini ve hangi tool'ların çalıştığını yazdırır.
- **b)** Router doğruluk testi: her kategoriden 5'er soru, doğru sınıflama oranı.
- **c)** `README.md` — mimari şeması, kurulum, çalıştırma, senaryolar.
- **d)** Sunum akışı notu: hangi soruyu hangi sırayla soracağın (aşağıdaki tablo).
- **e)** Bilinen sınırlar bölümü — dürüstlük puan kazandırır
  (fiyat bilgisi public değil, ücretsiz kota limitleri, sahte personel dizini).

### Demo senaryoları

| # | Senaryo | Girdi | Beklenen akış |
|---|---|---|---|
| 1 | Genel bilgi | "Netmera nedir, ne işe yarar?" | `general` → `rag_search(website)` → cevap, devir yok |
| 2 | Panel kullanımı | "Kural bazlı segment nasıl oluşturulur?" | `support` → `rag_search(user_guide)` → adım adım cevap + kaynak |
| 3 | Teknik (yeni yetenek) | "iOS'ta push izni nasıl isteniyor?" | `technical` → `rag_search(dev_guide)` → kod bloklu cevap ★ v1'de cevaplanamıyordu |
| 4 | **Satış → insana devir** | "Netmera almak istiyorum, bir satış temsilcisiyle görüşebilir miyim?" | `router: handoff_request` → `escalation` → `availability` → `handoff` → konsolda beliriyor |
| 5 | **Destek → çözemedi → devir** | "Push bildirimlerim 3 gündür gitmiyor, hesabımda bir sorun var" | `support` → RAG düşük güven → `escalation` → teknik departman |
| 6 | Kapsam dışı | "Bugün hava nasıl?" | `general` → nazikçe kapsam dışı, uydurmuyor |

**Doğrulama:**
```bash
python tests/demo_scenarios.py
```

**Bitti kriteri:** 6 senaryonun 6'sı beklenen agent ve tool zincirini üretiyor.

---

## 5. Zaman Tahmini

| Faz | İçerik | Süre |
|---|---|---|
| 0 | İskelet | 20 dk |
| 1 | **Veri katmanı** (scrape + indeks dahil) | 60 dk |
| 2 | Tool katmanı | 45 dk |
| 3 | Agent katmanı | 60 dk |
| 4 | SQLite | 30 dk |
| 5 | LangGraph | 60 dk |
| 6 | Devir araçları | 40 dk |
| 7 | Arayüzler | 60 dk |
| 8 | Test + sunum | 40 dk |
| | **Toplam** | **~6.5 saat** |

Fazlar bağımsız durabilir — bir oturumda 2-3 faz bitirip ara verebilirsin.
FAZ 1'in scrape adımı ~5 dakika arka planda çalışır.

---

## 6. Risk Notları

| Risk | Önlem |
|---|---|
| Gemini ücretsiz kota limiti (dakikada istek) | `router` için düşük `temperature` + kısa prompt; gerekirse tool çağrılarını sadeleştir |
| LangGraph `interrupt()` + Streamlit yeniden çalıştırma çakışması | Graf state'i SQLite checkpointer'da; Streamlit sadece DB'yi yokluyor, graf state'ini bellekte tutmuyor |
| İki Streamlit süreci SQLite kilidi | WAL modu (FAZ 4-d) |
| Developer Guide sayfalarında `.md` linki değişirse | `llms.txt` her seferinde yeniden okunuyor, sabit liste tutulmuyor |
| Sunumda internet yok | `chroma_db/` ve `data/` lokalde hazır; sadece LLM çağrısı internet ister — yedek olarak Ollama sağlayıcısı eklenebilir |

---

## 7. Başlangıç Komutu

```bash
cd "/Users/emir/NETMERA 27 JULY" && source venv/bin/activate
```

Sonra Claude'a:

```
PLAN_MULTI_AGENT.md dosyasindaki FAZ 0 bolumunu oku ve adim adim uygula.
```
