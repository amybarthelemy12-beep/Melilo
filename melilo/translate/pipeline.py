"""Translator pipeline: chunk -> prompt OLMo -> emit pair records.

This is the v0 scaffold. The model loading path is intentionally minimal so we
can swap in vLLM later for batched inference without changing callers.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable, Iterator

from melilo.config import settings
from melilo.translate.prompts import build_messages


@dataclass
class Chunk:
    source_uri: str
    text: str


def chunk_text(source_uri: str, text: str, max_chars: int = 4000) -> Iterator[Chunk]:
    """Naive paragraph-aware chunker. Replace with a clause-aware splitter
    once we see real legal documents."""
    buf: list[str] = []
    size = 0
    for para in text.split("\n\n"):
        para = para.strip()
        if not para:
            continue
        if size + len(para) > max_chars and buf:
            yield Chunk(source_uri=source_uri, text="\n\n".join(buf))
            buf, size = [], 0
        buf.append(para)
        size += len(para)
    if buf:
        yield Chunk(source_uri=source_uri, text="\n\n".join(buf))


def _record(chunk: Chunk, translation: str) -> dict:
    return {
        "id": hashlib.sha256(chunk.text.encode("utf-8")).hexdigest(),
        "source_uri": chunk.source_uri,
        "source_text": chunk.text,
        "translation": translation,
        "translator_model": settings.translator_model,
        "prompt_version": settings.prompt_version,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


def translate_chunks(chunks: Iterable[Chunk], translator) -> Iterator[dict]:
    """`translator` is any callable taking messages -> str. Kept abstract so the
    HF transformers loader, vLLM, or a hosted endpoint can all plug in."""
    for chunk in chunks:
        messages = build_messages(chunk.text)
        translation = translator(messages)
        yield _record(chunk, translation)
