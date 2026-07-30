"""Router'ın kategori başına 5 soruyla sınıflama doğruluğunu ölçer.

FAZ 10'dan itibaren router_agent.py yerini agents/orchestrator.py'ye
bıraktı (bkz. PLAN_ORCHESTRATOR.md); eski dosya karşılaştırma için
v2_legacy/router_agent.py'de duruyor. Bu test hâlâ o eski, bağlamsız
router'ın saf sınıflandırma doğruluğunu ölçer — tek-mesaj sınıflandırma
kalitesinin FAZ 9-11 öncesi/sonrası karşılaştırması için."""
import sys
from pathlib import Path

if __name__ == "__main__" and not __package__:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from v2_legacy.router_agent import RouterAgent

TEST_CASES = {
    "sales": [
        "Netmera'nın fiyatı ne kadar?",
        "Demo talep etmek istiyorum",
        "Paketlerinizde neler var?",
        "Satın almak istiyorum, nasıl ilerleyebilirim?",
        "Kurumsal plan fiyatlandırması nasıl?",
    ],
    "support": [
        "Segment nasıl oluşturuyorum?",
        "Push bildirim şablonu nasıl hazırlanır?",
        "Panelde kampanya nasıl planlanır?",
        "Kullanıcı listesi nasıl içe aktarılır?",
        "Otomasyon akışı nasıl kurulur?",
    ],
    "technical": [
        "Android SDK entegrasyonu nasıl yapılır?",
        "API key nereden alınır?",
        "iOS push sertifikası nasıl yüklenir?",
        "REST API ile event nasıl gönderilir?",
        "SDK sürüm güncellemesi nasıl yapılır?",
    ],
    "general": [
        "Netmera nedir?",
        "Hangi sektörlere hizmet veriyorsunuz?",
        "Neden Netmera kullanmalıyım?",
        "Netmera hangi platformları destekliyor?",
        "Şirket ne zaman kuruldu?",
    ],
    "handoff_request": [
        "Bir yetkiliyle görüşmek istiyorum",
        "İnsan temsilciye bağlanabilir miyim?",
        "Müşteri temsilcisiyle konuşmak istiyorum",
        "Beni bir uzmana yönlendirir misiniz?",
        "Canlı destek hattına bağlanmak istiyorum",
    ],
}


def main():
    router = RouterAgent()
    total = 0
    correct = 0
    for expected_intent, questions in TEST_CASES.items():
        for q in questions:
            total += 1
            result = router.classify(q)
            is_correct = result.intent == expected_intent
            correct += int(is_correct)
            status = "OK" if is_correct else "X "
            print(f"[{status}] beklenen={expected_intent:16s} bulunan={result.intent:16s} | {q}")

    print(f"\nDogruluk: {correct}/{total} ({100 * correct / total:.0f}%)")


if __name__ == "__main__":
    main()
