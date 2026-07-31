# Deploy — PortvMind Public Cloud

Bu proje tek bir VM üzerinde Docker Compose ile çalışacak şekilde
hazırlandı: `customer_app` (:8501), `agent_console` (:8502), ikisinin
önünde bir `caddy` (TLS'i otomatik alır/yeniler, HTTP'yi HTTPS'e
yönlendirir). Müşteri paneli, widget ve widget API bir hostname'de;
personel paneli Basic Auth korumalı ayrı bir hostname'de.

## 1. VM oluştur (PortvMind konsolu — `tr-ist-01-console.portvmind.com`)

**Compute → Instanceler → Instance Başlat:**

| Adım | Değer |
|---|---|
| Image | Ubuntu Server 24.04 |
| Flavor | `g1.large` (2 vCPU / 8 GB RAM, ~1.306 TL/ay) |
| Boot Source | Image (Volume Create Options: Delete on Termination = **kapat** öneri, VM silinse de disk kalsın) |
| Network | mevcut public network + floating IP ata |
| Security Group | yeni bir grup oluştur: `22/tcp` (SSH), `80/tcp` (ACME doğrulaması + HTTPS yönlendirmesi), `443/tcp` (HTTPS) |

VM oluşunca **Floating IP**'yi not al.

## 2. VM'e bağlan, Docker kur

```bash
ssh ubuntu@<FLOATING_IP>

curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER
newgrp docker

sudo apt-get update && sudo apt-get install -y git
```

## 3. Kodu getir

```bash
git clone <repo-url> netmera && cd netmera
```

(Repo private ise: deploy key veya personal access token ile clone et.)

## 4. `.env` dosyasını oluştur

```bash
cp .env.example .env
nano .env
```

Doldur:
```bash
LLM_PROVIDER=openrouter
OPENROUTER_API_KEY=sk-or-...
OPENROUTER_MODEL=openai/gpt-4o-mini
LOG_TOOL_CALLS=true
STAFF_DEMO_PASSWORD=<python -c "import secrets; print(secrets.token_urlsafe(32))" ile üret>
```

`STAFF_DEMO_PASSWORD` için kodda varsayılan yoktur. Boş, çok kısa veya placeholder
değerle uygulama açılmaz.

## 5. Personel paneli şifresini oluştur (HTTP Basic Auth)

Caddy `htpasswd` dosyası kullanmaz; parolayı **bcrypt hash** olarak
`.env` içindeki `PANEL_PASSWORD_HASH` değişkeninden okur.

```bash
# 1) Guclu bir parola uret ve SADECE sunucuda sakla
python3 -c "import secrets; print(secrets.token_urlsafe(24))" > ~/panel-parola.txt
chmod 600 ~/panel-parola.txt

# 2) Hash'ini uret
docker run --rm caddy:2-alpine caddy hash-password \
  --plaintext "$(cat ~/panel-parola.txt)"
```

> **⚠ TUZAK — mutlaka okuyun.** bcrypt hash `$` içerir ve Docker Compose
> bunu **değişken sanar**. `.env`'e olduğu gibi yazarsanız hash konteynere
> **bozuk** ulaşır (sessizce kısalır) ve panele hiçbir parolayla
> giremezsiniz. `.env`'e yazarken her `$` **iki kez** yazılmalı:
>
> ```
> $2a$14$abc...   ->   PANEL_PASSWORD_HASH=$$2a$$14$$abc...
> ```
>
> Doğrulama: `docker compose exec caddy sh -c 'echo ${#PANEL_PASSWORD_HASH}'`
> **60** dönmeli. Daha kısaysa escape eksiktir.

> Personel panelinde iki kapı vardır: önce Caddy Basic Auth
> (`PANEL_PASSWORD_HASH`), sonra uygulamanın kendi personel seçimi +
> `STAFF_DEMO_PASSWORD` kontrolü. Bu iki parolayı ayrı tutun.

## 6. Chroma/veri indeksi güncel mi kontrol et

`chroma_db/` repo ile birlikte geliyor (imaja gömülü). Dokümantasyon
güncellendiyse deploy öncesi lokalde yeniden indeksleyip commit'le:

```bash
python -m data_pipeline.indexer
```

Reindex sonrası (opsiyonel ama önerilir): Redis soru-cevap cache'i eski
dokümana göre üretilmiş yanıtları tutmaya devam edebilir (TTL 3 gün, kendi
kendine düşer ama hemen temizlemek istersen):

```bash
docker compose exec redis redis-cli FLUSHALL
```

## 7. Ayağa kaldır

```bash
docker compose build
docker compose up -d
docker compose ps       # ucu ucuna 3 servis de "healthy"/"running" olmali
```

