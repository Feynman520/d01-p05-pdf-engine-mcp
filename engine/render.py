"""engine/render.py — PDFium(크롬 PDF 엔진) 기반 렌더링·텍스트 추출.

pypdf 같은 순수 파이썬 라이브러리에는 래스터라이저(페이지를 픽셀로 그리는 엔진)가
없다. 이 모듈만 pypdfium2를 쓴다.
"""
from __future__ import annotations

import os
from typing import Optional

import pypdfium2 as pdfium

from .common import check_src, ensure_dir, parse_pages, stem_of


def _open(path: str, password: Optional[str]):
    try:
        return pdfium.PdfDocument(check_src(path), password=password)
    except pdfium.PdfiumError as e:
        raise ValueError(f"PDF를 열 수 없습니다(암호 오류 또는 손상): {e}") from e


def render_images(
    src_path: str,
    out_dir: str,
    pages: Optional[str] = None,
    dpi: int = 150,
    image_format: str = "png",
    password: Optional[str] = None,
) -> dict:
    if image_format not in ("png", "jpg", "jpeg"):
        raise ValueError('image_format은 "png" 또는 "jpg"만 가능합니다.')
    if not 18 <= dpi <= 600:
        raise ValueError("dpi는 18~600 범위로 주세요.")
    pdf = _open(src_path, password)
    try:
        idxs = parse_pages(pages, len(pdf))
        dst = ensure_dir(out_dir)
        stem = stem_of(src_path)
        scale = dpi / 72.0
        images = []
        for i in idxs:
            page = pdf[i]
            bitmap = page.render(scale=scale)
            pil = bitmap.to_pil()
            if image_format in ("jpg", "jpeg") and pil.mode != "RGB":
                pil = pil.convert("RGB")
            out = os.path.join(dst, f"{stem}_p{i + 1:03d}.{image_format}")
            pil.save(out)
            images.append({"page": i + 1, "path": out,
                           "width_px": pil.width, "height_px": pil.height})
            page.close()
        return {"out_dir": dst, "dpi": dpi, "count": len(images), "images": images}
    finally:
        pdf.close()


def extract_text(
    src_path: str,
    pages: Optional[str] = None,
    password: Optional[str] = None,
) -> dict:
    pdf = _open(src_path, password)
    try:
        idxs = parse_pages(pages, len(pdf))
        result = []
        total_chars = 0
        for i in idxs:
            page = pdf[i]
            textpage = page.get_textpage()
            text = textpage.get_text_bounded() or ""
            textpage.close()
            page.close()
            total_chars += len(text)
            result.append({"page": i + 1, "chars": len(text), "text": text})
        out = {"path": os.path.abspath(src_path), "pages": result,
               "total_chars": total_chars}
        if total_chars == 0:
            out["note"] = ("추출된 글자가 없습니다 — 스캔 이미지 PDF일 가능성이 큽니다. "
                           "pdf_render_images로 이미지를 만든 뒤 OCR/시각 판독을 쓰세요.")
        return out
    finally:
        pdf.close()
