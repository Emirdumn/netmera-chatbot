"""Anonim oturum token'i.

Widget kullanicilari oturum acmaz; kimlikleri oturumun KENDISIDIR. Token,
session_id'nin HMAC ile imzalanmis halidir:

    <session_id>.<hmac_sha256(secret, session_id)>

Neden imza, neden tablo degil:
- Sema degisikligi gerekmez (yeni tablo/migration yok).
- Sunucu tarafinda durum tutulmaz, yatay olceklenir.
- Karsiligi: token iptal edilemez. Anonim bir destek oturumu icin kabul
  edilebilir; kalici/hesapli kimlik gerekirse gercek bir oturum tablosu
  gerekir (o zaman burasi degisir, cagiranlar degismez).

Token yalnizca "bu session_id'yi ben verdim" der; yetki tasimaz. Bir
saldirgan baska bir session_id'yi tahmin etse bile imzayi uretemez.
"""
import hmac
from hashlib import sha256
from typing import Optional

from config.settings import WIDGET_TOKEN_SECRET


def issue(session_id: int) -> str:
    signature = hmac.new(
        WIDGET_TOKEN_SECRET.encode(), str(session_id).encode(), sha256
    ).hexdigest()
    return f"{session_id}.{signature}"


def verify(token: str) -> Optional[int]:
    """Gecerliyse session_id, degilse None doner."""
    if not token or "." not in token:
        return None
    raw_id, _, signature = token.partition(".")
    if not raw_id.isdigit():
        return None
    expected = hmac.new(
        WIDGET_TOKEN_SECRET.encode(), raw_id.encode(), sha256
    ).hexdigest()
    if not hmac.compare_digest(expected, signature):
        return None
    return int(raw_id)
