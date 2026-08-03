"""HTTP istek/yanit bicimleri.

Bunlar widget'in TypeScript port tiplerinin (widget/src/ports/types.ts)
sunucu tarafindaki karsiligidir; ikisi birlikte degismelidir.
"""
from typing import Literal, Optional

from pydantic import BaseModel, Field


class SessionResponse(BaseModel):
    session_id: int
    #: Sonraki isteklerde `Authorization: Bearer <token>` olarak gonderilir.
    token: str


class SourceOut(BaseModel):
    title: str
    url: str
    #: RAG parcasindan kisa ozet — musteri neden bu kaynagin secildigini gorsun.
    excerpt: str = ""


class MessageOut(BaseModel):
    id: str
    author: Literal["user", "bot", "staff"]
    author_name: Optional[str] = None
    text: str
    sent_at: str
    sources: list[SourceOut] = Field(default_factory=list)


class ConversationOut(BaseModel):
    session_id: int
    messages: list[MessageOut] = Field(default_factory=list)
    status: str
    is_waiting: bool
    needs_contact_form: bool


class SendMessageIn(BaseModel):
    text: str = Field(min_length=1, max_length=4000)


class ContactIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    email: str = Field(min_length=3, max_length=254)


class ArticleOut(BaseModel):
    id: str
    title: str
    excerpt: str
    url: str
    body: list[str] = Field(default_factory=list)
    #: user_guide | dev_guide | website — UI etiketi icin.
    source: str = ""
