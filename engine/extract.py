"""engine/extract.py — 내장 이미지 추출, 첨부파일 심기/꺼내기."""
from __future__ import annotations

import os
import re
from typing import Optional

from pypdf import PdfWriter

from .common import check_src, ensure_dir, ensure_parent, open_reader, parse_pages


def _safe_name(name: str) -> str:
    return re.sub(r'[\\/:*?"<>|]', "_", name).strip() or "unnamed"


def extract_images(
    src_path: str,
    out_dir: str,
    pages: Optional[str] = None,
    password: Optional[str] = None,
) -> dict:
    reader = open_reader(src_path, password)
    idxs = parse_pages(pages, len(reader.pages))
    dst = ensure_dir(out_dir)
    saved = []
    for i in idxs:
        page = reader.pages[i]
        try:
            images = list(page.images)
        except Exception:  # noqa: BLE001 — 지원 안 되는 필터 등
            images = []
        for j, img in enumerate(images):
            name = _safe_name(img.name or f"img{j}")
            out = os.path.join(dst, f"p{i + 1:03d}_{j:02d}_{name}")
            with open(out, "wb") as f:
                f.write(img.data)
            saved.append({"page": i + 1, "path": out, "bytes": len(img.data)})
    result = {"out_dir": dst, "count": len(saved), "images": saved}
    if not saved:
        result["note"] = "지정한 페이지에서 추출 가능한 내장 이미지가 없습니다."
    return result


def attach_files(
    src_path: str,
    out_path: str,
    files: list[str],
    password: Optional[str] = None,
) -> dict:
    if not files:
        raise ValueError("첨부할 파일 목록이 비었습니다.")
    reader = open_reader(src_path, password)
    writer = PdfWriter(clone_from=reader)
    names = []
    for f in files:
        p = check_src(f)
        with open(p, "rb") as fh:
            writer.add_attachment(os.path.basename(p), fh.read())
        names.append(os.path.basename(p))
    out = ensure_parent(out_path)
    with open(out, "wb") as fh:
        writer.write(fh)
    return {"out_path": out, "attached": names}


def extract_attachments(
    src_path: str,
    out_dir: str,
    names: Optional[list[str]] = None,
    password: Optional[str] = None,
) -> dict:
    reader = open_reader(src_path, password)
    attachments = reader.attachments or {}
    if names:
        missing = [n for n in names if n not in attachments]
        if missing:
            raise ValueError(f"없는 첨부: {missing} (있는 첨부: {list(attachments)})")
        target = {n: attachments[n] for n in names}
    else:
        target = dict(attachments)
    dst = ensure_dir(out_dir)
    saved = []
    for name, blobs in target.items():
        blobs = blobs if isinstance(blobs, list) else [blobs]
        for k, data in enumerate(blobs):
            base = _safe_name(name)
            if len(blobs) > 1:
                stem, ext = os.path.splitext(base)
                base = f"{stem}_{k + 1}{ext}"
            out = os.path.join(dst, base)
            with open(out, "wb") as f:
                f.write(data)
            saved.append({"name": name, "path": out, "bytes": len(data)})
    result = {"out_dir": dst, "count": len(saved), "files": saved}
    if not saved:
        result["note"] = "이 PDF에는 첨부파일이 없습니다."
    return result