- Müşteri + widget: `https://<HOSTNAME>/`
- Personel: `https://<STAFF_HOSTNAME>/` (kullanıcı adı/şifre sorar)

İlk açılışta Caddy sertifikayı otomatik alır. Büyük bir Caddyfile
değişikliğinden önce **staging CA ile deneyin** — üretimde aynı domain
için haftada 5 sertifika sınırı vardır:
`acme_ca https://acme-staging-v02.api.letsencrypt.org/directory`

İlk açılışta `storage/helpdesk.db` otomatik oluşur, `config/departments.py`
sahte personeli seed eder — bu, VM'in kendi diskinde kalıcı bir Docker
volume'unda (`netmera_storage`) durur; `docker compose down` veri
kaybetmez, sadece `docker compose down -v` (volume'u da siler) kaybettirir.

## 8. Domain / hostname

TLS **kurulu ve otomatik** (Caddy). Yapılması gereken tek şey, kullanılan
hostname'lerin sunucunun IP'sine çözümlenmesi.

**Pilot kurulumda DNS kaydı gerekmedi** — `sslip.io` kullanıldı; IP'yi
hostname'in içinde taşıdığı için kendiliğinden doğru adrese çözümlenir:

```
netmera-helpdesk.<IP>.sslip.io   -> müşteri paneli + widget + API
netmera-staff.<IP>.sslip.io      -> personel paneli
```

Gerçek domain'e geçerken iki A kaydı açıp `caddy/Caddyfile` içindeki
hostname'leri değiştirmek yeterli; başka değişiklik gerekmez.

> **Üretim DNS'ine dikkat.** Pilotta `destek.netmera.com` ve
> `panel.netmera.com` düşünülmüştü; kontrol edildiğinde ikisinin de zaten
> **çalışan üretim servislerine** işaret ettiği görüldü (CloudFront ve
> başka bir sunucu). Kullanılacak hostname'in boş olduğunu kayıt açmadan
> önce `dig` ile doğrulayın.

### Sertifika verisi kalıcı olmalı

Sertifikalar `caddy_data` named volume'unda durur. Bu volume silinirse her
başlangıçta yeni sertifika istenir ve **Let's Encrypt kotası dolar**
(aynı domain için haftada 5). `docker compose down -v` bu volume'u da
siler — üretimde kullanmayın.

## 9. (Opsiyonel) Verinin gerçek bir cloud Volume'da durması

Şu anki kurulum, kalıcı veriyi Docker'ın kendi yönettiği bir volume'da
(`netmera_storage`) tutuyor — bu, VM'in kök diskinde durur ve VM
silinmediği sürece kalıcıdır. Eğer VM'den BAĞIMSIZ, ayrı bir disk
(PortvMind → Volumeler) üzerinde tutmak istersen (VM'i silip yeniden
kursan bile veri korunsun diye):

1. PortvMind konsolunda bir Volume oluştur, VM'e bağla.
2. VM içinde formatla ve mount et: `sudo mkfs.ext4 /dev/vdb && sudo mkdir -p /data && sudo mount /dev/vdb /data` (kalıcı olması için `/etc/fstab`'a ekle).
3. `docker-compose.yml`'deki `volumes: netmera_storage:` satırını kaldırıp
   her iki serviste de `volumes:` altına `/data/netmera-storage:/app/storage`
   yaz (named volume yerine bind mount).

## Güncelleme (yeni kod / yeni doküman geldiğinde)

```bash
cd netmera
git pull
docker compose build
docker compose up -d
```

> nginx döneminde her deploy'dan sonra `docker compose restart nginx`
> gerekiyordu (nginx upstream IP'sini önbelleğe alıyor, konteyner yeniden
> oluşunca 502 veriyordu). **Caddy'de bu adım gerekmiyor.**

## Acil parola rotasyonu

Public repoya veya ekrana bir parola sızdıysa iki kapıyı da döndür:

```bash
cd netmera
git pull

# 1) .env icindeki STAFF_DEMO_PASSWORD degerini yeni, güçlü bir degerle değiştir
nano .env

# 2) Panel parolasini yeniden uret ve hash'ini .env'e yaz
#    ($ escape'ini unutmayin — yukaridaki TUZAK notu)

# 3) yeni kod/env ile servisleri yeniden oluştur
docker compose build
docker compose up -d --force-recreate customer_app agent_console caddy

# 4) SQLite'taki mevcut personel hash'lerini yeni STAFF_DEMO_PASSWORD'a döndür
docker compose exec customer_app python scripts/rotate_staff_passwords.py
```

Script parola veya hash yazdırmaz; yalnızca kaç personel kaydının güncellendiğini söyler.

## Sorun giderme

```bash
docker compose logs -f customer_app
docker compose logs -f agent_console
docker compose logs -f caddy
```
