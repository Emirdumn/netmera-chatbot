# Netmera Help Desk v3 — Orkestratör ve Konuşma Belleği

> **Devam planı.** `PLAN_MULTI_AGENT.md` (FAZ 0-8) tamamlandı ve çalışıyor.
> Bu dosya FAZ 9-14'ü kapsar: sistemi *belleksiz sınıflandırıcıdan* **bağlam
> yöneten orkestratöre** dönüştürür.
>
> Kullanım: `PLAN_ORCHESTRATOR.md dosyasindaki FAZ 9 bolumunu oku ve uygula.`

---

## 1. Neyi Düzeltiyoruz

Gerçek bir oturumda yakalanan hata zinciri:

```
1  Kullanıcı : "Fiyatlandırma hakkında bilgi almak istiyorum"
   💼 Satış   : "adınızı, şirketinizi, e-postanızı, uygulama türünüzü ve
                 tahmini kullanıcı sayınızı paylaşır mısınız?"          ✅ doğru

2  Kullanıcı : "Emir Duman / Vmind Bilgi Teknolojileri / Kahve sipariş
                 uygulaması / 1000 kullanıcı"                ← 5 alanın 5'i geldi
   🌐 Genel   : "Emir Duman ve Vmind hakkında bilgi bulunmamaktadır"     ❌ ÇÖKÜŞ

3  Kullanıcı : "Anlamadım benden ne istedin"
   🔁 Devir   : TICKET-0001                                    ❌ gereksiz devir
```

Adım 2'de üç şey aynı anda oldu: yanlış agent'a gitti, cevap RAG sorgusu sanıldı,
ve **verilen bilgilerin hiçbiri kaydedilmedi**.

### Kök nedenler (kodda doğrulandı)

| # | Kök neden | Kanıt | Faz |
|---|---|---|---|
| 1 | Router sadece son mesajı görüyor, konuşma geçmişi yok | `router_agent.py:76` → `state["messages"][-1]` | 10 |
| 2 | Agent da sadece son mesajı görüyor; kullanıcının **cevabını** RAG sorgusu sanıyor | `base.py:28-32` | 10, 12 |
| 3 | Yapışkan yönlendirme yok — her tur sıfırdan sınıflandırma | `workflow.py:32-35` | 10 |
| 4 | Çalışan bellek yok; `state["lead"]` tanımlı ama **hiçbir yer yazmıyor** | `state.py:24` | 9 |
| 5 | Agent'lar sabit boru hattı: `ara → skor düşükse pes → tek LLM çağrısı`. Aramaya karar vermiyor, sorgu yazmıyor, tekrar aramıyor | `base.py:52-64` | 12 |
| 6 | TR soru ↔ EN doküman eşleşmesi zayıf (segment sorusunda benzerlik 0.52, SDK sorusunda 0.77) | canlı retrieval testi | 13 |

**Tek cümlelik özet:** Sistem her mesajı, o mesajdan öncesi hiç yaşanmamış gibi işliyor.

---

## 2. Hedef Mimari

Yeni katmanlar **kalın**:

```
                        Kullanıcı mesajı
                               │
                    ┌──────────▼───────────┐
                    │  📝 MEMORY AGENT     │  her turda çalışır
                    │  Bilgi çıkar + MERGE │
                    └──────────┬───────────┘
                               │  customer_profile / case_notes güncellendi
                    ┌──────────▼───────────┐
                    │  🧠 ORKESTRATÖR      │  ← router'ın yerine
                    │                      │
                    │  Girdi:              │
                    │   • son N mesaj      │
                    │   • müşteri profili  │
                    │   • aktif agent      │
                    │   • bekleyen soru    │
                    │   • akış durumu      │
                    │                      │
                    │  Karar:              │
                    │   continue | switch  │
                    │   | escalate         │
                    └──────────┬───────────┘
              ┌────────┬───────┼────────┬─────────┐
              ▼        ▼       ▼        ▼         ▼
           SATIŞ   DESTEK  TEKNİK   GENEL   ESCALATION
              │        │       │        │
              └────────┴───┬───┴────────┘
                           │
              ┌────────────▼─────────────┐
              │  🔄 ReAct TOOL DÖNGÜSÜ   │  agent kendi karar verir
              │  düşün → tool → gözlem   │  (en fazla 4 tur)
              │  → tekrar düşün → cevap  │
              └────────────┬─────────────┘
                           │
              ┌────────────▼─────────────┐
              │  🎯 SLOT YÖNETİMİ        │  eksik bilgi var mı?
              │  varsa → sor, yoksa → ilerle │
              └──────────────────────────┘
```

