"""engine/form.py — AcroForm 양식 필드 읽기·채우기."""
from __future__ import annotations

from typing import Optional

from pypdf import PdfWriter

from .common import ensure_parent, open_reader


def form_fields(path: str, password: Optional[str] = None) -> dict:
    reader = open_reader(path, password)
    fields = reader.get_fields() or {}
    out = []
    for name, f in fields.items():
        item = {
            "name": str(name),
            "type": str(f.get("/FT", "")),
            "value": None if f.get("/V") is None else str(f.get("/V")),
            "default": None if f.get("/DV") is None else str(f.get("/DV")),
        }
        states = f.get("/_States_")
        if states:
            item["states"] = [str(s) for s in states]
        out.append(item)
    result = {"path": reader.stream.name if hasattr(reader.stream, "name") else path,
              "count": len(out), "fields": out}
    if not out:
        result["note"] = "이 PDF에는 AcroForm 양식 필드가 없습니다."
    return result


def fill_form(
    src_path: str,
    out_path: str,
    fields: dict,
    flatten: bool = False,
    password: Optional[str] = None,
) -> dict:
    """fields: {필드명: 값}. flatten=True면 채운 뒤 일반 내용으로 굳혀 수정 불가."""
    if not fields:
        raise ValueError("채울 필드가 없습니다.")
    reader = open_reader(src_path, password)
    existing = set((reader.get_fields() or {}).keys())
    if not existing:
        raise ValueError("이 PDF에는 양식 필드가 없습니다 — pdf_form_fields로 먼저 확인하세요.")
    unknown = sorted(set(fields) - existing)
    known = {k: v for k, v in fields.items() if k in existing}
    if not known:
        raise ValueError(f"일치하는 필드가 없습니다. 문서의 필드: {sorted(existing)}")
    writer = PdfWriter(clone_from=reader)
    for page in writer.pages:
        if page.get("/Annots"):
            writer.update_page_form_field_values(page, known, flatten=flatten)
    out = ensure_parent(out_path)
    with open(out, "wb") as f:
        writer.write(f)
    result = {"out_path": out, "filled": sorted(known), "flattened": flatten}
    if unknown:
        result["ignored_unknown_fields"] = unknown
    return result
