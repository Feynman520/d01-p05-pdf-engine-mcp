"""engine/secure.py — 암호 걸기/풀기(AES-256 기본)."""
from __future__ import annotations

import os
from typing import Optional

from pypdf import PdfReader, PdfWriter
from pypdf.constants import UserAccessPermissions as UAP

from .common import check_src, ensure_parent, open_reader


def encrypt(
    src_path: str,
    out_path: str,
    user_password: str,
    owner_password: Optional[str] = None,
    algorithm: str = "AES-256",
    allow_printing: bool = True,
    allow_copying: bool = True,
    password: Optional[str] = None,
) -> dict:
    """user_password=열람 암호, owner_password=권한 해제 암호(생략 시 user와 동일).

    password는 이미 암호화된 원본을 열 때의 기존 암호다.
    """
    if not user_password:
        raise ValueError("user_password가 비었습니다.")
    reader = open_reader(src_path, password)
    writer = PdfWriter(clone_from=reader)
    perms = UAP.all()
    if not allow_printing:
        perms &= ~(UAP.PRINT | UAP.PRINT_TO_REPRESENTATION)
    if not allow_copying:
        perms &= ~UAP.EXTRACT
    writer.encrypt(
        user_password=user_password,
        owner_password=owner_password or user_password,
        algorithm=algorithm,
        permissions_flag=perms,
    )
    out = ensure_parent(out_path)
    with open(out, "wb") as f:
        writer.write(f)
    return {"out_path": out, "algorithm": algorithm,
            "allow_printing": allow_printing, "allow_copying": allow_copying}


def decrypt(src_path: str, out_path: str, password: str) -> dict:
    src = check_src(src_path)
    probe = PdfReader(src)
    if not probe.is_encrypted:
        raise ValueError("이 PDF는 암호화되어 있지 않습니다.")
    reader = open_reader(src, password)
    writer = PdfWriter(clone_from=reader)
    out = ensure_parent(out_path)
    with open(out, "wb") as f:
        writer.write(f)
    return {"out_path": out, "pages": len(writer.pages), "decrypted": True,
            "note": "사용자가 암호를 아는 파일의 잠금 해제 용도입니다."}
