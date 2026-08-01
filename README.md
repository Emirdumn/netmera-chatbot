# 💬 Netmera Multi-Agent Yardım Masası (v3 — Orkestratör)

LangGraph tabanlı çok-agent RAG helpdesk'i: **çalışan bellek**, **bağlam
farkındalıklı orkestratör** (yapışkan yönlendirme + clarify), **slot bazlı
akışlar**, **ReAct arama döngüsü**, **hibrit retrieval** (BM25+vektör+rerank)
ve iki ayrı Streamlit arayüzü (müşteri sohbeti + personel paneli).

İki faz planı sırayla uygulandı:
- [`PLAN_MULTI_AGENT.md`](PLAN_MULTI_AGENT.md) (FAZ 0-8) — temel çok-agent iskelet
- [`PLAN_ORCHESTRATOR.md`](PLAN_ORCHESTRATOR.md) (FAZ 9-14) — bellek + orkestratör + ReAct + retrieval kalitesi + arayüz

## Mimari

```
Müşteri ──► customer_app (Streamlit :8501)
                 │
                 ▼
         LangGraph workflow.py
                 │
        ┌────────▼─────────┐
        │  📝 MEMORY NODE  │  her turda calisir — customer_profile/case_notes
        └────────┬─────────┘  guncellenir (bilgi hic silinmez), session_notes'a yazilir
                 │
        ┌────────▼──────────┐
        │  🧠 ORKESTRATÖR   │  son 6 mesaj + profil + aktif agent + bekleyen soru
        │                   │  → continue | switch | escalate | clarify
        └────────┬──────────┘  (yapışkanlık kuralı kod seviyesinde zorunlu)
     ┌─────┬─────┼─────┬──────────┬─────────┐
     ▼     ▼     ▼     ▼          ▼         ▼
  GENERAL SALES SUPPORT TECHNICAL CLARIFY ESCALATION
     │     │     │     │                     │
     │     └──┬──┴─────┘                     │
     │        ▼                              │
     │  🎯 SLOT/FLOW (flows/)                │
     │  eksik alan varsa en fazla 2'sini sor  │
     │  (profildeki bilgi tekrar sorulmaz)    │
     │        │                              │
     └────┬───┴──────────────────────┐       │
          ▼                          │       │
   🔄 ReAct arama döngüsü            │       │
   query_builder_tool → hibrit       │       │
   rag_search (BM25+vektör+rerank)   │       │
   yetersizse sorguyu yenile (×4)    │       │
          │                          │       │
   güven < 0.35 / can_answer=false / │       │
   sinirli musteri / 2 basarisiz  ───┴───────►│
                                              ▼
                                    availability_tool
                                    ┌─────┴─────┐
                                    ▼           ▼
                                handoff_tool  ticket_tool
                                    │
                              interrupt() — graf donar
                                    │  SQLite (storage/)
                          ┌─────────▼─────────┐
            Personel ───► │  agent_console    │ (:8502)
                          │  (Command(resume=...))
                          └───────────────────┘
```

### Önce / Sonra (PLAN_ORCHESTRATOR.md'nin kendi bug raporu)

```
FAZ 9-11 ÖNCESİ (bellek + orkestratör yok):
1  "Fiyatlandırma hakkında bilgi almak istiyorum"
   💼 Satış: "adınızı, şirketinizi, e-postanızı... paylaşır mısınız?"     ✅
2  "Emir Duman / Vmind / Kahve sipariş uygulaması / 1000 kullanıcı"
   🌐 Genel: "Emir Duman ve Vmind hakkında bilgi bulunmamaktadır"        ❌ ÇÖKÜŞ
3  "Anlamadım benden ne istedin"
   🔁 Devir: TICKET-0001                                                 ❌ gereksiz devir

FAZ 9-11 SONRASI (bu repo, tests/demo_scenarios.py ile regresyon testli):
1  💼 Satış: "Öncelikle adınızı ve şirketinizi alabilir miyim?"          (5 değil 2 slot)
2  🧠 Orkestra: is_answer_to_pending_question=TRUE → sales'te KAL         ★ DÜZELDİ
   💼 Satış: "E-posta adresinizi alabilir miyim?" (kalan tek eksik slot)
3  🧠 Orkestra: action=clarify → sales, devir AÇILMAZ                    ★ DÜZELDİ
   💼 Satış: "Özür dilerim, daha net sorayım: e-posta adresiniz?"
4  "iOS SDK entegrasyonu nasıl yapılır" → 🧠 switch → 👨‍💻 Teknik           (konu degisimi de dogru)
```

