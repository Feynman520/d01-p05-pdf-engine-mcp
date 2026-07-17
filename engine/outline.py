"""engine/outline.py — 북마크(목차) 새로 쓰기."""
from __future__ import annotations

from typing import Optional

from pypdf import PdfWriter

from .common import ensure_parent, open_reader


def set_bookmarks(
    src_path: str,
    out_path: str,
    bookmarks: list[dict],
    password: Optional[str] = None,
) -> dict:
    """bookmarks: [{"title": str, "page": 1-기반 int, "children": [...]?}, ...]
    기존 북마크는 버리고 준 트리로 교체한다."""
    if not bookmarks:
        raise ValueError("bookmarks가 비었습니다.")
    reader = open_reader(src_path, password)
    total = len(reader.pages)
    writer = PdfWriter()
    writer.append(reader, import_outline=False)

    count = 0

    def _add(items: list[dict], parent=None) -> None:
        nonlocal count
        for it in items:
            title = str(it.get("title", "")).strip()
            page = it.get("page")
            if not title or not isinstance(page, int) or not 1 <= page <= total:
                raise ValueError(
                    f"잘못된 북마크 항목: {it!r} (title 필수, page는 1~{total})")
            node = writer.add_outline_item(title, page - 1, parent=parent)
            count += 1
            children = it.get("children") or []
            if children:
                _add(children, node)

    _add(bookmarks)
    out = ensure_parent(out_path)
    with open(out, "wb") as f:
        writer.write(f)
    return {"out_path": out, "bookmarks_added": count}
