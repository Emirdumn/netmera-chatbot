# Deploy — PortvMind Public Cloud

Bu proje tek bir VM üzerinde Docker Compose ile çalışacak şekilde
hazırlandı: `customer_app` (:8501), `agent_console` (:8502), ikisinin
önünde bir `nginx` (müşteri tarafı herkese açık `:80`, personel paneli
HTTP Basic Auth ile korunan `:8082`).

## 1. VM oluştur (PortvMind konsolu — `tr-ist-01-console.portvmind.com`)

**Compute → Instanceler → Instance Başlat:**

| Adım | Değer |
|---|---|
| Image | Ubuntu Server 24.04 |
| Flavor | `g1.large` (2 vCPU / 8 GB RAM, ~1.306 TL/ay) |
| Boot Source | Image (Volume Create Options: Delete on Termination = **kapat** öneri, VM silinse de disk kalsın) |
| Network | mevcut public network + floating IP ata |
| Security Group | yeni bir grup oluştur: `22/tcp` (SSH, sadece kendi IP'ne), `80/tcp` (herkese açık), `8082/tcp` (herkese açık — auth nginx'te) |

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

```bash
sudo apt-get install -y apache2-utils
htpasswd -B -c nginx/.htpasswd personel
# şifreyi soracak — güçlü bir şifre gir
```

`nginx/.htpasswd` **asla git'e girmez** (`.gitignore`'da) — her sunucuda
ayrıca oluşturulmalı.

> Personel panelinde iki kapı vardır: önce nginx Basic Auth, sonra uygulamanın
> kendi personel seçimi + `STAFF_DEMO_PASSWORD` kontrolü. Bu iki parolayı ayrı
> tutmak daha güvenlidir.

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

- Müşteri: `http://<FLOATING_IP>/`
- Personel: `http://<FLOATING_IP>:8082/` (kullanıcı adı/şifre sorar)

İlk açılışta `storage/helpdesk.db` otomatik oluşur, `config/departments.py`
sahte personeli seed eder — bu, VM'in kendi diskinde kalıcı bir Docker
volume'unda (`netmera_storage`) durur; `docker compose down` veri
kaybetmez, sadece `docker compose down -v` (volume'u da siler) kaybettirir.

## 8. (Opsiyonel ama önerilir) Gerçek bir domain + HTTPS

Bir domain'i floating IP'ye yönlendirip Certbot ile ücretsiz SSL almak
istersen:

```bash
sudo apt-get install -y certbot python3-certbot-nginx
# nginx container yerine host'ta nginx kurup certbot onunla calisir,
# ya da nginx-proxy/caddy gibi otomatik-SSL alan bir reverse proxy'e gecilir.
```

Bu adım şu an compose dosyasına dahil değil — domain netleşince ayrıca
ele alınmalı (Let's Encrypt + docker-compose entegrasyonu için `caddy`
kullanmak nginx+certbot'tan daha az elle uğraş gerektirir).

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
docker compose restart nginx   # customer_app/agent_console yeniden
                                 # olusturulunca ic IP'leri degisir; nginx
                                 # bunu proxy_pass icin baslangicta cache'ler,
                                 # restart etmezse 502 verebilir.
```

## Acil parola rotasyonu

Public repoya veya ekrana bir parola sızdıysa iki kapıyı da döndür:

```bash
cd netmera
git pull

# 1) .env icindeki STAFF_DEMO_PASSWORD degerini yeni, güçlü bir degerle değiştir
nano .env

# 2) nginx Basic Auth parolasini yeniden üret
htpasswd -B -c nginx/.htpasswd personel

# 3) yeni kod/env ile servisleri yeniden oluştur
docker compose build
docker compose up -d --force-recreate customer_app agent_console nginx

# 4) SQLite'taki mevcut personel hash'lerini yeni STAFF_DEMO_PASSWORD'a döndür
docker compose exec customer_app python scripts/rotate_staff_passwords.py
```

Script parola veya hash yazdırmaz; yalnızca kaç personel kaydının güncellendiğini söyler.

## Sorun giderme

```bash
docker compose logs -f customer_app
docker compose logs -f agent_console
docker compose logs -f nginx
```
