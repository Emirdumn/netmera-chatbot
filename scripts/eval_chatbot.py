#!/usr/bin/env python3
"""Local chatbot eval — kalite, latency, LLM cagri sayisi.

Kullanim:
    # Canli eval (OPENROUTER_API_KEY / GEMINI_API_KEY + STAFF_DEMO_PASSWORD gerekir)
    venv/bin/python scripts/eval_chatbot.py

    # Sadece soru seti / kriter dogrulamasi (LLM yok)
    venv/bin/python scripts/eval_chatbot.py --dry-run

Cikti:
    reports/eval-YYYYMMDD-HHMM.json
    reports/eval-YYYYMMDD-HHMM.md
"""
from __future__ import annotations

import argparse
import io
import json
import os
import re
import statistics
import sys
import time
from contextlib import redirect_stdout
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# .env varsa yukle (canli eval icin API key)
try:
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
except Exception:
    pass

# settings import'undan once zorunlu env (import-time _required_env)
os.environ.setdefault(
    "STAFF_DEMO_PASSWORD",
    os.environ.get("STAFF_DEMO_PASSWORD")
    or "eval-staff-password-en-az-onalti",
)

LLM_CALL_RE = re.compile(
    r"🧠 LLM_CALL "
    r"tier=(?P<tier>\S+) "
    r"model=(?P<model>\S+) "
    r"call_site=(?P<call_site>\S+) "
    r"latency_ms=(?P<latency_ms>[\d.]+) "
    r"ok=(?P<ok>\S+)"
)

# --------------------------------------------------------------------------
# 40 soruluk suite
# --------------------------------------------------------------------------