### İki yeni kavram

**A. Çalışan bellek (working memory)** — konuşma boyunca biriken yapılandırılmış not:

```python
customer_profile = {
    "person_name": "Emir Duman",
    "company": "Vmind Bilgi Teknolojileri",
    "email": None,                      # henüz verilmedi
    "sector": "yiyecek-içecek",
    "app_name": "Kahve sipariş uygulaması",
    "platform": ["ios", "android"],
    "user_scale": "1000",
    "is_existing_customer": False,
}

case_notes = {
    "goal": "fiyat teklifi almak",
    "problem_summary": None,
    "error_message": None,
    "sdk_version": None,
    "steps_tried": [],
}
```

Senin tarif ettiğin "not alma" tam olarak bu: *"kullanıcı X şirketinde çalışıyor,
Y kullanıcısı var"* ve *"kullanıcı X sorununu Y platformunda kurmak istiyor"*.

**Birleştirme (merge) kuralı:** yeni değer `None` ise eskisi korunur — bilgi asla
silinmez. Listeler birleşir (union). Bu kural bellek katmanının tamamının temelidir.

**B. Yapışkan yönlendirme (sticky routing)** — orkestratör her turda şunu sorar:
*"Kullanıcı benim son sorduğum soruyu mu cevaplıyor?"* Cevap evet ise konu
değişmemiştir, aktif agent'ta kalınır. Ekrandaki hatayı doğrudan bu kural çözer.

---

## 3. Framework Kararı

**LangGraph'ta kalıyoruz.** Gerekçe:

- Ekrandaki hatanın framework ile ilgisi yok — graf *belleksiz* kurulduğu için oluştu.
  Aynı hata başka bir framework'te aynen tekrarlanır.
- İhtiyacımız olan her şey zaten var ve çalışıyor: state reducer'ları, koşullu
  kenarlar, SQLite checkpointing, `interrupt()` ile human-in-the-loop.
- FAZ 0-8'de yazılan ~40 dosya korunur; yeniden yazım maliyeti sıfır.

**Otonom akıl yürütme ihtiyacı** (agent'ın kendi kendine "önce şunu arayayım, sonuca
göre şunu da arayayım" demesi) framework değiştirerek değil, **düğümlerin içine ReAct
döngüsü koyarak** çözülür — FAZ 12. Bu, LangGraph'ın önerdiği standart yaklaşımdır.

---

## FAZ 9 — Konuşma Belleği (Working Memory)

**Amaç:** Kullanıcının söylediği hiçbir bilginin kaybolmaması. Bu faz tek başına
ekrandaki hatanın yarısını çözer.

**Adımlar:**

- **a)** `graph/state.py`'ye yeni alanlar ekle:
  ```
  customer_profile : dict   # kalıcı müşteri bilgisi
  case_notes       : dict   # bu oturumdaki vaka bilgisi
  active_agent     : str    # şu an konuşan agent
  pending_question : str    # bot'un cevap beklediği soru
  flow_state       : dict   # aktif akış + doldurulmuş slotlar
  turn_count       : int
  ```
  `customer_profile` ve `case_notes` için **özel reducer** yaz (`merge_dict`):
  yeni değer `None`/boş ise eskisini koru, liste alanlarını birleştir.
  Bu reducer'ı `Annotated[dict, merge_dict]` ile bağla — LangGraph birleştirmeyi
  otomatik yapsın, düğümlerin elle uğraşmasına gerek kalmasın.