## Bileşenler

- **Orkestrasyon:** LangGraph (`graph/`) — `SqliteSaver` checkpointer, `interrupt()`
  ile human-in-the-loop. Graf: `memory_node → orchestrator_node → {general,
  sales, support, technical, clarify, escalation}_node → (gerekirse) → human_wait_node`.
- **Çalışan bellek (FAZ 9):** `agents/memory_agent.py` her turda `customer_profile`
  + `case_notes` çıkarır; `graph/state.py:merge_dict` reducer'ı bilgiyi hiç
  silmeden birleştirir. `storage/session_notes` tablosuna her turda yazılır.
- **Orkestratör (FAZ 10):** `agents/orchestrator.py` — router'ın yerini aldı
  (eski dosya karşılaştırma için `v2_legacy/router_agent.py`'de duruyor).
  Yapışkanlık kuralı (`is_answer_to_pending_question` → aynı agent'ta kal)
  ve `clarify` aksiyonu (gereksiz devri önler) kod seviyesinde zorunlu.
- **Slot/akış yönetimi (FAZ 11):** `flows/` — `sales_lead`, `technical_case`,
  `support_case`. Profildeki bilgi tekrar sorulmaz, aynı anda en fazla 2
  eksik slot sorulur.
- **ReAct döngüsü (FAZ 12):** `agents/base.py:answer()` artık tek seferlik
  değil — `tools/query_builder_tool.py` konuşma+profili bağımsız, İngilizce
  bir sorguya çevirir; sonuç zayıfsa sorgu yeniden yazılıp en fazla
  `MAX_TOOL_ITERATIONS` (4) tur denenir. `reasoning_trace` arayüzde gösterilir.
- **Hibrit retrieval (FAZ 13):** `tools/rag_search_tool.py` — BM25 (anahtar
  kelime) + vektör aramasını RRF ile birleştirir, cross-encoder
  (`ms-marco-MiniLM-L-6-v2`) ile yeniden sıralar, `heading_boost` uygular.
  `similarity` alanı her zaman gerçek kosinüs benzerliğidir (BM25-only
  bulunan sonuçlar için bile ayrıca hesaplanır) — sistemin geri kalanındaki
  `CONFIDENCE_THRESHOLD` mantığı bozulmaz.
- **Tool'lar:** `tools/` — `rag_search`, `query_builder_tool`, `glossary_search`,
  `detect_sentiment`, `availability_tool`, `handoff_tool`, `ticket_tool`,
  `lead_capture_tool`, `demo_booking_tool`. Her çağrı terminale
  `🔧 TOOL → ...` olarak loglanır.
- **Veri:** ChromaDB + `paraphrase-multilingual-MiniLM-L12-v2` (lokal, ücretsiz
  embedding), ~6245 chunk / 3 kaynak (`user_guide`, `dev_guide`, `website`).
- **Kalıcı depo:** SQLite (`storage/helpdesk.db`) — oturumlar, mesajlar
  (tool/kaynak/orkestratör/akış meta verisiyle), devirler, personel,
  müşteri notları; iki Streamlit süreci arasında WAL modunda paylaşılır.
- **LLM:** `llm/client.py` tek giriş noktası. `.env`'deki `LLM_PROVIDER` ile
  Gemini veya OpenRouter (OpenAI-uyumlu) arasında seçim yapılır. Çağrılar
  `tier=control|worker|brain` ile ayrılır; model isimleri
  `LLM_CONTROL_MODEL` / `LLM_WORKER_MODEL` / `LLM_BRAIN_MODEL` (boşsa
  provider varsayılanı). Her çağrı `🧠 LLM_CALL tier=… model=… call_site=…
  latency_ms=…` olarak loglanır.

## Kurulum

```bash
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # sonra .env'i doldur
```

`.env` içinde:

```bash
LLM_PROVIDER=openrouter          # veya: gemini
OPENROUTER_API_KEY=sk-or-...
OPENROUTER_MODEL=openai/gpt-4o-mini
GEMINI_API_KEY=...               # LLM_PROVIDER=gemini ise gerekli
GEMINI_MODEL=gemini-3.6-flash
LOG_TOOL_CALLS=true
STAFF_DEMO_PASSWORD=...          # personel paneli ic girisi; güçlü ve benzersiz olmalı
```

`STAFF_DEMO_PASSWORD` için varsayılan yoktur. Boş bırakılırsa ya da zayıf/placeholder
bir değer verilirse uygulama başlangıçta durur. Güçlü bir değer üretmek için:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

> **Neden OpenRouter varsayılan?** Gemini ücretsiz tier'da `gemini-3.6-flash`
> için günlük 20 istek limiti var; multi-agent akışta bir soru 5-10+ LLM
> çağrısı yapar (memory + orchestrator + query_builder + answer + sentiment)
> ve bu limit dakikalar içinde tükenir. `LLM_PROVIDER=gemini` yaparak
> istediğiniz an Gemini'ye dönebilirsiniz, kod değişikliği gerekmez.

## Çalıştırma

```bash
./run_customer.sh   # müşteri sohbeti — http://localhost:8501
./run_console.sh    # personel paneli — http://localhost:8502
```

İlk çalıştırmada `storage/helpdesk.db` otomatik oluşturulur ve
`config/departments.py`'deki sahte personel `staff` tablosuna eklenir.
Müşteri ekranının kenar çubuğunda konuşma ilerledikçe **📋 Müşteri Notu**
canlı dolar; her cevabın altında **🧠 Orkestratör Kararı** (neden bu agent'a
yönlendirdiği) ve varsa **🔄 Akış Durumu** (kaç slottan kaçı dolu) görünür.

## Veri hattı (yeniden indekslemek için)

```bash
python -m data_pipeline.scraper_user_guide   # 218 sayfa
python -m data_pipeline.scraper_dev_guide    # 190 sayfa
python -m data_pipeline.scraper_website      # 185 sayfa
python -m data_pipeline.indexer              # hepsini chroma_db/'ye yazar
```

`data_pipeline/chunker.py` Markdown'ı `#`/`##`/`###` başlıklarına göre böler,
her parçanın başına başlık zincirini (`iOS > Push Notifications > ...`) ekler
ve kod bloklarını asla ortadan bölmez.

## Test ve demo senaryoları

```bash
python tests/test_tools.py            # devir araçları: müsait personel varken handoff, yokken ticket
python tests/test_router.py           # eski router'ın (v2_legacy) sınıflandırma doğruluğu
python tests/test_orchestrator.py     # yapışkanlık + clarify — orkestratörün asıl var oluş nedeni
python tests/test_flows.py            # slot yönetimi: bilinen alan tekrar sorulmuyor, akış tamamlanıyor
python tests/test_react_loop.py       # bağlama bağlı takip sorusu doğru sorguya çevriliyor mu
python tests/retrieval_benchmark.py   # 30 soru, isabet@5 ve ortalama benzerlik
python tests/demo_scenarios.py        # 6 uçtan uca senaryo + FAZ 14 regresyon testi (asıl bug senaryosu)
```

Personel paneli iç giriş şifresini değiştirdikten sonra mevcut SQLite staff hash'lerini
yenilemek için:

```bash
python scripts/rotate_staff_passwords.py
```

### Demo senaryoları ve sunum akışı

Sunumda sırayla şu soruları sormak akışı en iyi gösterir:

| # | Soru | Beklenen akış |
|---|---|---|
| 1 | "Netmera nedir, ne işe yarar?" | `general` → `rag_search(website)` → cevap, devir yok |
| 2 | "Kural bazlı segment nasıl oluşturulur?" | `support` → `rag_search(user_guide)` → adım adım cevap + kaynak |
| 3 | "iOS'ta push izni nasıl isteniyor?" | `technical` → `rag_search(dev_guide)` → kod bloklu cevap (v1'de cevaplanamıyordu) |
| 4 | "Netmera almak istiyorum, bir satış temsilcisiyle görüşebilir miyim?" | `escalate` → `availability` → `handoff` → **personel konsolunda beliriyor** |
| 5 | "Push bildirimlerim 3 gündür gitmiyor, hesabımda bir sorun var" | `support` → düşük güven → `escalation` |
| 6 | "Bugün hava nasıl?" | `general` → nazikçe kapsam dışı, uydurmuyor |
| 7★ | Sonra: "Fiyatlandırma..." → isim/şirket/e-posta ver → "anlamadım" | **📋 panelde profil canlı doluyor**, devir açılmadan lead tamamlanıyor |

Senaryo 4'ten sonra `agent_console`'da (:8502) departmanı seçip **Devral** →
(devir kartında müşterinin o ana kadar verdiği tüm bilgiler hazır) → yanıt
yaz → **Gönder** — cevap müşteri ekranına (:8501) 2 saniye içinde düşer.
**Kapat** ile oturum bot'a geri döner.

## Bilinen sınırlar

- **Fiyat bilgisi public değil:** `sales_agent` fiyat sorularında asla rakam
  uydurmaz; bunun yerine lead bilgisi (ad/şirket/e-posta/kullanıcı sayısı) ister.
- **Orkestratör/router LLM tabanlı sınıflandırma yapar:** sınırda kalan
  sorularda (ör. "iOS'ta push izni nasıl isteniyor" hem panel hem SDK
  bağlamında okunabilir) çalıştırmalar arası küçük varyasyon görülebilir —
  `tests/test_router.py` %90+ doğruluk gösterir, %100 garanti edilmez. Çok
  tetikleyicili devir mekanizması (düşük güven, `can_answer=false`, sinirli
  müşteri, 2 başarısız deneme) bu varyansı büyük ölçüde tolere eder.
- **`memory_agent` alanları asla silinmez (by design):** eski bir "vaka"
  bilgisi (ör. `case_notes.problem_summary`) konu değiştiğinde bile teoride
  sızabilir; `technical_agent`/`support_agent` bunu `orchestrator_action ==
  "switch"` kontrolüyle büyük ölçüde önler, ama %100 garanti değildir.
- **Hibrit retrieval'in ortalama benzerlik metriği:** `retrieval_benchmark.py`
  isabet@5'te (%87) hedefi (%85+) tutturuyor, ancak "ortalama en-iyi
  benzerlik" 0.63 civarında — hedeflenen 0.70'in altında. Rerank bazen
  kosinüs benzerliği düşük ama anahtar-kelime (BM25) eşleşmesi güçlü bir
  parçayı öne çıkarıyor (bu, tam da tasarlandığı şey — `Netmera-Config.plist`
  gibi tam-eşleşme gerektiren sorgularda ölçülebilir şekilde daha isabetli),
  ama bu genel 30-soruluk test setinde ortalamayı hafif düşürüyor.
- **Ücretsiz LLM kotaları:** Gemini free tier günlük 20 istekle sınırlı;
  OpenRouter'da seçtiğiniz modelin kendi kota/ücretlendirmesi geçerlidir.
- **Sahte personel dizini:** `config/departments.py`'deki personel ve
  çevrimiçi durumları demo amaçlıdır, gerçek bir kimlik doğrulama yoktur.
- **`checkpoints.db` / `helpdesk.db`:** WAL modunda, iki Streamlit süreci
  arasında paylaşılır; gerçek üretim ortamında ayrı bir DB sunucusu gerekir.

## Eski sürümler

- `v1_legacy/` — orijinal tek-agent RAG (`app.py`, `scrape.py`, `ingest.py`).
- `v2_legacy/router_agent.py` — FAZ 10 öncesi, bağlamsız (sadece son mesaja
  bakan) router; orkestratörle karşılaştırma için korunuyor.
