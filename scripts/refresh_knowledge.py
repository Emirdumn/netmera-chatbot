#!/usr/bin/env python3
"""Netmera bilgi tabanini yenile: scrape -> index -> (opsiyonel) cache flush.

Kullanim:
    python scripts/refresh_knowledge.py              # scrape + index
    python scripts/refresh_knowledge.py --scrape-only
    python scripts/refresh_knowledge.py --index-only
    python scripts/refresh_knowledge.py --flush-cache # redis QA cache temizle

Deploy sonrasi VM'de:
    python scripts/refresh_knowledge.py
    docker compose exec redis redis-cli FLUSHALL   # veya --flush-cache
    docker compose up -d --force-recreate customer_app widget_api
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _run(label: str, module: str) -> None:
    print(f"\n=== {label} ===")
    started = time.time()
    result = subprocess.run(
        [sys.executable, "-m", module],
        cwd=str(ROOT),
        check=False,
    )
    elapsed = time.time() - started
    if result.returncode != 0:
        raise SystemExit(f"{label} basarisiz (exit={result.returncode})")
    print(f"=== {label} bitti ({elapsed:.0f}s) ===")


def _count_files() -> dict[str, int]:
    counts = {}
    for name in ("user_guide", "dev_guide", "website"):
        folder = ROOT / "data" / name
        counts[name] = len(list(folder.glob("*.txt"))) if folder.exists() else 0
    return counts


def _flush_cache() -> None:
    print("\n=== Redis QA cache flush ===")
    result = subprocess.run(
        ["docker", "compose", "exec", "-T", "redis", "redis-cli", "FLUSHALL"],
        cwd=str(ROOT),
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print("Redis flush atlandi (docker/redis yok olabilir):", (result.stderr or result.stdout).strip())
        return
    print((result.stdout or "").strip() or "OK")


def main() -> int:
    parser = argparse.ArgumentParser(description="Netmera RAG bilgi tabani yenileme")
    parser.add_argument("--scrape-only", action="store_true")
    parser.add_argument("--index-only", action="store_true")
    parser.add_argument("--flush-cache", action="store_true", help="Islem sonunda Redis FLUSHALL")
    args = parser.parse_args()

    before = _count_files()
    print("Onceki dosya sayilari:", before)

    do_scrape = not args.index_only
    do_index = not args.scrape_only

    if do_scrape:
        _run("User Guide scrape", "data_pipeline.scraper_user_guide")
        _run("Developer Guide scrape", "data_pipeline.scraper_dev_guide")
        _run("Website scrape", "data_pipeline.scraper_website")

    after_scrape = _count_files()
    print("Scrape sonrasi:", after_scrape)

    if do_index:
        _run("Chroma index", "data_pipeline.indexer")

    if args.flush_cache:
        _flush_cache()

    print("\nBitti. Deploy icin chroma_db/ degisikliklerini commit edip VM'de pull edin,")
    print("veya VM uzerinde bu scripti dogrudan calistirin.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