- **b)** `agents/memory_agent.py` yaz — **bu fazın kalbi**. Tool değil, LLM agent.
  Her kullanıcı mesajında çalışır, yapılandırılmış çıktı döndürür:
  ```python
  class ExtractedFacts(BaseModel):
      person_name: str | None ;  company: str | None
      email: str | None       ;  phone: str | None
      sector: str | None      ;  app_name: str | None
      platform: list[str]           # ios|android|web|flutter|react-native|huawei
      user_scale: str | None  ;  is_existing_customer: bool | None
      goal: str | None              # "fiyat teklifi almak", "push kurmak"
      problem_summary: str | None ;  error_message: str | None
      sdk_version: str | None ;  steps_tried: list[str]
  ```
  Prompt kuralı: **emin olmadığın alanı `None` bırak, asla tahmin etme.**
  Uydurma bilgi profile girerse tüm sistem yanlış yönlenir.

- **c)** `memory_node`'u grafiğin **en başına** ekle: `START → memory_node → orchestrator`.

- **d)** `storage/` — `session_notes` tablosu (session_id, profile_json,
  case_json, updated_at). Her turda güncelle. Amaç: personel devraldığında
  müşterinin tüm bilgileri önünde hazır olsun.

- **e)** `repository.py`'ye `upsert_notes()` ve `get_notes()` ekle.

**Doğrulama:**
```bash
python -c "
from agents.memory_agent import MemoryAgent
m = MemoryAgent()
print(m.extract('Emir Duman Vmind Bilgi teknolojileri Kahve siparisi uygulamasi 1000 kullanici'))
print(m.extract('iOS SDK 3.2 kullaniyorum, push token null donuyor'))
"
```

**Bitti kriteri:** İlk çağrı `person_name`, `company`, `app_name`, `user_scale`
alanlarını doğru dolduruyor; ikinci çağrı `platform=["ios"]`, `sdk_version="3.2"`,
`error_message` alanlarını yakalıyor. Uydurulmuş alan yok.

---

## FAZ 10 — Orkestratör (router'ın yerine)

**Amaç:** Bağlam farkındalığı olan yönlendirme. Ekrandaki hatanın diğer yarısı burada kapanır.

**Adımlar:**

- **a)** `agents/orchestrator.py` yaz. `router_agent.py` **silinmez** — orkestratör
  onun sınıflandırma yeteneğini içerir, eski dosya karşılaştırma için `v2_legacy/`'ye taşınır.

- **b)** Orkestratörün girdisi (router'dan farkı tam olarak bu):
  ```
  • son 6 mesaj (sadece sonuncusu değil)
  • customer_profile + case_notes
  • active_agent      (şu an kim konuşuyordu)
  • pending_question  (bot en son ne sormuştu)
  • flow_state        (hangi akıştayız, hangi slotlar dolu)
  ```

- **c)** Yapılandırılmış karar:
  ```python
  class OrchestratorDecision(BaseModel):
      is_answer_to_pending_question: bool   # ← EN KRİTİK ALAN
      topic_changed: bool
      action: Literal["continue","switch","escalate","clarify"]
      target_agent: Literal["sales","support","technical","general"]
      language: Literal["tr","en"]
      urgency: Literal["low","normal","high"]
      reasoning: str        # arayüzde gösterilecek — sunumda çok etkili
  ```

- **d)** **Yapışkanlık kuralı** (kod seviyesinde, LLM'e bırakılmaz):
  ```
  is_answer_to_pending_question == True  →  action="continue",
                                            target_agent = active_agent
  ```
  Yani "Emir Duman / Vmind / 1000 kullanıcı" mesajı satış agent'ına geri döner.

- **e)** Konu değişimi: `topic_changed=True` ise `switch`. Ama `flow_state` yarım
  kalmışsa agent kullanıcıya önce şunu sorar: *"Önce fiyat teklifini tamamlayalım
  mı, yoksa bu yeni konuya mı geçelim?"* — yarım kalan akış sessizce kaybolmaz.

