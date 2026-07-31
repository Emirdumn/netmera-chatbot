# HTTPS'e Geçiş Planı (Caddy)

**Durum:** Öneri — onay bekliyor, kod yazılmadı.
**Amaç:** Widget'ın canlıya açılabilmesi. HTTPS bir siteye gömülen widget,
`http://` API çağrısı yapamaz (tarayıcı *mixed content* olarak bloke eder).

---

## Önce netleşmesi gereken 3 şey

Bunlar teknik değil, erişim/yetki soruları — cevaplar planı değiştirir.

1. **`netmera.com` DNS kayıtlarını ekleyebiliyor musunuz?**
   Plan `destek.netmera.com` varsayıyor. Kurumsal domain'e erişim yoksa
   alternatif bir domain (ya da `*.nip.io` gibi geçici bir çözüm) gerekir.
2. **Widget'ı gömmek istediğiniz sayfaya `<script>` ekleyebiliyor musunuz?**
   `WIDGET_ALLOWED_ORIGINS` buna göre belirlenir.
3. **Personel paneli için ikinci bir subdomain açılabilir mi?**
   (`panel.netmera.com`). Açılamazsa alternatifi aşağıda.

---

## Engel: güvenlik grubunda 443 kapalı

VM'in güvenlik grubunda (`netmera-sg`) şu an yalnızca **22, 80, 8082** açık.
HTTPS için **443/tcp** eklenmeli — aksi halde sertifika alınamaz ve site
açılmaz. PortvMind konsolu → Security → Security Groups → `netmera-sg` →
Add Ingress Rule: `443/tcp`, `0.0.0.0/0`.

Sunucuda 443 boş (doğrulandı), disk 14 GB boş.

---

## DNS kayıtları

| Kayıt | Tip | Değer | Ne için |
|---|---|---|---|
| `destek.netmera.com` | A | `43.229.92.6` | Müşteri paneli + widget + API |
| `panel.netmera.com` | A | `43.229.92.6` | Personel paneli |

Let's Encrypt HTTP-01 doğrulaması yapacağı için **DNS yayılmadan Caddy'yi
başlatmayın** — başarısız denemeler Let's Encrypt kotasını yer.

---

## Mimari önerisi: Caddy, nginx'in **yerine**

```
Internet
  :80  → HTTP'den HTTPS'e yönlendirme + ACME doğrulaması
  :443 → TLS
         │
         ├── destek.netmera.com
         │     ├─ /                → customer_app:8501   (Streamlit, WS)
         │     ├─ /api/widget/*    → widget_api:8000
         │     └─ /widget/*        → statik dosyalar (widget.js/.css)
         │
         └── panel.netmera.com
               └─ /                → agent_console:8502  (basic auth)
```

**Neden nginx'i değiştiriyoruz, üstüne koymuyoruz:**

- Caddy sertifikayı otomatik alır ve yeniler (asıl istediğimiz bu).
- İki proxy katmanı = iki ayrı yapılandırma, iki hata kaynağı. Mevcut
  nginx yapılandırması ~50 satır, Caddyfile'a taşınması kolay.
- Caddy WebSocket yükseltmesini kendiliğinden yapar — nginx'te bunun için
  elle `Upgrade`/`Connection` başlıkları yazmak zorundaydık (Streamlit
  bunlara bağlı).
- Deploy sırasında yaşadığımız **nginx upstream DNS önbelleği** sorunu
  (konteyner yeniden oluşunca 502) ortadan kalkar; şu an her deploy'da
  `docker compose restart nginx` yapmak zorundayız.

**Daha düşük riskli alternatif:** Caddy'yi nginx'in önüne koymak (Caddy
:443 → nginx :80). Test edilmiş nginx yapılandırmasına hiç dokunulmaz ama
iki katman kalır ve yukarıdaki DNS önbelleği sorunu da devam eder. Riski
minimumda tutmak isterseniz bu seçenek de geçerli.

---

## Dosya değişiklikleri (uygulama onaylanırsa)

| Dosya | Değişiklik |
|---|---|
| `caddy/Caddyfile` | **yeni** — iki site bloğu, basic auth, statik widget |
| `docker-compose.yml` | `nginx` servisi → `caddy`; `:443` portu; `caddy_data` + `caddy_config` volume'ları |
| `nginx/` | kaldırılır (git geçmişinde kalır, geri dönülebilir) |
| `.env` | aşağıdaki widget değerleri |
| `DEPLOY.md` | HTTPS bölümü güncellenir, `restart nginx` adımı kalkar |

