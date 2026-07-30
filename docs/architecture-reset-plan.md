# Netmera Helpdesk — Mimari Toparlama Planı

**Tarih:** 2026-07-30  
**Durum:** Canlı sistemi bozmadan revizyon planı. Kod değişikliği değil, karar zemini.

## Kısa teşhis

Proje canlıda çalışıyor; problem artık "ayağa kalkıyor mu?" değil, mimarinin ürün gibi
hissetmesi ve sürdürülebilir kalması. Mevcut sistem demo için güçlü: LangGraph,
memory, orkestratör, RAG, Streamlit müşteri paneli ve personel paneli aynı çekirdeği
hızlıca gösteriyor. Ancak canlıya geçince şu sınırlar rahatsız ediyor:

- Streamlit UI, graph çalıştırma mantığı, session polling ve SQLite persistence birbirine
  çok yakın duruyor.
- `customer_app.py` ve `agent_console.py` uygulama katmanı gibi değil, hem controller
  hem renderer hem state coordinator gibi davranıyor.
- `is_waiting` / session-status ve interrupt drain sıralaması iki UI'da tekrar ediyor;
  contact form ile human-wait geçişleri gibi incelikli davranışlar UI dosyasında kalınca
  canlıda küçük sıralama bug'ları doğuruyor.
- LangGraph state'i ile `storage/repository.py` verisi çift kaynak gibi çalışıyor:
  mesajlar hem graph state'inde hem SQLite'ta anlam taşıyor.
- Personel paneli ve müşteri paneli iki ayrı process; SQLite/WAL ile idare ediliyor.
  Bu demo için yeterli, ama production hissi için kırılgan.
- Agent kararları ve flow slotları çalışıyor, fakat business intent, case lifecycle ve
  handoff lifecycle açık bir domain modeli olarak ayrılmamış.
- `docs/support-widget-plan.md` doğru bir ihtiyacı yakalıyor: dış sitelere gömülebilen
  widget için HTTP API gerekir. Ama bu, mevcut canlı sistemi düzeltmekten ayrı bir iş.

## Mevcut iyi parçalar

Şu parçalar korunmalı:

- `agents/` içindeki uzmanlaşma: general, sales, support, technical, escalation.
- `graph/` içindeki LangGraph orkestrasyonu ve interrupt temelli human handoff.
- `tools/rag_search_tool.py` içindeki hibrit retrieval yaklaşımı.
- `flows/` slot modeli; özellikle lead/support/technical case için ayrı akışlar.
- `storage/repository.py` tek veri erişim kapısı fikri.
- Docker Compose ile müşteri, personel, Redis ve nginx ayrımı.

## Ana karar

Bu projede iki ayrı hedef var ve karıştırılmamalı:

1. **Canlı helpdesk'i toparlamak:** Mevcut müşteri paneli ve personel paneli daha
   güvenilir, okunabilir, yönetilebilir hale gelsin.
2. **Embed widget eklemek:** Netmera veya müşteri sitelerine gömülebilecek React/Vite
   widget + FastAPI adapter eklensin.

Önce 1. hedef yapılmalı. Çünkü widget API yazıldığında mevcut çekirdeğe bağlanacak;
çekirdek bulanıksa yeni widget sadece bu bulanıklığı çoğaltır.

## Hedef mimari

```
ui/customer_app.py       ui/agent_console.py       widget_api/* (ileride)
        │                       │                         │
        └───────────────┬───────┴───────────────┬─────────┘
                        ▼                       ▼
              app_services/chat_service.py   app_services/handoff_service.py
                        │                       │
                        └───────────┬───────────┘
                                    ▼
                             graph/workflow.py
                                    │
             ┌──────────────────────┼──────────────────────┐
             ▼                      ▼                      ▼
          agents/                 flows/                 tools/
                                    │
                                    ▼
                           storage/repository.py
```

Bu yapıda UI dosyaları yalnızca form/render/polling işini bilir. Graph invoke, interrupt
drain, mesaj persist etme, handoff claim/close gibi davranışlar servis katmanına taşınır.

## Önerilen fazlar

### Faz 1 — Çekirdeği servis katmanına al

Yeni dosyalar:

- `app_services/__init__.py`
- `app_services/chat_service.py`
- `app_services/handoff_service.py`
- `app_services/schemas.py`

Taşınacak davranışlar:

- Müşteri mesajı ekle → graph invoke → assistant mesajını persist et.
- Interrupt varsa escalation mesajını doğru agent adıyla kaydet.
- Contact form resume ve "bot ile devam et" drain işlemleri.
- Personel reply gönderirken graph interrupt varsa resume etme.
- Handoff claim/close çevrimleri.

Beklenen sonuç: `ui/customer_app.py` ve `ui/agent_console.py` incelir; ileride FastAPI
aynı servisleri kullanır, Streamlit kodu kopyalanmaz.

### Faz 2 — Runtime ve güvenlik borçlarını kapat

- `nginx` tarafında production için HTTPS/domain planını netleştir.
- Personel panelindeki paylaşımlı demo şifre modelini gerçek deployment için ayır:
  en azından env üzerinden zorunlu güçlü parola, mümkünse personel bazlı secret.
- LLM maliyeti için rate limit/kota ekle. Özellikle ileride widget açılırsa şart.
- `.env`, `.htpasswd`, API key ve canlı giriş bilgilerinin repo/doküman/screenshot içinde
  dolaşmasını engelleyen küçük bir checklist ekle.
- Healthcheck sadece Streamlit health değil, graph/DB/Chroma hazır mı sinyali de verebilsin.

### Faz 3 — Veri modelini netleştir

Minimum migration önerisi:

- `sessions.channel`: `streamlit_customer`, `widget`, `internal_demo` gibi kaynak ayrımı.
- `handoffs.channel`: personelin talebin nereden geldiğini görmesi için.
- `handoffs.updated_at`: claimed/closed sıralaması ve panel yenileme için.
- `messages.metadata_json`: orchestrator/tool/flow alanları büyüdükçe kolon patlamasını önler.

Bu faz şart değil, ama canlı ürün hissi için iyi olur.

### Faz 4 — Widget işine sonra gir

`docs/support-widget-plan.md` içindeki React + FastAPI planı ancak Faz 1 sonrası uygulanmalı.
O zaman `widget_api` doğrudan `app_services/chat_service.py` kullanır. Böylece:

- Streamlit'teki graph invoke mantığı kopyalanmaz.
- Widget, müşteri paneli ve personel paneli aynı case lifecycle'ı paylaşır.
- Testlerde graph yerine servis mock'lanabilir.

## İlk uygulanacak iş

En düşük riskli ilk PR:

1. `app_services/chat_service.py` oluştur.
2. `ui/customer_app.py` içindeki graph invoke + DB persist bloklarını servise taşı.
3. Mevcut davranışı değiştirmeden test ekle:
   - normal bot cevabı kaydediliyor,
   - escalation interrupt cevabı kaydediliyor,
   - contact form resume boş profil yazmıyor,
   - bot ile devam et session durumunu geri alıyor.

Bu PR canlı davranışı değiştirmemeli; sadece sorumlulukları ayırmalı. Ondan sonra
personel paneli ve widget API çok daha temiz bağlanır.
