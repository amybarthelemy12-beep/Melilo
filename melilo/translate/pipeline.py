"""Translator pipeline: source text -> prompt OLMo -> emit pair records.

Four task types are supported, all driven through one `translate_document` entry
point. Chunking behavior is task-dependent:

- `pirac`, `brief`, `summary` : whole document is one record.
- `section_walkthrough`       : split by section header (`§`, `Sec.`, `SECTION`),
                                one record per section, with `section_id` captured.
                                Falls back to a single record if no headers found.

Not every (task, source) combination is valid — `VALID_TASK_SOURCE` is the
authoritative table and `validate_task_source` raises on a bad combo. Keep this
synced with `prompts.build_messages`.

The pair record schema matches the Neon `pairs` table (see melilo.store.neon).
Every record carries `source_bucket` ("public" or "internal") so we can trace
provenance back to which govparti bucket it came from.

The model loader stays abstract (any `callable(messages) -> str`) so we can swap in
vLLM or a hosted endpoint without touching this file.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, Iterable, Iterator

from melilo.config import settings
from melilo.translate.prompts import SourceType, TaskType, build_messages


Translator = Callable[[list[dict]], str]


# Authoritative validation table. Mirrors the dispatch in prompts.build_messages.
VALID_TASK_SOURCE: dict[str, set[str]] = {
    "pirac":               {"case"},
    "brief":               {"case"},
    "summary":             {"case", "statute", "bill", "regulation", "declassified"},
    "section_walkthrough": {"statute", "bill", "regulation", "declassified"},
}


def validate_task_source(task_type: TaskType, source_type: SourceType) -> None:
    valid_sources = VALID_TASK_SOURCE.get(task_type)
    if valid_sources is None:
        raise ValueError(
            f"unknown task_type {task_type!r}; valid: {sorted(VALID_TASK_SOURCE)}"
        )
    if source_type not in valid_sources:
        raise ValueError(
            f"task {task_type!r} does not apply to source_type {source_type!r}; "
            f"valid for this task: {sorted(valid_sources)}"
        )


@dataclass
class Chunk:
    text: str
    section_id: str | None = None  # set only for section_walkthrough chunks


# Match a line that looks like the start of a section. Conservative — we'd rather
# under-split (and fall back to whole-doc) than over-split arbitrary prose.
_SECTION_HEADER_RE = re.compile(
    r"^\s*(?:§|Sec\.|SEC\.|Section\s+\d|SECTION\s+\d)\s*\S",
    re.MULTILINE,
)
# Used to pull a compact section_id from the header line.
_SECTION_ID_RE = re.compile(
    r"^\s*("
    r"§\s*\S+"                              # § 1.5, § 1983, § 12.3(a)
    r"|Sec(?:tion|\.)\s+\S+"                # Sec. 1, Section 2(a)
    r"|SEC(?:TION)?\.?\s+\S+"               # SEC. 1, SECTION 3
    r")",
    re.IGNORECASE,
)


def _extract_section_id(text: str) -> str | None:
    first_line = text.lstrip().splitlines()[0] if text.strip() else ""
    m = _SECTION_ID_RE.match(first_line)
    if not m:
        return None
    return m.group(1).rstrip(".,;:").strip()


def chunk_text(text: str, max_chars: int = 4000) -> Iterator[Chunk]:
    """Paragraph-aware chunker. Kept for callers that explicitly want it;
    `translate_document` no longer uses it for summaries (whole-doc is the default
    so the model can see provisions in context)."""
    buf: list[str] = []
    size = 0
    for para in text.split("\n\n"):
        para = para.strip()
        if not para:
            continue
        if size + len(para) > max_chars and buf:
            yield Chunk(text="\n\n".join(buf))
            buf, size = [], 0
        buf.append(para)
        size += len(para)
    if buf:
        yield Chunk(text="\n\n".join(buf))


def chunk_by_section(text: str) -> Iterator[Chunk]:
    """Split on lines that look like section headers (§ / Sec. / SECTION ...).
    Yields one chunk per section with section_id captured. If no markers are
    detected, yields the whole document as a single chunk."""
    matches = list(_SECTION_HEADER_RE.finditer(text))
    if not matches:
        body = text.strip()
        if body:
            yield Chunk(text=body, section_id=None)
        return

    bounds = [m.start() for m in matches] + [len(text)]
    for i in range(len(matches)):
        body = text[bounds[i]: bounds[i + 1]].strip()
        if not body:
            continue
        yield Chunk(text=body, section_id=_extract_section_id(body))


def _record(
    chunk: Chunk,
    translation: str,
    task_type: TaskType,
    source_type: SourceType,
    source_bucket: str,
    source_key: str,
) -> dict:
    return {
        "id": hashlib.sha256(
            f"{task_type}|{source_type}|{source_bucket}|{source_key}|"
            f"{chunk.section_id or ''}|{chunk.text}".encode("utf-8")
        ).hexdigest(),
        "task_type": task_type,
        "source_type": source_type,
        "source_bucket": source_bucket,
        "source_key": source_key,
        "source_uri": settings.source_uri(source_bucket, source_key),
        "section_id": chunk.section_id,
        "source_text": chunk.text,
        "translation": translation,
        "translator_model": settings.translator_model,
        "prompt_version": settings.prompt_version,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


def _units_for_task(text: str, task_type: TaskType) -> Iterator[Chunk]:
    """A `unit` is the text that becomes one pair record."""
    if task_type == "section_walkthrough":
        yield from chunk_by_section(text=text)
        return
    yield Chunk(text=text.strip())


def translate_document(
    text: str,
    translator: Translator,
    task_type: TaskType,
    source_type: SourceType,
    source_bucket: str,
    source_key: str,
) -> Iterator[dict]:
    """Top-level entry: take one document, produce one or more pair records for the
    given task. `translator` is any callable taking messages -> str.

    `source_bucket` is the logical role ("public" or "internal"). `source_key` is
    the R2 object key. Together they uniquely identify the source within govparti.
    """
    validate_task_source(task_type, source_type)
    for unit in _units_for_task(text, task_type):
        messages = build_messages(unit.text, task_type=task_type, source_type=source_type)
        translation = translator(messages)
        yield _record(
            unit,
            translation,
            task_type=task_type,
            source_type=source_type,
            source_bucket=source_bucket,
            source_key=source_key,
        )
