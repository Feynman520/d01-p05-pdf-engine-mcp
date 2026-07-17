"""engine/rawpdf.py — 외부 의존성 없이 손으로 조립하는 미니멀 PDF 생성기.

용도 두 가지:
  1. 텍스트 워터마크 오버레이 — 대상 페이지와 같은 크기의 1쪽짜리 투명 PDF를 만들어
     pypdf `merge_page`로 겹친다(내장 Helvetica → 라틴 문자 한정).
  2. 테스트 픽스처 — 스모크 테스트가 외부 샘플 파일 없이 텍스트 PDF를 자체 생성.

PDF 원시 구조: 객체들(1 0 obj …) + xref(각 객체의 바이트 오프셋 표) + trailer.
build_pdf()가 오프셋 계산을 맡는다.
"""
from __future__ import annotations

import math
import zlib


def build_pdf(objects: list[bytes], root_obj: int = 1) -> bytes:
    """객체 본문 목록(1번 객체부터 순서대로)을 받아 완전한 PDF 바이트를 조립한다."""
    header = b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n"
    out = bytearray(header)
    offsets = []
    for i, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n".encode("ascii") + body + b"\nendobj\n"
    xref_pos = len(out)
    n = len(objects) + 1
    out += f"xref\n0 {n}\n".encode("ascii")
    out += b"0000000000 65535 f \n"
    for off in offsets:
        out += f"{off:010d} 00000 n \n".encode("ascii")
    out += (
        f"trailer\n<< /Size {n} /Root {root_obj} 0 R >>\n"
        f"startxref\n{xref_pos}\n%%EOF\n"
    ).encode("ascii")
    return bytes(out)


def _esc(text: str) -> str:
    """PDF 문자열 리터럴 이스케이프."""
    return text.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")


def text_overlay_pdf(
    width: float,
    height: float,
    text: str,
    font_size: float = 48,
    rotation: float = 45,
    opacity: float = 0.3,
    gray: float = 0.5,
) -> bytes:
    """페이지 중앙에 회전된 텍스트 하나를 그린 1쪽짜리 오버레이 PDF를 만든다.

    내장 Helvetica(WinAnsi) 사용 — 라틴 문자만 지원. 한글 등은 latin-1 인코딩이
    불가능하므로 호출 측에서 stamp PDF 사용을 안내한다.
    """
    text.encode("latin-1")  # 지원 문자 검증(실패 시 UnicodeEncodeError)
    rad = math.radians(rotation)
    cos, sin = math.cos(rad), math.sin(rad)
    # Helvetica 평균 글자폭 ≈ 0.53em — 중앙 정렬용 근사치
    text_w = 0.53 * font_size * len(text)
    cx, cy = width / 2, height / 2
    content = (
        f"q /GS gs BT /F1 {font_size:.2f} Tf {gray:.3f} {gray:.3f} {gray:.3f} rg\n"
        f"{cos:.6f} {sin:.6f} {-sin:.6f} {cos:.6f} {cx:.2f} {cy:.2f} Tm\n"
        f"{-text_w / 2:.2f} {-font_size / 3:.2f} Td ({_esc(text)}) Tj ET Q\n"
    ).encode("latin-1")
    stream = zlib.compress(content)
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {width:.2f} {height:.2f}] "
            f"/Resources << /Font << /F1 4 0 R >> /ExtGState << /GS 5 0 R >> >> "
            f"/Contents 6 0 R >>"
        ).encode("ascii"),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
        f"<< /Type /ExtGState /ca {opacity:.3f} /CA {opacity:.3f} >>".encode("ascii"),
        (f"<< /Length {len(stream)} /Filter /FlateDecode >>\nstream\n".encode("ascii")
         + stream + b"\nendstream"),
    ]
    return build_pdf(objects)


def simple_text_pdf(pages: list[str], width: float = 595, height: float = 842) -> bytes:
    """페이지별 텍스트 한 덩어리(줄바꿈 지원)를 담은 다쪽 PDF를 만든다(테스트 픽스처용)."""
    objects: list[bytes] = []
    n_pages = len(pages)
    # 1=Catalog, 2=Pages, 3=Font, 4..=Page, (4+n)..=Contents
    page_ids = [4 + i for i in range(n_pages)]
    content_ids = [4 + n_pages + i for i in range(n_pages)]
    kids = " ".join(f"{i} 0 R" for i in page_ids)
    objects.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    objects.append(f"<< /Type /Pages /Kids [{kids}] /Count {n_pages} >>".encode("ascii"))
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>")
    for pid, cid in zip(page_ids, content_ids):
        objects.append(
            (
                f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {width:.0f} {height:.0f}] "
                f"/Resources << /Font << /F1 3 0 R >> >> /Contents {cid} 0 R >>"
            ).encode("ascii")
        )
    for text in pages:
        lines = text.split("\n")
        body = f"BT /F1 14 Tf 72 {height - 72:.0f} Td 18 TL\n".encode("latin-1")
        for i, line in enumerate(lines):
            op = "Tj" if i == 0 else "'"
            body += f"({_esc(line)}) {op}\n".encode("latin-1")
        body += b"ET\n"
        stream = zlib.compress(body)
        objects.append(
            f"<< /Length {len(stream)} /Filter /FlateDecode >>\nstream\n".encode("ascii")
            + stream + b"\nendstream"
        )
    return build_pdf(objects)
