"""engine/assemble.py — 문서 조립: 병합·분할·페이지 수술·워터마크."""
from __future__ import annotations

import io
import os
from typing import Optional

from pypdf import PdfReader, PdfWriter

from . import rawpdf
from .common import ensure_dir, ensure_parent, open_reader, parse_pages, stem_of


def merge(inputs: list[dict], out_path: str) -> dict:
    """inputs: [{"path": str, "pages": "1-3,5"?, "password": str?}, ...] 순서대로 병합."""
    if not inputs:
        raise ValueError("병합할 입력이 없습니다.")
    writer = PdfWriter()
    total = 0
    for item in inputs:
        reader = open_reader(item["path"], item.get("password"))
        idxs = parse_pages(item.get("pages"), len(reader.pages))
        writer.append(reader, pages=idxs)
        total += len(idxs)
    out = ensure_parent(out_path)
    with open(out, "wb") as f:
        writer.write(f)
    return {"out_path": out, "pages": total, "inputs": len(inputs)}


def split(
    src_path: str,
    pages: Optional[str] = None,
    out_path: Optional[str] = None,
    out_dir: Optional[str] = None,
    every: int = 1,
    password: Optional[str] = None,
) -> dict:
    """pages를 주면 그 페이지들만 out_path 한 파일로 추출.
    안 주면 every쪽씩 잘라 out_dir에 여러 파일로 저장."""
    reader = open_reader(src_path, password)
    total = len(reader.pages)
    if pages is not None:
        if not out_path:
            raise ValueError("pages 추출 모드에는 out_path가 필요합니다.")
        idxs = parse_pages(pages, total)
        writer = PdfWriter()
        writer.append(reader, pages=idxs)
        out = ensure_parent(out_path)
        with open(out, "wb") as f:
            writer.write(f)
        return {"out_paths": [out], "count": 1, "pages_each": [len(idxs)]}
    if not out_dir:
        raise ValueError("분할 모드에는 out_dir이 필요합니다.")
    if every < 1:
        raise ValueError("every는 1 이상이어야 합니다.")
    dst = ensure_dir(out_dir)
    stem = stem_of(src_path)
    outs, counts = [], []
    for start in range(0, total, every):
        idxs = list(range(start, min(start + every, total)))
        writer = PdfWriter()
        writer.append(reader, pages=idxs)
        if every == 1:
            name = f"{stem}_p{start + 1:03d}.pdf"
        else:
            name = f"{stem}_p{start + 1:03d}-{idxs[-1] + 1:03d}.pdf"
        out = os.path.join(dst, name)
        with open(out, "wb") as f:
            writer.write(f)
        outs.append(out)
        counts.append(len(idxs))
    return {"out_paths": outs, "count": len(outs), "pages_each": counts}


def pages_op(
    src_path: str,
    out_path: str,
    op: str,
    pages: Optional[str] = None,
    degrees: int = 90,
    order: Optional[list[int]] = None,
    password: Optional[str] = None,
) -> dict:
    """op: "rotate"(pages·degrees) | "delete"(pages) | "reorder"(order, 1-기반 새 순서)."""
    reader = open_reader(src_path, password)
    total = len(reader.pages)
    if op == "rotate":
        if degrees % 90 != 0:
            raise ValueError("degrees는 90의 배수여야 합니다.")
        idxs = parse_pages(pages, total)
        writer = PdfWriter(clone_from=reader)
        for i in idxs:
            writer.pages[i].rotate(degrees)
        detail = {"rotated_pages": len(idxs), "degrees": degrees}
    elif op == "delete":
        if pages is None:
            raise ValueError("delete에는 pages가 필요합니다.")
        drop = set(parse_pages(pages, total))
        keep = [i for i in range(total) if i not in drop]
        if not keep:
            raise ValueError("모든 페이지를 삭제할 수는 없습니다.")
        writer = PdfWriter()
        writer.append(reader, pages=keep)
        detail = {"deleted_pages": len(drop), "remaining": len(keep)}
    elif op == "reorder":
        if not order:
            raise ValueError("reorder에는 order(1-기반 페이지 번호 목록)가 필요합니다.")
        bad = [n for n in order if n < 1 or n > total]
        if bad:
            raise ValueError(f"order에 잘못된 페이지 번호: {bad} (문서는 1~{total}쪽)")
        writer = PdfWriter()
        writer.append(reader, pages=[n - 1 for n in order])
        detail = {"order": order}
    else:
        raise ValueError(f"지원하지 않는 op: {op} (rotate|delete|reorder)")
    out = ensure_parent(out_path)
    with open(out, "wb") as f:
        writer.write(f)
    return {"out_path": out, "op": op, **detail}


def watermark(
    src_path: str,
    out_path: str,
    text: Optional[str] = None,
    stamp_path: Optional[str] = None,
    pages: Optional[str] = None,
    mode: str = "overlay",
    opacity: float = 0.3,
    font_size: float = 48,
    rotation: float = 45,
    password: Optional[str] = None,
) -> dict:
    """text(내장 Helvetica — 라틴 문자만) 또는 stamp_path(임의 PDF 1쪽)를 겹친다.

    mode: "overlay"(내용 위에) | "background"(내용 아래에).
    한글 등 비라틴 텍스트는 stamp PDF를 만들어 stamp_path로 쓰는 것을 안내한다.
    """
    if (text is None) == (stamp_path is None):
        raise ValueError("text 또는 stamp_path 중 정확히 하나를 주세요.")
    if mode not in ("overlay", "background"):
        raise ValueError('mode는 "overlay" 또는 "background"만 가능합니다.')
    reader = open_reader(src_path, password)
    idxs = set(parse_pages(pages, len(reader.pages)))
    stamp_page = None
    overlay_cache: dict[tuple, object] = {}
    if stamp_path is not None:
        stamp_page = open_reader(stamp_path).pages[0]
    else:
        try:
            text.encode("latin-1")
        except UnicodeEncodeError as e:
            raise ValueError(
                "텍스트 워터마크는 내장 Helvetica라 라틴 문자만 지원합니다. "
                "한글 등은 도장용 PDF를 만들어 stamp_path로 넘기세요."
            ) from e
    writer = PdfWriter(clone_from=reader)
    for i, page in enumerate(writer.pages):
        if i not in idxs:
            continue
        if stamp_page is not None:
            overlay = stamp_page
        else:
            box = page.mediabox
            key = (round(float(box.width), 2), round(float(box.height), 2))
            if key not in overlay_cache:
                data = rawpdf.text_overlay_pdf(
                    key[0], key[1], text,
                    font_size=font_size, rotation=rotation, opacity=opacity,
                )
                overlay_cache[key] = PdfReader(io.BytesIO(data)).pages[0]
            overlay = overlay_cache[key]
        page.merge_page(overlay, over=(mode == "overlay"))
    out = ensure_parent(out_path)
    with open(out, "wb") as f:
        writer.write(f)
    return {
        "out_path": out, "mode": mode, "pages_stamped": len(idxs),
        "kind": "stamp_pdf" if stamp_path else "text",
    }
