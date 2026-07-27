"""Netmera dokümantasyonunu ve web sitesini indirip data/ klasörüne kaydeder."""
import re
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup

HEADERS = {"User-Agent": "Mozilla/5.0 (NetmeraBot egitim projesi)"}
DATA_DIR = Path("data")
DELAY = 0.3  # siteyi yormamak icin istekler arasi bekleme (saniye)


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


def save(folder, url, text):
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / (safe_name(url) + ".txt")
    path.write_text(f"URL: {url}\n\n{text}", encoding="utf-8")


def scrape_docs():
    """user.netmera.com — GitBook, tum sayfalar hazir Markdown olarak sunuluyor."""
    print("== Dokumantasyon (user.netmera.com) ==")
    llms = fetch("https://user.netmera.com/llms.txt")
    if not llms:
        print("llms.txt alinamadi!")
        return
    urls = sorted(set(re.findall(r"https://user\.netmera\.com/\S+\.md", llms)))
    print(f"{len(urls)} dokuman sayfasi bulundu")
    for i, url in enumerate(urls, 1):
        md = fetch(url)
        if md:
            save(DATA_DIR / "docs", url, md)
        if i % 20 == 0:
            print(f"  {i}/{len(urls)}")
        time.sleep(DELAY)


def scrape_site():
    """netmera.com — sitemap'lerdeki sayfalarin gorunur metnini cikarir."""
    print("== Web sitesi (netmera.com) ==")
    urls = set()
    for sm in ["https://netmera.com/page-sitemap.xml",
               "https://netmera.com/post-sitemap.xml"]:
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
            if len(text) > 200:  # bos/anlamsiz sayfalari atla
                save(DATA_DIR / "site", url, text)
        if i % 20 == 0:
            print(f"  {i}/{len(urls)}")
        time.sleep(DELAY)


if __name__ == "__main__":
    scrape_docs()
    scrape_site()
    n = len(list(DATA_DIR.rglob("*.txt")))
    print(f"\nBitti: {n} sayfa data/ klasorune kaydedildi.")
