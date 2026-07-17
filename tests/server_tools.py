"""MCP 계층 검증 — server.py가 정상 임포트되고 18개 도구가 등록됐는지 확인한다.

실행: .venv\\Scripts\\python.exe tests\\server_tools.py
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import anyio  # noqa: E402
import server  # noqa: E402

EXPECTED = {
    "pdf_info",
    "pdf_merge",
    "pdf_split",
    "pdf_pages",
    "pdf_watermark",
    "pdf_render_images",
    "pdf_extract_text",
    "pdf_extract_images",
    "pdf_form_fields",
    "pdf_fill_form",
    "pdf_encrypt",
    "pdf_decrypt",
    "pdf_compress",
    "pdf_attach_files",
    "pdf_extract_attachments",
    "pdf_bookmarks",
    "pdf_set_metadata",
    "pdf_health",
}


async def _list():
    tools = await server.mcp.list_tools()
    return {t.name for t in tools}


def main():
    names = anyio.run(_list)
    print(f"[srv] 등록된 도구({len(names)}): {sorted(names)}", flush=True)
    missing = EXPECTED - names
    extra = names - EXPECTED
    assert not missing, f"누락된 도구: {missing}"
    print(f"[srv] === MCP 계층 OK: 기대한 18개 도구 모두 등록됨 (추가:{extra or '없음'}) ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
