"""FAZ 12 doğrulaması: bağlama bağlı takip sorusu ("peki ya android
tarafında?") önceki konuyu koruyarak doğru sonucu getiriyor mu, ReAct
izinde (reasoning_trace) arama adımları görülüyor mu."""
import sys
from pathlib import Path

if __name__ == "__main__" and not __package__:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agents.technical_agent import TechnicalAgent

ALL_PASS = True


def check(label, condition, detail=""):
    global ALL_PASS
    status = "PASS" if condition else "FAIL"
    ALL_PASS = ALL_PASS and condition
    print(f"[{status}] {label}" + (f" — {detail}" if detail else ""))


def main():
    agent = TechnicalAgent()

    state = {
        "messages": [
            {"role": "user", "content": "iOS SDK entegrasyonu nasıl yapılır?"},
            {"role": "assistant", "content": "iOS SDK entegrasyonu icin Netmera-Config.plist dosyasini projenize eklemeniz gerekiyor..."},
            {"role": "user", "content": "peki ya android tarafında?"},
        ],
        "customer_profile": {},
        "case_notes": {},
        "language": "tr",
    }

    result = agent.run(state)
    trace = result.get("reasoning_trace", [])

    print("Cevap:", result["answer"][:200])
    print("Sources:", result["sources"])
    print("Trace:")
    for step in trace:
        print(f"  tur {step['iteration']}: query={step['query']!r}  similarity={step['similarity']}")

    first_query = trace[0]["query"].lower() if trace else ""
    check(
        "ilk sorgu 'android' baglamini yakaladi (takip sorusu tek basina anlamsiz)",
        "android" in first_query,
        f"first_query={first_query!r}",
    )
    check("agent cevap verebildi (can_answer=True)", result["can_answer"])
    check(
        "cevap Android ile ilgili (SDK entegrasyonu iceriyor)",
        "android" in result["answer"].lower(),
        f"answer={result['answer'][:150]!r}",
    )
    check("trace en az 1 arama adimi iceriyor", len(trace) >= 1, f"adim sayisi={len(trace)}")
    print(f"\nToplam arama turu: {len(trace)} (esik altinda kalirsa otomatik ikinci tur denenir)")

    print("\nTum kontroller basarili." if ALL_PASS else "\nBAZI KONTROLLER BASARISIZ.")


if __name__ == "__main__":
    main()
