"""engine/optimize.py — 용량 줄이기(스트림 압축·중복 제거·이미지 재압축)."""
from __future__ import annotations

import os
from typing import Optional

from pypdf import PdfWriter

from .common import check_src, ensure_parent, open_reader


def compress(
    src_path: str,
    out_path: str,
    compress_streams: bool = True,
    remove_duplicates: bool = True,
    image_quality: Optional[int] = None,
    password: Optional[str] = None,
) -> dict:
    """image_quality(1~95)를 주면 내장 이미지를 JPEG 품질로 재압축한다(손실)."""
    src = check_src(src_path)
    before = os.path.getsize(src)
    reader = open_reader(src, password)
    writer = PdfWriter(clone_from=reader)
    images_recompressed = 0
    if image_quality is not None:
        if not 1 <= image_quality <= 95:
            raise ValueError("image_quality는 1~95 범위로 주세요.")
        for page in writer.pages:
            try:
                images = list(page.images)
            except Exception:  # noqa: BLE001
                continue
            for img in images:
                try:
                    img.replace(img.image, quality=image_quality)
                    images_recompressed += 1
                except Exception:  # noqa: BLE001 — 마스크·특수 필터 이미지는 건너뜀
                    continue
    if compress_streams:
        for page in writer.pages:
            page.compress_content_streams()
    if remove_duplicates:
        writer.compress_identical_objects(remove_identicals=True, remove_orphans=True)
    out = ensure_parent(out_path)
    with open(out, "wb") as f:
        writer.write(f)
    after = os.path.getsize(out)
    return {
        "out_path": out,
        "bytes_before": before,
        "bytes_after": after,
        "saved_percent": round((1 - after / before) * 100, 1) if before else 0.0,
        "images_recompressed": images_recompressed,
    }