**Değişmeyecekler:** `ui/customer_app.py`, `ui/agent_console.py`,
`app_services/`, `graph/`, `agents/`, `tools/`, `widget/`, `widget_api/`.
Uygulama kodu bu işten hiç etkilenmiyor.

---

## `.env` değerleri

```bash
WIDGET_API_ENABLED=true
WIDGET_TOKEN_SECRET=<32+ karakter rastgele>
WIDGET_ALLOWED_ORIGINS=https://www.netmera.com,https://netmera.com
WIDGET_RATE_LIMIT_PER_MIN=20
```

`WIDGET_TOKEN_SECRET`, `STAFF_DEMO_PASSWORD`'da yaptığımız gibi doğrudan
VM'de üretilip `.env`'e yazılacak, hiçbir yerde ekrana basılmayacak:

```bash
python3 -c "import secrets; print('WIDGET_TOKEN_SECRET=' + secrets.token_urlsafe(32))" >> .env
```

---

## Personel paneli parolası — dikkat

Caddy `htpasswd` dosyası kullanmaz; parolayı **bcrypt hash** olarak
Caddyfile içinde ister (`caddy hash-password` ile üretilir). Yani
`nginx/.htpasswd` geçersiz kalır.

Bu aslında iyi bir zamanlama: nginx Basic Auth parolası (`EdVd1903`) bu
sohbette dolaştığı için zaten döndürülmesi gerekiyordu ve o adım hâlâ
bekliyor. Geçiş sırasında yeni parola üretilip iki iş birlikte kapanır.

---

## Uygulama sırası

1. Güvenlik grubuna **443/tcp** ekle.
2. DNS kayıtlarını gir, yayılmasını bekle (`dig destek.netmera.com` ile doğrula).
3. Caddyfile'ı yaz, **yerelde `tls internal` ile** test et (gerçek sertifika
   almadan yapılandırmayı doğrula).
4. VM'de **Let's Encrypt staging** ile bir tur dene — yapılandırma hatası
   üretim kotasını yakmasın.
5. Staging başarılıysa üretim CA'ya geç, servisleri kaldır.
6. Doğrula: müşteri paneli, personel paneli (yeni parola), widget.js,
   `/api/widget/health`.
7. En son `WIDGET_API_ENABLED=true` yapıp widget'ı aç.
8. Gömen sayfaya `<script>` etiketini ekle.

Adım 4 önemli: Let's Encrypt üretim ortamında **aynı domain için haftada 5
sertifika** sınırı var. Yapılandırmayı staging'de doğrulamadan üretimde
deneme yapmak, hata halinde bir haftalık kilit anlamına gelebilir.

---

## Riskler

| Risk | Etki | Önlem |
|---|---|---|
| Caddy sertifika verisi kalıcı değilse | Her restart'ta yeni sertifika → kota dolar → site HTTPS'siz kalır | `caddy_data` **named volume** şart |
| DNS yayılmadan başlatma | ACME başarısız, kota yenir | Önce `dig` ile doğrula |
| 443 güvenlik grubunda kapalı | Sertifika alınamaz | Adım 1 |
| Basic auth hash formatı | Personel paneli açılmaz | Geçişte `caddy hash-password` ile yeni parola |
| Cutover anı | nginx durup Caddy kalkarken birkaç saniye kesinti | Düşük trafikli saatte yap |

**Geri alma:** `git revert` + `docker compose up -d`. nginx yapılandırması
git geçmişinde duruyor, eski hâline dönmek tek commit.

---

## Geçişten sonra değişen davranışlar

- `http://43.229.92.6/` ve `:8082` **artık kullanılmayacak.** IP ile erişimde
  sertifika domain'e ait olduğu için tarayıcı uyarı verir. Personelin
  yer imlerini güncellemesi gerekir.
- HTTP'ye gelen istekler otomatik HTTPS'e yönlenir.
- Deploy adımlarından `docker compose restart nginx` kalkar.

---

## Opsiyonel sıkılaştırmalar (bu iş paketine dahil değil)

- HSTS başlığı (`Strict-Transport-Security`) — geri dönüşü zor, önce bir
  süre sorunsuz çalıştığından emin olduktan sonra.
- Personel paneline IP kısıtı (`@allowed remote_ip ...`).
- Let's Encrypt bildirimleri için Caddyfile'da `email` tanımı.
