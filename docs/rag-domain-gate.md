# Fast RAG Domain Gate

Amaç: Netmera User Guide, Developer Guide ve web sitesi kapsamındaki sorulara
hızlı, kaynaklı cevap vermek; Netmera dışı soruları insana devretmeden kapsam
dışı diye kapatmak.

Akış:

1. Son kullanıcı mesajı riskli bir süreç mesajı mı kontrol edilir.
   - Temsilci talebi, fiyat/demo/satın alma, açık hata/şikayet, pending form
     cevabı eski agent akışına bırakılır.
2. Kısa sosyal mesajlar (selamlaşma / teşekkür) LLM/RAG'e girmeden
   dostça kısa yanıt alır (`greeting` / `thanks` modları).
3. Hızlı vektör araması (`semantic_probe`) yapılır.
   - `FAST_RAG_DIRECT_THRESHOLD` üstünde ise doğrudan verilen kaynaklardan
     grounded cevap üretilir.
4. Semantik eşleşme zayıfsa LLM yalnızca domain kararı verir.
   - Alakasızsa cevap: bot sadece Netmera kapsamındaki sorulara bakar.
   - İlgiliyse LLM'in ürettiği bağımsız arama sorgusuyla tekrar semantic probe
     yapılır.
5. Hâlâ güvenli cevap üretilemiyorsa mevcut graph devam eder:
   `memory -> orchestrator -> specialist -> gerekirse escalation`.

Bu katman `graph` başlangıcında çalışır. Başarılı olursa graph doğrudan `END`
olur; başarısız/emin değilse mevcut davranışı bozmaz.

Önemli ayarlar:

```bash
FAST_RAG_ENABLED=true
FAST_RAG_DIRECT_THRESHOLD=0.50
FAST_RAG_REWRITE_THRESHOLD=0.35
```

Performans notu: `semantic_probe` cross-encoder kullanmaz; yalnızca embedding
modeli + Chroma vektör araması yapar. Docker image build sırasında embedding
ve cross-encoder modelleri cache'e alınır; runtime warm-up ise modelleri
yalnızca local cache'ten yüklemeyi dener. Böylece deploy sonrası ilk kullanıcı
mesajı HuggingFace indirme/metadata bekleyişine takılmaz.