- **f)** `clarify` aksiyonu: kullanıcı "anlamadım benden ne istedin" derse
  **devir açma** — bekleyen soruyu daha basit ifade ederek tekrar sor.
  Ekrandaki 3. adımdaki gereksiz TICKET-0001 bu kuralla önlenir.

- **g)** `graph/workflow.py`'yi güncelle: `router_node` → `orchestrator_node`,
  dallanma `decision.target_agent` üzerinden.

**Doğrulama:**
```bash
python tests/test_orchestrator.py
```
Test, ekrandaki konuşmayı birebir oynatır:
```
1. "Fiyatlandırma hakkında bilgi almak istiyorum"        → sales
2. "Emir Duman Vmind Bilgi teknolojileri 1000 kullanıcı" → sales (continue) ★
3. "Anlamadım benden ne istedin"                          → sales (clarify) ★
4. "iOS SDK entegrasyonu nasıl yapılır"                   → technical (switch)
```

**Bitti kriteri:** 2. adım `general`'a **düşmüyor**, `sales`'te kalıyor.
3. adım devir açmıyor. Bu iki madde bu planın varlık sebebidir.

---

## FAZ 11 — Akış ve Slot Yönetimi

**Amaç:** Agent'ın neyi bildiğini, neyi hâlâ sorması gerektiğini takip etmesi.

**Adımlar:**

- **a)** `flows/base.py` — `Slot(name, question_tr, question_en, required)` ve
  `Flow(name, slots, completion_action)` modelleri.

- **b)** `flows/sales_lead.py` — slotlar: `person_name`, `company`, `email`,
  `app_name`, `user_scale`. Tamamlanınca → `lead_capture_tool` + demo/devir teklifi.

- **c)** `flows/technical_case.py` — slotlar: `platform`, `sdk_version`,
  `error_message`, `steps_tried`. Tamamlanınca → hedefli RAG araması, çözülemezse
  **dolu vaka notuyla** teknik departmana devir.

- **d)** `flows/support_case.py` — slotlar: `affected_feature`, `when_started`,
  `steps_tried`.

- **e)** Slot doldurma **`customer_profile`'dan okur** — kullanıcı bir bilgiyi
  daha önce verdiyse tekrar sorulmaz. (Ekranda kullanıcı bilgileri iki kez yazmak
  zorunda kalmıştı; bu kural onu bitirir.)

- **f)** Agent aynı anda en fazla **2 eksik slot** sorar — 5 soruyu birden sormak
  kullanıcıyı kaçırıyor (ekrandaki 1. adımın sorunu buydu).

**Doğrulama:**
```bash
python tests/test_flows.py
```

**Bitti kriteri:** Profilde `company` doluyken satış akışı şirket adını tekrar
sormuyor; eksik slot kalmayınca akış `complete` durumuna geçiyor.

---

## FAZ 12 — Agent'ları ReAct Döngüsüne Geçirmek

**Amaç:** Agent'ların sabit boru hattı olmaktan çıkıp gerçekten *akıl yürütmesi*.
Senin "bunlar LLM bazlı çalışmalı, tool değiller" isteğinin karşılığı.

**Adımlar:**

- **a)** `agents/base.py`'deki `answer()` metodunu **tool döngüsüyle** değiştir:
  ```
  1. LLM'e profil + konuşma + tool'lar verilir
  2. LLM hangi tool'u çağıracağına KENDİ karar verir
  3. Tool sonucu gözlem olarak geri beslenir
  4. LLM ya yeni tool çağırır ya nihai cevabı yazar
  5. En fazla 4 tur (MAX_TOOL_ITERATIONS)
  ```
  Kritik fark: agent **iki kez arayabilir**, ilk arama zayıfsa **sorguyu yeniden
  yazabilir**. Şu an ilk aramada 0.35'in altında skor gelirse doğrudan pes ediyor.

- **b)** `tools/query_builder_tool.py` — konuşmayı ve profili tek bir bağımsız
  arama sorgusuna çevirir, **İngilizceye çevirerek** (dokümanlar İngilizce).
  Örnek: `"peki ya android'de?"` + profil → `"Android SDK push notification setup"`.
  Bu tek tool hem bağlam kaybını hem TR/EN uyumsuzluğunu çözer.

