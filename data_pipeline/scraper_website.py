"""netmera.com — sitemap'lerdeki sayfaların görünür metnini çıkarır."""
import re
import sys
import time
from pathlib import Path

if __name__ == "__main__" and not __package__:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import requests
from bs4 import BeautifulSoup

from config.settings import WEBSITE_DIR

HEADERS = {"User-Agent": "Mozilla/5.0 (NetmeraBot egitim projesi)"}
DELAY = 0.3
SITEMAPS = [
    "https://netmera.com/page-sitemap.xml",
    "https://netmera.com/post-sitemap.xml",
]


def fetch(url):
    try:
        r = requests.get(url, headers=HEADERS, timeout=20)
        if r.status_code == 200:
            return r.text
        print(f"  ! {r.status_code}: {url}")
    except requests.RequestException as e:
        print(f"  ! hata: {url} ({e})")
    return None


def safe_name(url):
    name = re.sub(r"https?://", "", url).strip("/")
    return re.sub(r"[^a-zA-Z0-9._-]", "_", name)[:180]


def save(url, text):
    WEBSITE_DIR.mkdir(parents=True, exist_ok=True)
    path = WEBSITE_DIR / (safe_name(url) + ".txt")
    path.write_text(f"URL: {url}\n\n{text}", encoding="utf-8")


def scrape_website():
    print("== Web sitesi (netmera.com) ==")
    urls = set()
    for sm in SITEMAPS:
        xml = fetch(sm)
        if xml:
            urls.update(re.findall(r"<loc>(https://netmera\.com/[^<]*)</loc>", xml))
    urls = sorted(urls)
    print(f"{len(urls)} site sayfasi bulundu")
    for i, url in enumerate(urls, 1):
        html = fetch(url)
        if html:
            soup = BeautifulSoup(html, "lxml")
            for tag in soup(["script", "style", "nav", "footer", "header", "form"]):
                tag.decompose()
            text = re.sub(r"\n{3,}", "\n\n", soup.get_text(separator="\n").strip())
            if len(text) > 200:
                save(url, text)
        if i % 20 == 0:
            print(f"  {i}/{len(urls)}")
        time.sleep(DELAY)
    n = len(list(WEBSITE_DIR.glob("*.txt")))
    print(f"\nBitti: {n} sayfa {WEBSITE_DIR} klasorune kaydedildi.")


if __name__ == "__main__":
    scrape_website()
