"""
server.py — PDF 엔진 자동화 MCP 서버 (stdio).

Word/Excel MCP와 달리 PDF에는 상주 데스크톱 앱이 없다. 대신 두 네이티브 엔진을
라이브러리로 불러 쓴다:
  - PDFium(pypdfium2) — 크롬의 PDF 렌더 엔진: 페이지→이미지 렌더링, 텍스트 추출
  - pypdf(+cryptography) — 문서 수술: 병합·분할·페이지·워터마크·양식·암호·압축·첨부·북마크

무상태(stateless) 설계: COM 세션·전용 스레드 없이, 각 도구 호출이
열기→작업→out_path 저장→닫기로 끝난다. 블로킹 작업은 anyio.to_thread로 위임해
이벤트 루프를 막지 않는다. 원본은 항상 보존된다.

실행:  python server.py        (Claude Code가 stdio로 기동)
"""
from __future__ import annotations

from typing import Any, Optional

import anyio
from mcp.server.fastmcp import FastMCP

from engine import assemble as assemble_mod
from engine import extract as extract_mod
from engine import form as form_mod
from engine import info as info_mod
from engine import optimize as optimize_mod
from engine import outline as outline_mod
from engine import render as render_mod
from engine import secure as secure_mod

mcp = FastMCP(
    "pdf-automation",
    instructions=(
        "PDF 엔진 자동화(PDFium 렌더 + pypdf 문서수술, 무상태). "
        "조회 pdf_info → 조립 pdf_merge/pdf_split/pdf_pages/pdf_watermark → "
        "렌더·추출 pdf_render_images/pdf_extract_text/pdf_extract_images → "
        "양식 pdf_form_fields/pdf_fill_form → 보안 pdf_encrypt/pdf_decrypt → "
        "최적화 pdf_compress → 첨부 pdf_attach_files/pdf_extract_attachments → "
        "구조 pdf_bookmarks/pdf_set_metadata. 페이지 지정은 1-기반 문자열('1-3,5'). "
        "경로는 절대경로 권장. 원본은 보존되며 결과는 out_path/out_dir로 저장된다. "
        "PDF→Word 변환은 word-automation의 word_convert를 사용."
    ),
)


async def _bg(fn) -> Any:
    return await anyio.to_thread.run_sync(fn)


# ============================================================================
# 조회
# ============================================================================
@mcp.tool()
async def pdf_info(path: str, password: Optional[str] = None) -> dict:
    """① PDF 기본 정보를 한 번에 읽는다 — 페이지 수·크기, 메타데이터, 암호 여부,
    양식 필드 목록, 첨부파일 목록, 북마크 트리.

    Args:
        path: PDF 절대경로
        password: 암호화 문서의 암호(선택)
    Returns: {"pages","page_sizes","metadata","encrypted","form_field_names","attachments","bookmarks",...}
    """
    return await _bg(lambda: info_mod.info(path, password))


# ============================================================================
# 조립
# ============================================================================
@mcp.tool()
async def pdf_merge(inputs: list[dict], out_path: str) -> dict:
    """② 여러 PDF를 순서대로 한 파일로 병합한다(파일별 페이지 범위 지정 가능).

    Args:
        inputs: [{"path": 절대경로, "pages": "1-3,5"(선택), "password": 암호(선택)}, ...]
        out_path: 결과 .pdf 절대경로
    Returns: {"out_path","pages","inputs"}
    """
    return await _bg(lambda: assemble_mod.merge(inputs, out_path))


@mcp.tool()
async def pdf_split(
    src_path: str,
    pages: Optional[str] = None,
    out_path: Optional[str] = None,
    out_dir: Optional[str] = None,
    every: int = 1,
    password: Optional[str] = None,
) -> dict:
    """③ 페이지 추출/분할. pages를 주면 그 페이지들만 out_path 한 파일로 추출,
    안 주면 every쪽씩 잘라 out_dir에 여러 파일로 저장.

    Args:
        src_path: 입력 PDF 절대경로
        pages: 추출할 페이지("2-5,7" 등, 1-기반) — 추출 모드
        out_path: 추출 모드 결과 파일 경로
        out_dir: 분할 모드 결과 폴더
        every: 분할 모드에서 파일당 페이지 수(기본 1)
        password: 암호(선택)
    Returns: {"out_paths","count","pages_each"}
    """
    return await _bg(lambda: assemble_mod.split(src_path, pages, out_path, out_dir, every, password))