- **c)** `CONFIDENCE_THRESHOLD` mantığını değiştir: düşük skor artık **anında pes
  etme** değil, *"sorguyu yeniden yaz ve tekrar dene"* sinyali. Sadece ikinci
  denemeden sonra devir düşünülür.

- **d)** Her agent'ın sistem promptuna `customer_profile` + `case_notes` enjekte et
  — agent kiminle konuştuğunu bilsin.

- **e)** ReAct adımlarını `state["reasoning_trace"]`'e yaz — arayüzde
  "🧠 Agent nasıl düşündü" panelinde gösterilecek. Sunumda güçlü bir demo unsuru.

**Doğrulama:**
```bash
python tests/test_react_loop.py
```

**Bitti kriteri:** "peki ya android tarafında?" gibi bağlama bağlı takip sorusu,
önceki konuyu koruyarak doğru sonucu getiriyor; trace'te iki arama görülüyor.

---

## FAZ 13 — Retrieval Kalitesi

**Amaç:** Ölçülen zayıflığı kapatmak — TR sorularda benzerlik 0.52, EN sorularda 0.77.

**Adımlar:**

- **a)** FAZ 12-b'deki sorgu çevirisini ölç: 20 Türkçe soruluk sabit set üzerinde
  çeviri öncesi/sonrası ortalama benzerlik karşılaştırması.

- **b)** Yeterli değilse **hibrit arama**: BM25 (anahtar kelime) + vektör skorlarını
  birleştir (RRF). SDK adları, hata kodları, `netmera-android-sdk` gibi tam
  eşleşme gerektiren terimlerde vektör araması zayıf kalır.

- **c)** Yeniden sıralama (rerank): ilk 20 sonucu çek, `cross-encoder` ile en iyi 5'i
  seç. Lokal ve ücretsiz (`ms-marco-MiniLM-L-6-v2`, ~80 MB).

- **d)** `rag_search_tool`'a `heading_boost` — kullanıcının kelimeleri
  `heading_path` ile eşleşiyorsa skoru artır.

- **e)** Ölçüm: `tests/retrieval_benchmark.py` — 30 soru (10 user_guide, 10 dev_guide,
  10 website), her değişiklik sonrası isabet@5 raporla.

**Bitti kriteri:** Türkçe sorularda ortalama en-iyi benzerlik 0.52 → 0.70+;
isabet@5 %85 üzeri.

---

## FAZ 14 — Arayüz, Test ve Sunum

**Amaç:** Yeni yapının görünür ve savunulabilir olması.

**Adımlar:**

- **a)** `ui/customer_app.py` kenar çubuğuna **📋 Müşteri Notu** paneli — konuşma
  ilerledikçe canlı dolan profil. *Sunumun en etkileyici anı: kullanıcı konuşuyor,
  yan panelde notlar kendiliğinden birikiyor.*

- **b)** **🧠 Orkestratör kararı** açılır paneli: `reasoning`, seçilen agent,
  `is_answer_to_pending_question`, `topic_changed`. Yönlendirmenin neden öyle
  olduğu şeffaf olsun.

- **c)** **🔄 Akış durumu** göstergesi: `Satış akışı — 5 slottan 3'ü dolu`.

- **d)** `ui/agent_console.py`: devir kartında artık **dolu müşteri profili +
  vaka notu + bot'un ne denediği** görünsün. Personel sıfırdan başlamasın —
  bu, human-in-the-loop'un asıl değer önerisi.

- **e)** `tests/demo_scenarios.py`'ye ekrandaki konuşmayı **regresyon testi** olarak
  ekle. Bir daha aynı hataya düşmediğimizi her çalıştırmada kanıtlar.

- **f)** README'yi v3 mimarisiyle güncelle; "önce/sonra" bölümü ekle
  (ekrandaki hatalı akış → düzeltilmiş akış).