EVAL_CASES: list[dict] = [
    # --- 15 User Guide how-to ---
    {"id": "ug01", "category": "user_guide", "q": "Push kampanyası nasıl oluşturulur?", "expect": {"sources_min": 1, "brain": False, "handoff": False}},
    {"id": "ug02", "category": "user_guide", "q": "Kural bazlı segment nasıl oluşturulur?", "expect": {"sources_min": 1, "brain": False, "handoff": False}},
    {"id": "ug03", "category": "user_guide", "q": "Journey builder ile otomatik akış nasıl kurulur?", "expect": {"sources_min": 1, "brain": False, "handoff": False}},
    {"id": "ug04", "category": "user_guide", "q": "E-posta şablonu nasıl oluşturulur?", "expect": {"sources_min": 1, "brain": False, "handoff": False}},
    {"id": "ug05", "category": "user_guide", "q": "SMS kampanyası nasıl gönderilir?", "expect": {"sources_min": 1, "brain": False, "handoff": False}},
    {"id": "ug06", "category": "user_guide", "q": "In-app mesaj nasıl oluşturulur?", "expect": {"sources_min": 1, "brain": False, "handoff": False}},
    {"id": "ug07", "category": "user_guide", "q": "A/B test kampanyası nasıl yapılır?", "expect": {"sources_min": 1, "brain": False, "handoff": False}},
    {"id": "ug08", "category": "user_guide", "q": "Geofence ile lokasyon bazlı bildirim nasıl ayarlanır?", "expect": {"sources_min": 1, "brain": False, "handoff": False}},
    {"id": "ug09", "category": "user_guide", "q": "Kullanıcı profiline özel attribute nasıl eklenir?", "expect": {"sources_min": 1, "brain": False, "handoff": False}},
    {"id": "ug10", "category": "user_guide", "q": "Raporlarda delivery rate nereden bakılır?", "expect": {"sources_min": 1, "brain": False, "handoff": False}},
    {"id": "ug11", "category": "user_guide", "q": "IYS izin yönetimi nasıl yapılır?", "expect": {"sources_min": 1, "brain": False, "handoff": False}},
    {"id": "ug12", "category": "user_guide", "q": "Web push nasıl etkinleştirilir?", "expect": {"sources_min": 1, "brain": False, "handoff": False}},
    {"id": "ug13", "category": "user_guide", "q": "Silent push nedir ve nasıl kullanılır?", "expect": {"sources_min": 1, "brain": False, "handoff": False}},
    {"id": "ug14", "category": "user_guide", "q": "Kampanya zamanlaması (best time) nasıl ayarlanır?", "expect": {"sources_min": 1, "brain": False, "handoff": False}},
    {"id": "ug15", "category": "user_guide", "q": "Audience export nasıl alınır?", "expect": {"sources_min": 1, "brain": False, "handoff": False}},
    # --- 10 Developer Guide ---
    {"id": "dg01", "category": "dev_guide", "q": "iOS SDK entegrasyonu nasıl yapılır?", "expect": {"sources_min": 1, "brain": False, "handoff": False}},
    {"id": "dg02", "category": "dev_guide", "q": "Android'de push notification permission nasıl istenir?", "expect": {"sources_min": 1, "brain": False, "handoff": False}},
    {"id": "dg03", "category": "dev_guide", "q": "Flutter Netmera SDK nasıl kurulur?", "expect": {"sources_min": 1, "brain": False, "handoff": False}},
    {"id": "dg04", "category": "dev_guide", "q": "React Native push token nasıl alınır?", "expect": {"sources_min": 1, "brain": False, "handoff": False}},
    {"id": "dg05", "category": "dev_guide", "q": "Custom event nasıl gönderilir?", "expect": {"sources_min": 1, "brain": False, "handoff": False}},
    {"id": "dg06", "category": "dev_guide", "q": "User ID set etmek için hangi API kullanılır?", "expect": {"sources_min": 1, "brain": False, "handoff": False}},
    {"id": "dg07", "category": "dev_guide", "q": "Deep link handling iOS'ta nasıl yapılır?", "expect": {"sources_min": 1, "brain": False, "handoff": False}},
    {"id": "dg08", "category": "dev_guide", "q": "REST API ile bildirim gönderme örneği nedir?", "expect": {"sources_min": 1, "brain": False, "handoff": False}},
    {"id": "dg09", "category": "dev_guide", "q": "Huawei push entegrasyonu nasıl yapılır?", "expect": {"sources_min": 1, "brain": False, "handoff": False}},
    {"id": "dg10", "category": "dev_guide", "q": "Web SDK nasıl initialize edilir?", "expect": {"sources_min": 1, "brain": False, "handoff": False}},
    # --- 5 website / genel ---
    {"id": "ws01", "category": "website", "q": "Netmera nedir?", "expect": {"sources_min": 1, "brain": False, "handoff": False}},
    {"id": "ws02", "category": "website", "q": "Netmera hangi sektörlere hizmet veriyor?", "expect": {"sources_min": 1, "brain": False, "handoff": False}},
    {"id": "ws03", "category": "website", "q": "Omnichannel marketing Netmera'da ne anlama geliyor?", "expect": {"sources_min": 1, "brain": False, "handoff": False}},
    {"id": "ws04", "category": "website", "q": "Netmera customer journey orchestration nedir?", "expect": {"sources_min": 1, "brain": False, "handoff": False}},
    {"id": "ws05", "category": "website", "q": "Netmera'nın temel özellikleri nelerdir?", "expect": {"sources_min": 1, "brain": False, "handoff": False}},
    # --- 5 off-topic (ucuz yol: domain_guard, llm<=2, brain yok) ---
    {"id": "ot01", "category": "off_topic", "q": "Bugün hava nasıl?", "expect": {"handoff": False, "off_topic": True, "agent_name": "domain_guard", "llm_max": 2, "brain": False}},
    {"id": "ot02", "category": "off_topic", "q": "En yakın pizza restoranı nerede?", "expect": {"handoff": False, "off_topic": True, "agent_name": "domain_guard", "llm_max": 2, "brain": False}},
    {"id": "ot03", "category": "off_topic", "q": "Bitcoin fiyatı ne kadar?", "expect": {"handoff": False, "off_topic": True, "agent_name": "domain_guard", "llm_max": 2, "brain": False}},
    {"id": "ot04", "category": "off_topic", "q": "Python'da list comprehension nasıl yazılır?", "expect": {"handoff": False, "off_topic": True, "agent_name": "domain_guard", "llm_max": 2, "brain": False}},
    {"id": "ot05", "category": "off_topic", "q": "Galatasaray maçı kaç kaç bitti?", "expect": {"handoff": False, "off_topic": True, "agent_name": "domain_guard", "llm_max": 2, "brain": False}},
    # --- 5 sales / handoff / problem ---
    {"id": "rt01", "category": "routing", "q": "Bir temsilciye bağlanmak istiyorum", "expect": {"needs_contact_form": True}},
    {"id": "rt02", "category": "routing", "q": "Netmera fiyatlandırma paketleri nedir? Demo almak istiyorum", "expect": {"handoff_or_sales": True}},
    {"id": "rt03", "category": "routing", "q": "Push bildirimleri çalışmıyor, 401 hatası alıyorum", "expect": {"handoff_or_answer": True}},
    {"id": "rt04", "category": "routing", "q": "Müşteri temsilcisiyle görüşmek istiyorum lütfen", "expect": {"needs_contact_form": True}},
    {"id": "rt05", "category": "routing", "q": "Satın alma ve ücret bilgisi alabilir miyim?", "expect": {"handoff_or_sales": True}},
]


