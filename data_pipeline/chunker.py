"""Başlık-duyarlı Markdown chunker.

Metni #/##/### başlıklarına göre bölümlere ayırır, her parçanın başına
başlık zincirini ekler (örn. "iOS > Push Notifications > Media Push").
1500 karakteri aşan bölümler paragraf sınırından, kod bloklarını
bozmadan, 150 karakter örtüşmeyle alt-parçalara ayrılır.
"""
import re

MAX_CHUNK_CHARS = 1500
OVERLAP_CHARS = 150
MIN_CHUNK_CHARS = 80

HEADING_RE = re.compile(r"^(#{1,3})\s+(.+?)\s*$")
FENCE_RE = re.compile(r"^```")
HTML_TAG_RE = re.compile(r"<[^>]+>")


def _split_sections(text):
    """Metni başlıklara göre (heading_path, title, body) bölümlerine ayırır."""
    sections = []
    stack = []  # [(level, title), ...]
    current_body = []
    in_code_fence = False
    heading_path, title = "", None
    started = False

    def flush():
        body = "\n".join(current_body).strip()
        sections.append((heading_path, title, body))

    for line in text.splitlines():
        stripped = line.strip()
        if FENCE_RE.match(stripped):
            in_code_fence = not in_code_fence
            current_body.append(line)
            started = True
            continue
        m = None if in_code_fence else HEADING_RE.match(line)
        if m:
            if started:
                flush()
            level = len(m.group(1))
            new_title = HTML_TAG_RE.sub("", m.group(2)).strip()
            while stack and stack[-1][0] >= level:
                stack.pop()
            stack.append((level, new_title))
            heading_path = " > ".join(t for _, t in stack)
            title = new_title
            current_body = []
            started = True
        else:
            current_body.append(line)
            started = True

    if started:
        flush()
    return sections


def _split_blocks(body):
    """Kod bloklarını atomik birim olarak koruyarak paragraf bloklarına ayırır."""
    blocks = []
    buf = []
    in_fence = False
    for line in body.splitlines():
        is_fence_line = bool(FENCE_RE.match(line.strip()))
        if is_fence_line and not in_fence:
            if buf:
                blocks.append("\n".join(buf).strip())
                buf = []
            in_fence = True
            buf.append(line)
        elif is_fence_line and in_fence:
            buf.append(line)
            in_fence = False
            blocks.append("\n".join(buf).strip())
            buf = []
        elif in_fence:
            buf.append(line)
        elif line.strip() == "":
            if buf:
                blocks.append("\n".join(buf).strip())
                buf = []
        else:
            buf.append(line)
    if buf:
        blocks.append("\n".join(buf).strip())
    return [b for b in blocks if b]


def _pack_blocks(blocks, max_chars=MAX_CHUNK_CHARS, overlap_chars=OVERLAP_CHARS):
    """Bloklari max_chars'i asmayacak sekilde paketler, aralara overlap birakir."""
    chunks = []
    current = ""
    for block in blocks:
        candidate = f"{current}\n\n{block}" if current else block
        if not current or len(candidate) <= max_chars:
            current = candidate
        else:
            chunks.append(current)
            tail = current[-overlap_chars:]
            current = f"{tail}\n\n{block}"
    if current:
        chunks.append(current)
    return chunks


def chunk_markdown(text, fallback_title=None):
    """Markdown metnini {"text", "heading_path", "title"} sozlukleri listesine boler."""
    chunks = []
    for heading_path, title, body in _split_sections(text):
        if not body:
            continue
        if len(body) > MAX_CHUNK_CHARS:
            sub_bodies = _pack_blocks(_split_blocks(body))
        else:
            sub_bodies = [body]
        for sub in sub_bodies:
            if len(sub.strip()) < MIN_CHUNK_CHARS:
                continue
            prefixed = f"{heading_path}\n\n{sub}" if heading_path else sub
            chunks.append({
                "text": prefixed,
                "heading_path": heading_path,
                "title": title or fallback_title,
            })
    return chunks
