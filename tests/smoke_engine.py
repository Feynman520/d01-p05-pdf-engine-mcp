"""엔진 왕복 스모크 테스트 — 자체 생성 픽스처로 17개 도구의 엔진 함수를 전부 실행한다.

실행: .venv\\Scripts\\python.exe tests\\smoke_engine.py
"""
from __future__ import annotations

import os
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from engine import assemble, extract, form, info, optimize, outline, render, secure  # noqa: E402
from tests import fixtures  # noqa: E402

OUT = os.path.join(ROOT, "tests", "_out")


def ok(step: str, detail: str = "") -> None:
    print(f"[smoke] {step} OK {detail}", flush=True)


def main() -> int:
    shutil.rmtree(OUT, ignore_errors=True)
    os.makedirs(OUT, exist_ok=True)
    text_pdf = fixtures.make_text_pdf(os.path.join(OUT, "text.pdf"))
    form_pdf = fixtures.make_form_pdf(os.path.join(OUT, "form.pdf"))
    ok("fixtures", f"text={os.path.getsize(text_pdf)}B form={os.path.getsize(form_pdf)}B")

    # ① info
    r = info.info(text_pdf)
    assert r["pages"] == 3 and not r["encrypted"], r
    assert r["page_sizes"][0]["width_pt"] == 595.0, r["page_sizes"]
    ok("pdf_info", f"pages={r['pages']}")

    # ② merge (3쪽 + 1-2쪽 = 5쪽)
    merged = os.path.join(OUT, "merged.pdf")
    r = assemble.merge([{"path": text_pdf}, {"path": text_pdf, "pages": "1-2"}], merged)
    assert r["pages"] == 5 and info.info(merged)["pages"] == 5, r
    ok("pdf_merge", "3+2=5쪽")

    # ③ split — 추출 모드 + 분할 모드
    part = os.path.join(OUT, "part.pdf")
    r = assemble.split(text_pdf, pages="2-3", out_path=part)
    assert info.info(part)["pages"] == 2, r
    r = assemble.split(text_pdf, out_dir=os.path.join(OUT, "split"), every=1)
    assert r["count"] == 3, r
    ok("pdf_split", "추출 2쪽 / 분할 3파일")

    # ④ pages — rotate / delete / reorder
    rot = os.path.join(OUT, "rot.pdf")
    r = assemble.pages_op(text_pdf, rot, "rotate", pages="1", degrees=90)
    assert r["rotated_pages"] == 1, r
    dele = os.path.join(OUT, "del.pdf")
    r = assemble.pages_op(text_pdf, dele, "delete", pages="2")
    assert info.info(dele)["pages"] == 2, r
    reo = os.path.join(OUT, "reorder.pdf")
    r = assemble.pages_op(text_pdf, reo, "reorder", order=[3, 1, 2])
    assert info.info(reo)["pages"] == 3, r
    ok("pdf_pages", "rotate/delete/reorder")

    # ⑤ watermark — 텍스트 오버레이 + 비라틴 거부
    wm = os.path.join(OUT, "wm.pdf")
    r = assemble.watermark(text_pdf, wm, text="DRAFT")
    assert r["pages_stamped"] == 3, r
    try:
        assemble.watermark(text_pdf, wm, text="한글워터마크")
        raise AssertionError("비라틴 텍스트가 거부되지 않음")
    except ValueError:
        pass
    ok("pdf_watermark", "DRAFT 3쪽 + 한글 거부 확인")

    # ⑥ render_images (PDFium)
    r = render.render_images(text_pdf, os.path.join(OUT, "img"), dpi=72)
    assert r["count"] == 3 and all(os.path.getsize(i["path"]) > 0 for i in r["images"]), r
    ok("pdf_render_images", f"{r['count']}개 PNG, {r['images'][0]['width_px']}px")

    # 워터마크 결과도 렌더돼야 함(겹침 후 무결성)
    r = render.render_images(wm, os.path.join(OUT, "img_wm"), pages="1", dpi=72)
    assert r["count"] == 1, r
    ok("watermark render", "워터마크본 렌더 무결성")

    # ⑦ extract_text (PDFium)
    r = render.extract_text(text_pdf)
    assert "Hello PDF" in r["pages"][0]["text"], r["pages"][0]
    assert "Third" in r["pages"][2]["text"], r["pages"][2]
    ok("pdf_extract_text", f"total_chars={r['total_chars']}")

    # ⑧ extract_images — 텍스트 PDF엔 이미지 없음(정직한 빈 결과)
    r = extract.extract_images(text_pdf, os.path.join(OUT, "imgs"))
    assert r["count"] == 0 and "note" in r, r
    ok("pdf_extract_images", "이미지 없음 정직 보고")

    # ⑨⑩ form_fields / fill_form (+flatten)
    r = form.form_fields(form_pdf)
    assert r["count"] == 2 and {f["name"] for f in r["fields"]} == {"name", "school"}, r
    filled = os.path.join(OUT, "filled.pdf")
    r = form.fill_form(form_pdf, filled, {"name": "Hong Gildong", "school": "Shinjang HS"})
    assert set(r["filled"]) == {"name", "school"}, r
    vals = {f["name"]: f["value"] for f in form.form_fields(filled)["fields"]}
    assert vals["name"] == "Hong Gildong", vals
    flat = os.path.join(OUT, "flat.pdf")
    r = form.fill_form(form_pdf, flat, {"name": "Flat Test"}, flatten=True)
    assert r["flattened"], r
    ok("pdf_form_fields/fill_form", f"값 왕복={vals}")

    # ⑪⑫ encrypt / decrypt
    enc = os.path.join(OUT, "enc.pdf")
    r = secure.encrypt(text_pdf, enc, user_password="pw123", allow_copying=False)
    assert info.info(enc)["encrypted"], r
    assert info.info(enc, password="pw123")["pages"] == 3
    dec = os.path.join(OUT, "dec.pdf")
    r = secure.decrypt(enc, dec, "pw123")
    assert not info.info(dec)["encrypted"] and r["pages"] == 3, r
    ok("pdf_encrypt/decrypt", "AES-256 왕복")

    # ⑬ compress
    comp = os.path.join(OUT, "comp.pdf")
    r = optimize.compress(merged, comp)
    assert os.path.getsize(comp) > 0 and info.info(comp)["pages"] == 5, r
    ok("pdf_compress", f"{r['bytes_before']}→{r['bytes_after']}B ({r['saved_percent']}%)")

    # ⑭⑮ attach / extract_attachments
    att_src = os.path.join(OUT, "note.txt")
    with open(att_src, "w", encoding="utf-8") as f:
        f.write("attachment payload 첨부 내용")
    att = os.path.join(OUT, "att.pdf")
    r = extract.attach_files(text_pdf, att, [att_src])
    assert r["attached"] == ["note.txt"], r
    assert "note.txt" in info.info(att)["attachments"]
    r = extract.extract_attachments(att, os.path.join(OUT, "att_out"))
    assert r["count"] == 1, r
    with open(r["files"][0]["path"], encoding="utf-8") as f:
        assert "첨부 내용" in f.read()
    ok("pdf_attach_files/extract_attachments", "왕복 내용 일치")

    # ⑯ bookmarks
    bmk = os.path.join(OUT, "bmk.pdf")
    r = outline.set_bookmarks(text_pdf, bmk, [
        {"title": "Chapter 1", "page": 1,
         "children": [{"title": "Section 1.1", "page": 2}]},
        {"title": "Chapter 2", "page": 3},
    ])
    assert r["bookmarks_added"] == 3, r
    tree = info.info(bmk)["bookmarks"]
    assert tree[0]["title"] == "Chapter 1" and tree[0]["children"][0]["page"] == 2, tree
    ok("pdf_bookmarks", f"tree={tree}")

    # ⑰ set_metadata
    meta = os.path.join(OUT, "meta.pdf")
    r = info.set_metadata(text_pdf, meta, title="스모크 제목", author="IRIS")
    got = info.info(meta)["metadata"]
    assert got.get("Title") == "스모크 제목" and got.get("Author") == "IRIS", got
    ok("pdf_set_metadata", str(r["updated"]))

    print("[smoke] === 엔진 스모크 전체 통과 (17개 도구 경로) ===", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
