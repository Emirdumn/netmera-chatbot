"""user.netmera.com/netmera-developer-guide — 190 sayfalık Developer Guide'i indirir."""
import re
import sys
import time
from pathlib import Path

if __name__ == "__main__" and not __package__:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import requests

from config.settings import DEV_GUIDE_DIR

HEADERS = {"User-Agent": "Mozilla/5.0 (NetmeraBot egitim projesi)"}
DELAY = 0.3
LLMS_TXT_URL = "https://user.netmera.com/netmera-developer-guide/llms.txt"


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
    DEV_GUIDE_DIR.mkdir(parents=True, exist_ok=True)
    path = DEV_GUIDE_DIR / (safe_name(url) + ".txt")
    path.write_text(f"URL: {url}\n\n{text}", encoding="utf-8")


def scrape_dev_guide():
    print("== Developer Guide (user.netmera.com) ==")
    llms = fetch(LLMS_TXT_URL)
    if not llms:
        print("llms.txt alinamadi!")
        return
    urls = sorted(set(re.findall(r"https://user\.netmera\.com/\S+\.md", llms)))
    print(f"{len(urls)} dokuman sayfasi bulundu")
    for i, url in enumerate(urls, 1):
        md = fetch(url)
        if md:
            save(url, md)
        if i % 20 == 0:
            print(f"  {i}/{len(urls)}")
        time.sleep(DELAY)
    n = len(list(DEV_GUIDE_DIR.glob("*.txt")))
    print(f"\nBitti: {n} sayfa {DEV_GUIDE_DIR} klasorune kaydedildi.")


if __name__ == "__main__":
    scrape_dev_guide()
