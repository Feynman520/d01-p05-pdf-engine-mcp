"""테스트 픽스처 — 외부 샘플 없이 PDF를 자체 생성한다(engine.rawpdf 사용).

  make_text_pdf()  3쪽짜리 텍스트 PDF
  make_form_pdf()  AcroForm 텍스트 필드 2개짜리 양식 PDF
"""
from __future__ import annotations

import os
import sys
import zlib

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from engine import rawpdf  # noqa: E402


def make_text_pdf(path: str) -> str:
    data = rawpdf.simple_text_pdf([
        "Hello PDF page one.\nThis is a smoke-test fixture.",
        "Second page content.\nLine two of page two.",
        "Third and final page.",
    ])
    with open(path, "wb") as f:
        f.write(data)
    return path


def make_form_pdf(path: str) -> str:
    """텍스트 필드 name/school 2개를 가진 1쪽짜리 AcroForm PDF."""
    label = zlib.compress(b"BT /Helv 12 Tf 72 740 Td (Application Form) Tj ET\n")
    objects = [
        # 1 Catalog + AcroForm
        (b"<< /Type /Catalog /Pages 2 0 R /AcroForm << /Fields [5 0 R 6 0 R] "
         b"/NeedAppearances true /DA (/Helv 0 Tf 0 g) "
         b"/DR << /Font << /Helv 4 0 R >> >> >> >>"),
        # 2 Pages
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        # 3 Page
        (b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
         b"/Resources << /Font << /Helv 4 0 R >> >> "
         b"/Annots [5 0 R 6 0 R] /Contents 7 0 R >>"),
        # 4 Font
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
        # 5 field 'name'
        (b"<< /Type /Annot /Subtype /Widget /FT /Tx /T (name) /P 3 0 R "
         b"/Rect [72 680 400 704] /F 4 /DA (/Helv 12 Tf 0 g) >>"),
        # 6 field 'school'
        (b"<< /Type /Annot /Subtype /Widget /FT /Tx /T (school) /P 3 0 R "
         b"/Rect [72 640 400 664] /F 4 /DA (/Helv 12 Tf 0 g) >>"),
        # 7 contents
        (f"<< /Length {len(label)} /Filter /FlateDecode >>\nstream\n".encode("ascii")
         + label + b"\nendstream"),
    ]
    with open(path, "wb") as f:
        f.write(rawpdf.build_pdf(objects))
    return path