@dataclass
class LlmCall:
    tier: str
    model: str
    call_site: str
    latency_ms: float
    ok: bool


@dataclass
class CaseResult:
    id: str
    category: str
    question: str
    elapsed_ms: float
    agent_name: str = ""
    answer_empty: bool = True
    answer_preview: str = ""
    sources_count: int = 0
    source_urls: list[str] = field(default_factory=list)
    escalated: bool = False
    needs_contact_form: bool = False
    brain_called: bool = False
    llm_calls: list[dict] = field(default_factory=list)
    llm_call_count: int = 0
    checks: dict = field(default_factory=dict)
    passed: bool = True
    error: str = ""


def parse_llm_calls(log_text: str) -> list[LlmCall]:
    calls = []
    for match in LLM_CALL_RE.finditer(log_text):
        calls.append(
            LlmCall(
                tier=match.group("tier"),
                model=match.group("model"),
                call_site=match.group("call_site"),
                latency_ms=float(match.group("latency_ms")),
                ok=match.group("ok").lower() == "true",
            )
        )
    return calls


def validate_suite() -> list[str]:
    errors = []
    if len(EVAL_CASES) != 40:
        errors.append(f"beklenen 40 soru, bulunan {len(EVAL_CASES)}")
    counts = {}
    for case in EVAL_CASES:
        counts[case["category"]] = counts.get(case["category"], 0) + 1
    expected = {
        "user_guide": 15,
        "dev_guide": 10,
        "website": 5,
        "off_topic": 5,
        "routing": 5,
    }
    for key, n in expected.items():
        if counts.get(key) != n:
            errors.append(f"{key}: beklenen {n}, bulunan {counts.get(key, 0)}")
    ids = [c["id"] for c in EVAL_CASES]
    if len(ids) != len(set(ids)):
        errors.append("duplicate case id")
    return errors


def _percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    k = (len(ordered) - 1) * p
    f = int(k)
    c = min(f + 1, len(ordered) - 1)
    if f == c:
        return ordered[f]
    return ordered[f] + (ordered[c] - ordered[f]) * (k - f)


def evaluate_case(case: dict) -> CaseResult:
    from app_services import chat_service

    buf = io.StringIO()
    started = time.perf_counter()
    result = CaseResult(
        id=case["id"],
        category=case["category"],
        question=case["q"],
        elapsed_ms=0.0,
    )
    try:
        with redirect_stdout(buf):
            session_id = chat_service.create_session("tr")
            turn = chat_service.send_message(session_id, case["q"])
            convo = chat_service.load_conversation(session_id)
        elapsed_ms = (time.perf_counter() - started) * 1000
        result.elapsed_ms = elapsed_ms
        result.escalated = bool(turn.escalated)
        result.needs_contact_form = bool(convo.needs_contact_form)

        assistants = [m for m in convo.messages if m.get("role") == "assistant"]
        last = assistants[-1] if assistants else {}
        content = (last.get("content") or "").strip()
        result.answer_empty = not bool(content)
        result.answer_preview = content[:240]
        result.agent_name = last.get("agent_name") or ""
        sources = last.get("sources") or []
        result.sources_count = len(sources)
        result.source_urls = list(sources)[:5]

        calls = parse_llm_calls(buf.getvalue())
        result.llm_calls = [asdict(c) for c in calls]
        result.llm_call_count = len(calls)
        result.brain_called = any(c.tier == "brain" for c in calls) or any(
            "brain" in c.call_site for c in calls
        )

        expect = case.get("expect") or {}
        checks = {}
        if "sources_min" in expect:
            checks["sources_min"] = result.sources_count >= expect["sources_min"]
        if expect.get("handoff") is False:
            checks["no_handoff"] = (not result.escalated) and (not result.needs_contact_form)
        if expect.get("brain") is False:
            checks["no_brain"] = not result.brain_called
        if expect.get("needs_contact_form"):
            checks["needs_contact_form"] = result.needs_contact_form
        if expect.get("agent_name"):
            checks["agent_name"] = result.agent_name == expect["agent_name"]
        if "llm_max" in expect:
            checks["llm_max"] = result.llm_call_count <= int(expect["llm_max"])
        if expect.get("off_topic"):
            # off-topic: handoff yok + cevap bos degil
            checks["off_topic_no_handoff"] = (not result.escalated) and (not result.needs_contact_form)
            checks["off_topic_answered"] = not result.answer_empty
        if expect.get("handoff_or_sales"):
            checks["handoff_or_sales"] = (
                result.needs_contact_form
                or result.escalated
                or "sales" in (result.agent_name or "")
                or not result.answer_empty
            )
        if expect.get("handoff_or_answer"):
            checks["handoff_or_answer"] = (
                result.needs_contact_form
                or result.escalated
                or (not result.answer_empty)
            )
        checks["answer_not_empty"] = not result.answer_empty
        result.checks = checks
        result.passed = all(checks.values()) if checks else True
    except Exception as exc:
        result.elapsed_ms = (time.perf_counter() - started) * 1000
        result.error = f"{type(exc).__name__}: {exc}"
        result.passed = False
        result.checks = {"error": False}
    return result


