"""URL bazli makale birlestirme — widget Help / Kaynaklar icin."""
import sys
from pathlib import Path

if __name__ == "__main__" and not __package__:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools import article_lookup


def test_public_doc_url_strips_md():
    assert (
        article_lookup.public_doc_url(
            "https://user.netmera.com/netmera-user-guide/ai-features/best-time-delivery.md"
        )
        == "https://user.netmera.com/netmera-user-guide/ai-features/best-time-delivery"
    )
    print("PASS: .md public url")


def test_assemble_article_from_chroma():
    url = "https://user.netmera.com/netmera-user-guide/ai-features/best-time-delivery.md"
    article = article_lookup.assemble_article(url)
    assert article is not None
    assert article.title
    assert len(article.body) >= 2
    assert not article.url.endswith(".md")
    assert "llms.txt" not in article.body[0].lower()
    # memo hit
    again = article_lookup.assemble_article(
        "https://user.netmera.com/netmera-user-guide/ai-features/best-time-delivery"
    )
    assert again is not None
    assert again.title == article.title
    print(f"PASS: assemble_article title={article.title!r} paragraphs={len(article.body)}")


def test_source_preview():
    preview = article_lookup.source_preview(
        "https://user.netmera.com/netmera-user-guide/ai-features/best-time-delivery.md"
    )
    assert preview["title"]
    assert preview["excerpt"]
    assert not preview["url"].endswith(".md")
    print("PASS: source_preview")


def main():
    tests = [
        test_public_doc_url_strips_md,
        test_assemble_article_from_chroma,
        test_source_preview,
    ]
    failed = 0
    for test in tests:
        try:
            test()
        except Exception as exc:
            failed += 1
            print(f"FAIL: {test.__name__} — {exc}")
    print()
    print("TUM TESTLER GECTI" if not failed else f"{failed} TEST BASARISIZ")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