**Bitti kriteri:** Ekrandaki 3 adımlık konuşma baştan sona doğru ilerliyor;
yan panelde profil doluyor; gereksiz devir açılmıyor.

---

## 4. Sonuç: Aynı Konuşma, Yeni Mimaride

```
1  Kullanıcı : "Fiyatlandırma hakkında bilgi almak istiyorum"
   📝 Bellek  : goal="fiyat teklifi almak"
   🧠 Orkestra: switch → sales   |  akış: sales_lead başladı (0/5 slot)
   💼 Satış   : "Öncelikle adınızı ve şirketinizi alabilir miyim?"   ← 5 değil 2 slot

2  Kullanıcı : "Emir Duman Vmind Bilgi teknolojileri Kahve siparişi uyg. 1000 kullanıcı"
   📝 Bellek  : person_name="Emir Duman", company="Vmind Bilgi Teknolojileri",
                app_name="Kahve sipariş uygulaması", user_scale="1000"
   🧠 Orkestra: is_answer_to_pending_question=TRUE → continue → sales   ★ DÜZELDİ
   💼 Satış   : "Teşekkürler Emir Bey. Son olarak e-posta adresinizi
                alabilir miyim? (4/5 slot dolu)"

3  Kullanıcı : "Anlamadım benden ne istedin"
   🧠 Orkestra: action=clarify → sales   ★ DEVİR AÇMIYOR
   💼 Satış   : "Özür dilerim, daha net sorayım: size teklifi hangi
                e-posta adresine gönderelim?"

4  Kullanıcı : "emir@vmind.com.tr"
   📝 Bellek  : email="emir@vmind.com.tr"
   🎯 Akış    : 5/5 tamamlandı → lead_capture_tool
   💼 Satış   : "Bilgilerinizi satış ekibimize ilettim. Hemen bir
                temsilcimize bağlanmak ister misiniz?"
   👤 Personel: devir kartında Emir Bey'in TÜM bilgileri hazır
```

---

## 5. Sıra ve Süre

| Faz | İçerik | Süre | Etki |
|---|---|---|---|
| **9** | **Konuşma belleği** | 60 dk | ★★★ Bilgi kaybı biter |
| **10** | **Orkestratör** | 75 dk | ★★★ Yanlış yönlendirme biter |
| 11 | Akış / slot yönetimi | 60 dk | ★★ Tekrar soru sorma biter |
| 12 | ReAct döngüsü | 75 dk | ★★★ Agent'lar gerçekten akıl yürütür |
| 13 | Retrieval kalitesi | 60 dk | ★★ Cevap isabeti artar |
| 14 | Arayüz + test | 60 dk | ★★ Sunulabilirlik |
| | **Toplam** | **~6.5 saat** | |

**FAZ 9 + FAZ 10 birlikte ekrandaki hatanın tamamını çözer (~2.5 saat).**
Zaman darsa bu ikisi yapılıp geri kalan sunum sonrasına bırakılabilir.

---

## 6. Riskler

| Risk | Önlem |
|---|---|
| Memory agent bilgi uyduruyor | Prompt'ta "emin değilsen `None`" kuralı + `test_memory_extraction.py` ile negatif testler |
| Orkestratör her turda ekstra LLM çağrısı → kota | Memory + orkestratör tek çağrıda birleştirilebilir (fallback planı) |
| Yapışkanlık fazla agresif → konu değişince takılı kalır | `topic_changed` ayrı alan; FAZ 10 testinde 4. adım bunu ölçer |
| ReAct döngüsü sonsuza girer | `MAX_TOOL_ITERATIONS = 4` sabit sınır |
| Yeni state alanları eski checkpoint'leri bozar | `total=False` + reducer'lar varsayılan üretir; gerekirse `checkpoints.db` sıfırlanır (oturum geçmişi kaybı önemsiz) |

---

## 7. Başlangıç

```bash
cd "/Users/emir/NETMERA 27 JULY" && source venv/bin/activate
```

Claude'a:

```
PLAN_ORCHESTRATOR.md dosyasindaki FAZ 9 bolumunu oku ve adim adim uygula.
```
