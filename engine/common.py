"""engine/common.py — 공통 헬퍼: 경로 검증, 페이지 지정 파싱, 암호화 PDF 열기.

페이지 지정 문자열(pages spec)은 사용자 눈높이의 1-기반 표기를 받는다:
  "3"      → 3쪽
  "1-3,5"  → 1,2,3,5쪽
  "4-"     → 4쪽부터 끝까지
  "-2"     → 처음부터 2쪽까지
내부적으로는 0-기반 인덱스 목록으로 변환해 쓴다. None이면 전체 페이지.
"""
from __future__ import annotations

import os
from typing import Optional

from pypdf import PdfReader


def check_src(path: str) -> str:
    """입력 파일 존재를 확인하고 절대경로를 돌려준다."""
    p = os.path.abspath(path)
    if not os.path.isfile(p):
        raise FileNotFoundError(f"입력 파일이 없습니다: {p}")
    return p


def ensure_parent(path: str) -> str:
    """출력 파일의 부모 폴더를 만들고 절대경로를 돌려준다."""
    p = os.path.abspath(path)
    parent = os.path.dirname(p)
    if parent:
        os.makedirs(parent, exist_ok=True)
    return p


def ensure_dir(path: str) -> str:
    """출력 폴더를 만들고 절대경로를 돌려준다."""
    p = os.path.abspath(path)
    os.makedirs(p, exist_ok=True)
    return p


def open_reader(path: str, password: Optional[str] = None) -> PdfReader:
    """PDF를 열어 PdfReader를 돌려준다. 암호화 문서는 password로 해제(빈 암호도 시도)."""
    reader = PdfReader(check_src(path))
    if reader.is_encrypted:
        pw = password if password is not None else ""
        if not reader.decrypt(pw):
            raise ValueError(
                "암호화된 PDF입니다 — 올바른 password 인자를 함께 주세요." if password is None
                else "암호가 틀렸습니다."
            )
    return reader


def parse_pages(spec: Optional[str], total: int) -> list[int]:
    """1-기반 페이지 지정 문자열 → 0-기반 인덱스 목록. spec이 None이면 전체."""
    if total <= 0:
        raise ValueError("페이지가 없는 PDF입니다.")
    if spec is None or str(spec).strip() == "":
        return list(range(total))
    out: list[int] = []
    for raw in str(spec).split(","):
        token = raw.strip()
        if not token:
            continue
        if "-" in token:
            a, _, b = token.partition("-")
            start = int(a) if a.strip() else 1
            end = int(b) if b.strip() else total
        else:
            start = end = int(token)
        if start < 1 or end > total or start > end:
            raise ValueError(f"페이지 범위가 잘못됐습니다: '{token}' (문서는 1~{total}쪽)")
        out.extend(range(start - 1, end))
    if not out:
        raise ValueError(f"페이지 지정이 비었습니다: '{spec}'")
    return out


def stem_of(path: str) -> str:
    return os.path.splitext(os.path.basename(path))[0]