def write_reports(
    results: list[CaseResult],
    out_dir: Path,
    stamp: str,
    *,
    dry_run: bool = False,
) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / f"eval-{stamp}.json"
    md_path = out_dir / f"eval-{stamp}.md"

    elapsed = [r.elapsed_ms for r in results]
    llm_counts = [r.llm_call_count for r in results]
    brain_count = sum(1 for r in results if r.brain_called)
    passed = sum(1 for r in results if r.passed)
    rag_cases = [r for r in results if r.category in ("user_guide", "dev_guide", "website")]
    rag_with_sources = sum(1 for r in rag_cases if r.sources_count >= 1)
    off = [r for r in results if r.category == "off_topic"]
    off_ok = sum(1 for r in off if r.checks.get("off_topic_no_handoff"))
    off_cheap = sum(
        1
        for r in off
        if r.agent_name == "domain_guard"
        and r.llm_call_count <= 2
        and not r.brain_called
    )
    contact = [r for r in results if (r.id in ("rt01", "rt04"))]
    contact_ok = sum(1 for r in contact if r.needs_contact_form)
    doc_no_brain = [
        r for r in results
        if r.category in ("user_guide", "dev_guide", "website") and not r.brain_called
    ]

    summary = {
        "stamp": stamp,
        "dry_run": dry_run,
        "total": len(results),
        "passed": passed,
        "failed": len(results) - passed,
        "p50_latency_ms": round(_percentile(elapsed, 0.50), 1),
        "p95_latency_ms": round(_percentile(elapsed, 0.95), 1),
        "avg_latency_ms": round(statistics.mean(elapsed), 1) if elapsed else 0,
        "avg_llm_calls": round(statistics.mean(llm_counts), 2) if llm_counts else 0,
        "brain_cases": brain_count,
        "rag_with_sources": f"{rag_with_sources}/{len(rag_cases)}",
        "off_topic_no_handoff": f"{off_ok}/{len(off)}",
        "off_topic_cheap_path": f"{off_cheap}/{len(off)}",
        "explicit_handoff_contact_form": f"{contact_ok}/{len(contact)}",
        "doc_questions_without_brain": f"{len(doc_no_brain)}/{len(rag_cases)}",
    }

    payload = {
        "summary": summary,
        "cases": [asdict(r) for r in results],
    }
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        f"# Chatbot Eval — {stamp}",
        "",
    ]
    if dry_run:
        lines += [
            "> **Dry-run:** suite doğrulandı; LLM çağrılmadı. "
            "Latency / sources / handoff / BRAIN metrikleri ölçülmedi.",
            "",
            "## Suite",
            "",
            f"- Toplam soru: **{summary['total']}** (kategori dağılımı geçerli)",
            "- Canlı metrikler için API key ile `scripts/eval_chatbot.py` çalıştırın.",
            "",
            "## Case listesi",
            "",
            "| id | cat | question |",
            "|---|---|---|",
        ]
        for r in results:
            q = r.question.replace("|", "\\|")
            lines.append(f"| {r.id} | {r.category} | {q} |")
    else:
        lines += [
            "## Özet",
            "",
            f"- Toplam: **{summary['total']}** | Geçen: **{summary['passed']}** | Kalan: **{summary['failed']}**",
            f"- p50 latency: **{summary['p50_latency_ms']} ms**",
            f"- p95 latency: **{summary['p95_latency_ms']} ms**",
            f"- Ortalama latency: **{summary['avg_latency_ms']} ms**",
            f"- Ortalama LLM çağrısı: **{summary['avg_llm_calls']}**",
            f"- BRAIN çağrılan case: **{summary['brain_cases']}**",
            f"- RAG sources≥1: **{summary['rag_with_sources']}**",
            f"- Off-topic handoff yok: **{summary['off_topic_no_handoff']}**",
            f"- Off-topic ucuz yol (domain_guard, llm≤2, brain=0): **{summary['off_topic_cheap_path']}**",
            f"- Açık temsilci → contact form: **{summary['explicit_handoff_contact_form']}**",
            f"- Doküman sorusunda BRAIN=0: **{summary['doc_questions_without_brain']}**",
            "",
            "## Başarı kriterleri",
            "",
            "| Kriter | Sonuç |",
            "|---|---|",
            f"| RAG sources ≥ 1 | {summary['rag_with_sources']} |",
            f"| Off-topic handoff yok | {summary['off_topic_no_handoff']} |",
            f"| Off-topic ucuz yol | {summary['off_topic_cheap_path']} |",
            f"| Temsilci isteğinde contact form | {summary['explicit_handoff_contact_form']} |",
            f"| Normal dokümanda BRAIN=0 | {summary['doc_questions_without_brain']} |",
            "",
            "## Case detayları",
            "",
            "| id | cat | ms | llm | brain | sources | agent | pass |",
            "|---|---|---:|---:|:---:|---:|---|:---:|",
        ]
        for r in results:
            lines.append(
                f"| {r.id} | {r.category} | {r.elapsed_ms:.0f} | {r.llm_call_count} | "
                f"{'Y' if r.brain_called else ''} | {r.sources_count} | "
                f"{r.agent_name or '-'} | {'✓' if r.passed else '✗'} |"
            )

        fails = [r for r in results if not r.passed]
        if fails:
            lines += ["", "## Başarısız case'ler", ""]
            for r in fails:
                lines.append(f"### {r.id} — {r.question}")
                lines.append(f"- checks: `{r.checks}`")
                if r.error:
                    lines.append(f"- error: `{r.error}`")
                lines.append(f"- preview: {r.answer_preview[:180]}")
                lines.append("")

    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, md_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Netmera chatbot local eval")
    parser.add_argument("--dry-run", action="store_true", help="Sadece suite dogrula, LLM cagirma")
    parser.add_argument("--limit", type=int, default=0, help="Ilk N soruyu calistir (0=hepsi)")
    parser.add_argument("--out", default=str(ROOT / "reports"), help="Rapor klasoru")
    args = parser.parse_args()

    errors = validate_suite()
    if errors:
        print("SUITE HATALI:")
        for err in errors:
            print(f"  - {err}")
        return 1
    print(f"Suite OK: {len(EVAL_CASES)} soru")

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M")
    out_dir = Path(args.out)

    if args.dry_run:
        # Dry-run raporu — metrikler 0, suite dogrulandi.
        results = [
            CaseResult(
                id=c["id"],
                category=c["category"],
                question=c["q"],
                elapsed_ms=0,
                checks={"dry_run": True},
                passed=True,
            )
            for c in EVAL_CASES
        ]
        json_path, md_path = write_reports(
            results, out_dir, stamp + "-dry", dry_run=True
        )
        print(f"Dry-run raporlari:\n  {json_path}\n  {md_path}")
        return 0

    provider = os.environ.get("LLM_PROVIDER", "openrouter")
    key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if provider == "openrouter":
        if not key or key.startswith("sk-test") or key in {"changeme", "dummy", "test"}:
            print(
                "Gecerli OPENROUTER_API_KEY yok — .env'e gercek key koyun "
                "veya --dry-run kullanin."
            )
            return 2
    if provider == "gemini" and not os.environ.get("GEMINI_API_KEY"):
        print("GEMINI_API_KEY yok — once .env doldurun veya --dry-run kullanin.")
        return 2

    cases = EVAL_CASES[: args.limit] if args.limit else EVAL_CASES
    results: list[CaseResult] = []
    for i, case in enumerate(cases, 1):
        print(f"[{i}/{len(cases)}] {case['id']} {case['q'][:60]}...", flush=True)
        result = evaluate_case(case)
        status = "PASS" if result.passed else "FAIL"
        print(
            f"  → {status} {result.elapsed_ms:.0f}ms llm={result.llm_call_count} "
            f"brain={result.brain_called} sources={result.sources_count} "
            f"agent={result.agent_name or '-'}",
            flush=True,
        )
        results.append(result)

    json_path, md_path = write_reports(results, out_dir, stamp, dry_run=False)
    print(f"\nRaporlar:\n  {json_path}\n  {md_path}")
    failed = sum(1 for r in results if not r.passed)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
