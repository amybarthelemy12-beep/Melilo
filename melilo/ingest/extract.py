"""Extract plain text from a source document.

Dispatches by file extension. PDFs go through pypdfium2, HTML through
selectolax, everything else is decoded as UTF-8 with replacement.
"""
from __future__ import annotations

import io
from pathlib import PurePosixPath


def extract(key: str, body: bytes) -> str:
    suffix = PurePosixPath(key).suffix.lower()
    if suffix == ".pdf":
        return _pdf(body)
    if suffix in {".html", ".htm"}:
        return _html(body)
    return body.decode("utf-8", errors="replace")


def _pdf(body: bytes) -> str:
    import pypdfium2 as pdfium

    pdf = pdfium.PdfDocument(io.BytesIO(body))
    out: list[str] = []
    for page in pdf:
        textpage = page.get_textpage()
        out.append(textpage.get_text_range())
        textpage.close()
        page.close()
    pdf.close()
    return "\n\n".join(out)


def _html(body: bytes) -> str:
    from selectolax.parser import HTMLParser

    tree = HTMLParser(body.decode("utf-8", errors="replace"))
    for tag in tree.css("script, style, nav, footer, header"):
        tag.decompose()
    body_node = tree.body or tree.root
    return body_node.text(separator="\n").strip() if body_node else ""
