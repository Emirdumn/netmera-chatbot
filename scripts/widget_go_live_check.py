#!/usr/bin/env python3
"""Widget canliya alma oncesi kontrol listesi.

Kullanim (VM'de veya lokal):
    python scripts/widget_go_live_check.py
    python scripts/widget_go_live_check.py --base https://netmera-helpdesk.X.X.X.X.sslip.io

Cikis kodu 0 = hazir, 1 = eksik/hatali.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _ok(msg: str) -> None:
    print(f"  ✓ {msg}")


def _fail(msg: str) -> None:
    print(f"  ✗ {msg}")


def _warn(msg: str) -> None:
    print(f"  ! {msg}")


def check_env() -> list[str]:
    errors: list[str] = []
    print("1) Ortam degiskenleri")
    enabled = os.environ.get("WIDGET_API_ENABLED", "false").lower() == "true"
    if not enabled:
        errors.append("WIDGET_API_ENABLED=false — widget API kapali")
        _fail("WIDGET_API_ENABLED acik degil")
    else:
        _ok("WIDGET_API_ENABLED=true")

    secret = os.environ.get("WIDGET_TOKEN_SECRET", "")
    if len(secret) < 32:
        errors.append("WIDGET_TOKEN_SECRET en az 32 karakter olmali")
        _fail(f"WIDGET_TOKEN_SECRET yetersiz (len={len(secret)})")
    else:
        _ok("WIDGET_TOKEN_SECRET uzunlugu yeterli")

    origins = [
        o.strip()
        for o in os.environ.get("WIDGET_ALLOWED_ORIGINS", "").split(",")
        if o.strip()
    ]
    if not origins:
        errors.append("WIDGET_ALLOWED_ORIGINS bos — hicbir dis site widget kullanamaz")
        _fail("WIDGET_ALLOWED_ORIGINS bos")
    else:
        _ok(f"WIDGET_ALLOWED_ORIGINS: {', '.join(origins)}")

    return errors


def _http_get(url: str, headers: dict | None = None) -> tuple[int, bytes]:
    req = Request(url, headers=headers or {}, method="GET")
    with urlopen(req, timeout=15) as resp:
        return resp.status, resp.read()


def _http_post(url: str, headers: dict | None = None) -> tuple[int, bytes]:
    req = Request(url, data=b"{}", headers={
        "Content-Type": "application/json",
        **(headers or {}),
    }, method="POST")
    with urlopen(req, timeout=30) as resp:
        return resp.status, resp.read()


def check_remote(base: str) -> list[str]:
    errors: list[str] = []
    base = base.rstrip("/")
    print(f"\n2) Uzak uc noktalar ({base})")

    if not base.startswith("https://"):
        errors.append("Widget HTTPS olmadan canliya acilamaz (mixed content)")
        _fail(f"base HTTPS degil: {base}")
    else:
        _ok("base HTTPS")

    try:
        status, body = _http_get(f"{base}/widget/widget.js")
        if status == 200 and (b"NetmeraWidget" in body or b"function" in body):
            _ok(f"/widget/widget.js ({len(body)} byte)")
        else:
            errors.append("/widget/widget.js beklenen icerikte degil")
            _fail(f"/widget/widget.js status={status}")
    except (HTTPError, URLError) as exc:
        errors.append(f"/widget/widget.js erisilemedi: {exc}")
        _fail(f"/widget/widget.js — {exc}")

    try:
        status, _ = _http_get(f"{base}/widget/embed-test.html")
        if status == 200:
            _ok("/widget/embed-test.html hazir")
        else:
            _warn(f"/widget/embed-test.html status={status} (opsiyonel)")
    except (HTTPError, URLError) as exc:
        _warn(f"/widget/embed-test.html yok — {exc}")

    try:
        status, body = _http_post(f"{base}/api/widget/session")
        if status == 200 and b"token" in body:
            _ok("/api/widget/session oturum aciyor")
        else:
            errors.append(f"/api/widget/session beklenmeyen yanit: {status}")
            _fail(f"/api/widget/session status={status}")
    except HTTPError as exc:
        if exc.code == 404:
            errors.append("API 404 — WIDGET_API_ENABLED kapali olabilir")
        else:
            errors.append(f"/api/widget/session HTTP {exc.code}")
        _fail(f"/api/widget/session — HTTP {exc.code}")
    except URLError as exc:
        errors.append(f"/api/widget/session erisilemedi: {exc}")
        _fail(f"/api/widget/session — {exc}")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Widget canliya alma kontrolu")
    parser.add_argument(
        "--base",
        default=os.environ.get(
            "WIDGET_PUBLIC_BASE",
            "https://netmera-helpdesk.43.229.92.6.sslip.io",
        ),
        help="Public HTTPS base URL (musteri/widget hostname)",
    )
    parser.add_argument(
        "--env-only",
        action="store_true",
        help="Yalnizca .env kontrolleri (uzak istek yok)",
    )
    args = parser.parse_args()

    # .env varsa yukle (python-dotenv yoksa elle parse)
    env_path = ROOT / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))

    print("Netmera Widget — canliya alma kontrolu\n")
    errors = check_env()
    if not args.env_only:
        errors.extend(check_remote(args.base))

    print()
    if errors:
        print("SONUC: HAZIR DEGIL")
        for err in errors:
            print(f"  - {err}")
        print(
            "\nAcmak icin ornek:\n"
            "  1) .env: WIDGET_API_ENABLED=true + WIDGET_TOKEN_SECRET + ORIGINS\n"
            "  2) docker compose up -d --force-recreate widget_api widget_build caddy\n"
            "  3) Bu scripti tekrar calistir\n"
            f"  4) Smoke: {args.base}/widget/embed-test.html"
        )
        return 1

    print("SONUC: CANLIYA HAZIR")
    print(f"  Embed:\n  <script src=\"{args.base}/widget/widget.js\" "
          f"data-api-base=\"{args.base}/api/widget\" defer></script>")
    print(f"  Smoke: {args.base}/widget/embed-test.html")
    return 0


if __name__ == "__main__":
    sys.exit(main())