@mcp.tool()
async def pdf_pages(
    src_path: str,
    out_path: str,
    op: str,
    pages: Optional[str] = None,
    degrees: int = 90,
    order: Optional[list[int]] = None,
    password: Optional[str] = None,
) -> dict:
    """④ 페이지 수술 — 회전·삭제·재배열.

    Args:
        src_path: 입력 PDF 절대경로
        out_path: 결과 저장 경로
        op: "rotate"(pages+degrees) | "delete"(pages) | "reorder"(order)
        pages: 대상 페이지("1,3-4", rotate는 생략 시 전체)
        degrees: 회전 각도(90의 배수, 시계방향)
        order: reorder용 1-기반 새 페이지 순서(예: [3,1,2])
        password: 암호(선택)
    Returns: {"out_path","op",...}
    """
    return await _bg(lambda: assemble_mod.pages_op(src_path, out_path, op, pages, degrees, order, password))


@mcp.tool()
async def pdf_watermark(
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
    """⑤ 워터마크/스탬프 — 텍스트(내장 Helvetica, 라틴 문자만) 또는 도장 PDF 1쪽을 겹친다.
    한글 워터마크는 도장용 PDF를 만들어 stamp_path로 넘길 것.

    Args:
        src_path: 입력 PDF 절대경로
        out_path: 결과 저장 경로
        text: 워터마크 문구(라틴 문자) — stamp_path와 둘 중 하나만
        stamp_path: 도장 PDF 절대경로(1쪽만 사용)
        pages: 대상 페이지(기본 전체)
        mode: "overlay"(내용 위) | "background"(내용 아래)
        opacity: 텍스트 불투명도 0~1(기본 0.3, text 모드만)
        font_size: 텍스트 크기 pt(기본 48)
        rotation: 텍스트 회전 각도(기본 45)
        password: 암호(선택)
    Returns: {"out_path","mode","pages_stamped","kind"}
    """
    return await _bg(lambda: assemble_mod.watermark(
        src_path, out_path, text, stamp_path, pages, mode, opacity, font_size, rotation, password))


# ============================================================================
# 렌더·추출 (PDFium)
# ============================================================================
@mcp.tool()
async def pdf_render_images(
    src_path: str,
    out_dir: str,
    pages: Optional[str] = None,
    dpi: int = 150,
    image_format: str = "png",
    password: Optional[str] = None,
) -> dict:
    """⑥ 페이지를 이미지로 렌더링한다(크롬 PDFium 엔진 — 라이브러리로는 불가능한 부분).
    미리보기·LLM 시각 확인·OCR 전처리용.

    Args:
        src_path: 입력 PDF 절대경로
        out_dir: 이미지 저장 폴더
        pages: 대상 페이지(기본 전체)
        dpi: 해상도 18~600(기본 150)
        image_format: "png"(기본) | "jpg"
        password: 암호(선택)
    Returns: {"out_dir","dpi","count","images":[{"page","path","width_px","height_px"}]}
    """
    return await _bg(lambda: render_mod.render_images(src_path, out_dir, pages, dpi, image_format, password))


@mcp.tool()
async def pdf_extract_text(
    src_path: str,
    pages: Optional[str] = None,
    password: Optional[str] = None,
) -> dict:
    """⑦ 페이지별 텍스트를 추출한다(PDFium 텍스트 엔진). 스캔본이면 빈 결과와 함께
    OCR 안내를 돌려준다 — 날조하지 않는다.

    Args:
        src_path: 입력 PDF 절대경로
        pages: 대상 페이지(기본 전체)
        password: 암호(선택)
    Returns: {"pages":[{"page","chars","text"}],"total_chars","note"?}
    """
    return await _bg(lambda: render_mod.extract_text(src_path, pages, password))


@mcp.tool()
async def pdf_extract_images(
    src_path: str,
    out_dir: str,
    pages: Optional[str] = None,
    password: Optional[str] = None,
) -> dict:
    """⑧ 문서에 내장된 이미지 원본을 파일로 추출한다(렌더링이 아니라 원본 그대로).

    Args:
        src_path: 입력 PDF 절대경로
        out_dir: 이미지 저장 폴더
        pages: 대상 페이지(기본 전체)
        password: 암호(선택)
    Returns: {"out_dir","count","images":[{"page","path","bytes"}]}
    """
    return await _bg(lambda: extract_mod.extract_images(src_path, out_dir, pages, password))


# ============================================================================
# 양식
# ============================================================================
@mcp.tool()
async def pdf_form_fields(path: str, password: Optional[str] = None) -> dict:
    """⑨ AcroForm 양식 필드 목록과 현재값을 읽는다(pdf_fill_form 전 확인용).

    Args:
        path: PDF 절대경로
        password: 암호(선택)
    Returns: {"count","fields":[{"name","type","value","default","states"?}]}
    """
    return await _bg(lambda: form_mod.form_fields(path, password))


@mcp.tool()
async def pdf_fill_form(
    src_path: str,
    out_path: str,
    fields: dict,
    flatten: bool = False,
    password: Optional[str] = None,
) -> dict:
    """⑩ 양식 필드를 채운다. flatten=True면 채운 값을 일반 내용으로 굳혀 이후 수정 불가
    (제출용 확정본).

    Args:
        src_path: 양식 PDF 절대경로
        out_path: 결과 저장 경로
        fields: {"필드명": "값"} — 필드명은 pdf_form_fields로 확인
        flatten: 평탄화 여부(기본 False)
        password: 암호(선택)
    Returns: {"out_path","filled","flattened","ignored_unknown_fields"?}
    """
    return await _bg(lambda: form_mod.fill_form(src_path, out_path, fields, flatten, password))


# ============================================================================
# 보안
# ============================================================================
@mcp.tool()
async def pdf_encrypt(
    src_path: str,
    out_path: str,
    user_password: str,
    owner_password: Optional[str] = None,
    algorithm: str = "AES-256",
    allow_printing: bool = True,
    allow_copying: bool = True,
    password: Optional[str] = None,
) -> dict:
    """⑪ PDF에 암호를 건다(기본 AES-256).

    Args:
        src_path: 입력 PDF 절대경로
        out_path: 결과 저장 경로
        user_password: 열람 암호
        owner_password: 권한 암호(생략 시 user와 동일)
        algorithm: "AES-256"(기본) | "AES-128" | "RC4-128"
        allow_printing: 인쇄 허용(기본 True)
        allow_copying: 텍스트 복사 허용(기본 True)
        password: 원본이 이미 암호화된 경우 그 암호
    Returns: {"out_path","algorithm",...}
    """
    return await _bg(lambda: secure_mod.encrypt(
        src_path, out_path, user_password, owner_password, algorithm,
        allow_printing, allow_copying, password))


@mcp.tool()
async def pdf_decrypt(src_path: str, out_path: str, password: str) -> dict:
    """⑫ 암호를 아는 PDF의 잠금을 풀어 암호 없는 사본을 만든다(본인 소유/권한 파일 전용).

    Args:
        src_path: 암호화된 PDF 절대경로
        out_path: 결과 저장 경로
        password: 현재 암호
    Returns: {"out_path","pages","decrypted"}
    """
    return await _bg(lambda: secure_mod.decrypt(src_path, out_path, password))


# ============================================================================
# 최적화·첨부·구조
# ============================================================================
@mcp.tool()
async def pdf_compress(
    src_path: str,
    out_path: str,
    compress_streams: bool = True,
    remove_duplicates: bool = True,
    image_quality: Optional[int] = None,
    password: Optional[str] = None,
) -> dict:
    """⑬ 용량을 줄인다 — 콘텐츠 스트림 압축 + 중복 객체 제거(무손실),
    image_quality(1~95)를 주면 내장 이미지 JPEG 재압축(손실).

    Args:
        src_path: 입력 PDF 절대경로
        out_path: 결과 저장 경로
        compress_streams: 스트림 압축(기본 True)
        remove_duplicates: 중복 객체·고아 객체 제거(기본 True)
        image_quality: 이미지 재압축 품질(선택, 낮을수록 작아짐)
        password: 암호(선택)
    Returns: {"out_path","bytes_before","bytes_after","saved_percent","images_recompressed"}
    """
    return await _bg(lambda: optimize_mod.compress(
        src_path, out_path, compress_streams, remove_duplicates, image_quality, password))


@mcp.tool()
async def pdf_attach_files(
    src_path: str,
    out_path: str,
    files: list[str],
    password: Optional[str] = None,
) -> dict:
    """⑭ PDF 안에 파일을 첨부(내장)한다 — 근거 자료를 문서에 심어 배포할 때.

    Args:
        src_path: 입력 PDF 절대경로
        out_path: 결과 저장 경로
        files: 첨부할 파일 절대경로 목록
        password: 암호(선택)
    Returns: {"out_path","attached"}
    """
    return await _bg(lambda: extract_mod.attach_files(src_path, out_path, files, password))


@mcp.tool()
async def pdf_extract_attachments(
    src_path: str,
    out_dir: str,
    names: Optional[list[str]] = None,
    password: Optional[str] = None,
) -> dict:
    """⑮ PDF에 내장된 첨부파일을 꺼내 저장한다(names 생략 시 전부).

    Args:
        src_path: 입력 PDF 절대경로
        out_dir: 저장 폴더
        names: 꺼낼 첨부 이름 목록(선택 — pdf_info의 attachments 참조)
        password: 암호(선택)
    Returns: {"out_dir","count","files":[{"name","path","bytes"}]}
    """
    return await _bg(lambda: extract_mod.extract_attachments(src_path, out_dir, names, password))


@mcp.tool()
async def pdf_bookmarks(
    src_path: str,
    out_path: str,
    bookmarks: list[dict],
    password: Optional[str] = None,
) -> dict:
    """⑯ 북마크(목차)를 새로 쓴다 — 기존 북마크는 버리고 준 트리로 교체.
    현재 북마크 확인은 pdf_info.

    Args:
        src_path: 입력 PDF 절대경로
        out_path: 결과 저장 경로
        bookmarks: [{"title": 제목, "page": 1-기반 쪽, "children": [...](선택)}, ...]
        password: 암호(선택)
    Returns: {"out_path","bookmarks_added"}
    """
    return await _bg(lambda: outline_mod.set_bookmarks(src_path, out_path, bookmarks, password))


@mcp.tool()
async def pdf_set_metadata(
    src_path: str,
    out_path: str,
    title: Optional[str] = None,
    author: Optional[str] = None,
    subject: Optional[str] = None,
    keywords: Optional[str] = None,
    creator: Optional[str] = None,
    producer: Optional[str] = None,
    password: Optional[str] = None,
) -> dict:
    """⑰ 메타데이터(제목·작성자·주제·키워드 등)를 쓴다 — 준 항목만 갱신.

    Args:
        src_path: 입력 PDF 절대경로
        out_path: 결과 저장 경로
        title, author, subject, keywords, creator, producer: 바꿀 값(선택)
        password: 암호(선택)
    Returns: {"out_path","updated"}
    """
    return await _bg(lambda: info_mod.set_metadata(
        src_path, out_path, title, author, subject, keywords, creator, producer, password))


# ---- 진단 ------------------------------------------------------------------
@mcp.tool()
async def pdf_health() -> dict:
    """엔진 상태 점검 — pypdf/PDFium/Pillow 버전 확인(상주 앱 없음, 즉시 응답)."""
    def work():
        import PIL
        import pypdf
        import pypdfium2
        try:
            pdfium_ver = pypdfium2.PDFIUM_INFO.build
        except Exception:  # noqa: BLE001
            pdfium_ver = getattr(pypdfium2, "V_PDFIUM", "?")
        return {
            "alive": True,
            "stateless": True,
            "pypdf": pypdf.__version__,
            "pypdfium2": pypdfium2.__version__,
            "pdfium_build": str(pdfium_ver),
            "pillow": PIL.__version__,
        }
    return await _bg(work)


if __name__ == "__main__":
    mcp.run(transport="stdio")
