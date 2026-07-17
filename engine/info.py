"""engine/info.py — 문서 조회(pdf_info)와 메타데이터 쓰기(pdf_set_metadata)."""
from __future__ import annotations

import os
from typing import Optional

from pypdf import PdfReader, PdfWriter

from .common import check_src, ensure_parent, open_reader


def _outline_tree(reader: PdfReader, items) -> list[dict]:
    """pypdf outline(중첩 리스트)을 {title, page, children} 트리로 변환한다."""
    out: list[dict] = []
    for it in items:
        if isinstance(it, list):
            if out:
                out[-1]["children"] = _outline_tree(reader, it)
            continue
        try:
            page = reader.get_destination_page_number(it) + 1
        except Exception:  # noqa: BLE001 — 외부 링크 등 페이지 없는 항목
            page = None
        out.append({"title": str(it.title), "page": page})
    return out


def info(path: str, password: Optional[str] = None) -> dict:
    src = check_src(path)
    file_size = os.path.getsize(src)
    probe = PdfReader(src)
    if probe.is_encrypted:
        pw = password if password is not None else ""
        if not probe.decrypt(pw):
            return {
                "path": src,
                "file_size": file_size,
                "encrypted": True,
                "note": "암호로 잠긴 PDF — password 인자를 주면 상세 정보를 읽습니다.",
            }
    reader = probe
    meta = {}
    if reader.metadata:
        for k, v in reader.metadata.items():
            meta[str(k).lstrip("/")] = str(v)
    # 페이지 크기: 같은 크기끼리 묶어 요약(포인트 단위, 1pt = 1/72인치)
    sizes: dict[tuple, list[int]] = {}
    for i, page in enumerate(reader.pages):
        box = page.mediabox
        key = (round(float(box.width), 2), round(float(box.height), 2))
        sizes.setdefault(key, []).append(i + 1)
    page_sizes = [
        {"width_pt": w, "height_pt": h, "pages": len(nums), "first_page": nums[0]}
        for (w, h), nums in sizes.items()
    ]
    try:
        fields = reader.get_fields() or {}
    except Exception:  # noqa: BLE001
        fields = {}
    try:
        attachment_names = list((reader.attachments or {}).keys())
    except Exception:  # noqa: BLE001
        attachment_names = []
    try:
        bookmarks = _outline_tree(reader, reader.outline)
    except Exception:  # noqa: BLE001
        bookmarks = []
    return {
        "path": src,
        "file_size": file_size,
        "encrypted": bool(probe.is_encrypted),
        "pdf_version": str(reader.pdf_header).lstrip("%"),
        "pages": len(reader.pages),
        "page_sizes": page_sizes,
        "metadata": meta,
        "form_field_count": len(fields),
        "form_field_names": sorted(fields.keys()),
        "attachments": attachment_names,
        "bookmarks": bookmarks,
    }


def set_metadata(
    src_path: str,
    out_path: str,
    title: Optional[str] = None,
    author: Optional[str] = None,
    subject: Optional[str] = None,
    keywords: Optional[str] = None,
    creator: Optional[str] = None,
    producer: Optional[str] = None,
    password: Optional[str] = None,
) -> dict:
    reader = open_reader(src_path, password)
    writer = PdfWriter(clone_from=reader)
    updates = {
        "/Title": title, "/Author": author, "/Subject": subject,
        "/Keywords": keywords, "/Creator": creator, "/Producer": producer,
    }
    updates = {k: v for k, v in updates.items() if v is not None}
    if not updates:
        raise ValueError("바꿀 메타데이터 항목이 하나도 없습니다.")
    writer.add_metadata(updates)
    out = ensure_parent(out_path)
    with open(out, "wb") as f:
        writer.write(f)
    return {"out_path": out, "updated": sorted(k.lstrip("/") for k in updates)}
