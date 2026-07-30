"""FAZ 13 — retrieval kalite ölçümü. 30 sabit Türkçe soru (10 user_guide,
10 dev_guide, 10 website): her soru query_builder_tool ile İngilizce'ye
çevrilip rag_search ile aranır. Ortalama en-iyi benzerlik ve isabet@5
(top-1 benzerlik >= HIT_BAR) raporlanır. Her FAZ 13 değişikliğinden
(hibrit arama, rerank, heading_boost) sonra tekrar çalıştırıp öncesi/sonrası
karşılaştırmak için kullanılır."""
import sys
from pathlib import Path

if __name__ == "__main__" and not __package__:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.query_builder_tool import query_builder_tool
from tools.rag_search_tool import rag_search

HIT_BAR = 0.5

QUESTIONS = {
    "user_guide": [
        "Kural bazlı segment nasıl oluşturulur?",
        "Otomasyon akışı nasıl kurulur?",
        "Push bildirim şablonu nasıl hazırlanır?",
        "E-posta kampanyası nasıl gönderilir?",
        "Kullanıcı listesi nasıl içe aktarılır?",
        "Feedback butonu nasıl oluşturulur?",
        "IYS izin yönetimi nasıl çalışır?",
        "Dashboard'da hangi metrikler var?",
        "Coğrafi konum bazlı mesajlaşma nasıl kurulur?",
        "Panelde kampanya nasıl planlanır?",
    ],
    "dev_guide": [
        "iOS SDK nasıl entegre edilir?",
        "Android SDK push token nasıl alınır?",
        "API key nereden alınır?",
        "REST API ile event nasıl gönderilir?",
        "Flutter SDK entegrasyonu nasıl yapılır?",
        "iOS push sertifikası nasıl yüklenir?",
        "SDK sürüm güncellemesi nasıl yapılır?",
        "React Native SDK kurulumu nasıl yapılır?",
        "Huawei push kurulumu nasıl yapılır?",
        "Netmera-Config.plist dosyası ne işe yarar?",
    ],
    "website": [
        "Netmera nedir?",
        "Churn rate nedir?",
        "Deep linking nedir?",
        "Netmera hangi sektörlere hizmet veriyor?",
        "LTV nedir?",
        "Conversion rate nedir?",
        "Omnichannel pazarlama nedir?",
        "A/B testing nedir?",
        "Netmera fiyatlandırması nasıl çalışıyor?",
        "Cohort analizi nedir?",
    ],
}


def _translated_query(question):
    result = query_builder_tool.invoke({"conversation": f"user: {question}", "profile_context": ""})
    if result.ok and result.data.get("query"):
        return result.data["query"]
    return question


def run_benchmark(use_translation=True, verbose=True):
    all_similarities = []
    hits = 0
    total = 0
    per_source_similarities = {s: [] for s in QUESTIONS}

    for source, questions in QUESTIONS.items():
        for q in questions:
            query = _translated_query(q) if use_translation else q
            result = rag_search.invoke({"query": query, "source": source, "top_k": 5})
            best_sim = result.data[0]["similarity"] if result.ok and result.data else 0.0
            all_similarities.append(best_sim)
            per_source_similarities[source].append(best_sim)
            total += 1
            if best_sim >= HIT_BAR:
                hits += 1
            if verbose:
                print(f"  [{source}] {q!r} -> query={query!r} sim={best_sim:.3f}")

    avg = sum(all_similarities) / len(all_similarities)
    hit_rate = hits / total

    print(f"\n{'Ceviri ILE' if use_translation else 'Ceviri OLMADAN (ham TR)'}:")
    for source, sims in per_source_similarities.items():
        print(f"  {source}: ortalama={sum(sims)/len(sims):.3f}")
    print(f"  TOPLAM ortalama en-iyi benzerlik: {avg:.3f}")
    print(f"  isabet@5 (sim >= {HIT_BAR}): {hits}/{total} (%{100*hit_rate:.0f})")
    return avg, hit_rate


if __name__ == "__main__":
    print("=== Ham Turkce sorgu (ceviri yok) ===")
    run_benchmark(use_translation=False, verbose=False)
    print("\n=== query_builder_tool ile cevrilmis sorgu ===")
    run_benchmark(use_translation=True, verbose=True)
