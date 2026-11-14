# pdf-engine-mcp (한국어 안내)

[English → README.md](README.md)

**네이티브 PDF 엔진 두 개** — **PDFium**(크롬의 PDF 렌더 엔진, `pypdfium2`)과 **pypdf**(+`cryptography`) — 를 호출해 일상적인 PDF 작업 전체를 다루는 로컬 MCP 서버입니다: **조회, 병합/분할, 페이지 수술, 워터마크, 페이지→이미지 렌더링, 텍스트/이미지 추출, 양식(AcroForm) 채우기, 암호화/해제, 압축, 첨부파일 심기/꺼내기, 북마크·메타데이터 쓰기**.

> 설계 철학: 형제 프로젝트([word](https://github.com/Feynman520/d01-p04-word-engine-mcp) / [excel](https://github.com/Feynman520/d01-p02-excel-engine-mcp) / [ppt](https://github.com/Feynman520/d01-p03-ppt-engine-mcp) / [hwp](https://github.com/Feynman520/d01-p01-hwp-form-automation-mcp))와 동일 — 파일을 손으로 쑤시지 않고 **엔진을 호출**한다. 단, 오피스 형제들과 달리 자동화할 상주 데스크톱 앱이 없으므로 이 서버는 **무상태(stateless)** 입니다: COM 세션도 워커 스레드도 없고 크로스플랫폼입니다. 모든 도구 호출은 열기 → 작업 → `out_path` 저장 → 닫기로 끝나며, 원본은 절대 수정하지 않습니다.

## 요구 사항

- Python 3.10+ — **3.12** 검증(Windows 11; OS 종속 의존성 없음)
- [Claude Code](https://claude.com/claude-code) 또는 임의의 MCP 클라이언트
- Adobe Acrobat·MS Office·Ghostscript 전부 불필요

## 설치

```powershell
git clone https://github.com/Feynman520/d01-p05-pdf-engine-mcp.git
cd d01-p05-pdf-engine-mcp
py -3.12 -m venv .venv          # 또는: python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

### Claude Code에 등록

클론한 폴더에서 실행합니다(절대경로가 박히므로 이후 어디서든 동작):

```powershell
claude mcp add pdf-automation --scope user -- "$PWD\.venv\Scripts\python.exe" "$PWD\server.py"
```

`--scope user`는 모든 프로젝트에서 사용 가능하게 합니다. 한 프로젝트로 한정하려면 `--scope project`.

### 검증

```powershell
$py = ".\.venv\Scripts\python.exe"; $env:PYTHONUTF8 = "1"
& $py tests\smoke_engine.py   # 자체 생성 픽스처로 17개 도구 경로 전부 실행
& $py tests\server_tools.py   # MCP 도구 등록 확인
```

## 도구 (핵심 17 + 진단 1)

| 분류 | 도구 | 하는 일 | 엔진 |
|---|---|---|---|
| 조회 | `pdf_info` | 페이지 수·크기, 메타데이터, 암호 여부, 양식 필드, 첨부 목록, 북마크 트리를 한 번에 | pypdf |
| 조립 | `pdf_merge` | 여러 PDF 병합(파일별 페이지 범위 지정) | pypdf |
| | `pdf_split` | 페이지 추출(`pages`+`out_path`) 또는 `every`쪽씩 분할(`out_dir`) | pypdf |
| | `pdf_pages` | 회전·삭제·재배열(`op: rotate\|delete\|reorder`) | pypdf |
| | `pdf_watermark` | 텍스트(내장 Helvetica, 라틴) 또는 도장 PDF(`stamp_path`) 겹치기 | pypdf |
| 렌더 | `pdf_render_images` | 페이지→PNG/JPG 렌더링(dpi 지정) | **PDFium** |
| | `pdf_extract_text` | 페이지별 텍스트 추출(스캔본이면 정직하게 빈 결과+OCR 안내) | **PDFium** |
| | `pdf_extract_images` | 내장 이미지 원본 추출 | pypdf |
| 양식 | `pdf_form_fields` | AcroForm 필드 이름·유형·현재값 읽기 | pypdf |
| | `pdf_fill_form` | 필드 채우기(+`flatten`: 굳혀서 수정 불가) | pypdf |
| 보안 | `pdf_encrypt` | AES-256 암호 걸기(인쇄/복사 허용 제어) | pypdf |
| | `pdf_decrypt` | 암호를 아는 파일의 잠금 해제 사본 | pypdf |
| 최적화 | `pdf_compress` | 무손실 압축(+`image_quality`로 이미지 손실 재압축) | pypdf |
| 첨부 | `pdf_attach_files` / `pdf_extract_attachments` | 파일 심기 / 꺼내기 | pypdf |
| 구조 | `pdf_bookmarks` | 북마크(목차) 트리 새로 쓰기 | pypdf |
| | `pdf_set_metadata` | 제목·작성자·주제·키워드 등 쓰기 | pypdf |
| — | `pdf_health` | 엔진 버전 확인(무상태, 즉시) | 둘 다 |

페이지 지정은 1-기반 문자열: `"3"`, `"1-3,5"`, `"4-"`, `"-2"`. 경로는 절대경로 권장.
PDF→Word 변환은 의도적으로 없음 — word 형제의 `word_convert` 담당(무중복 원칙).

## 아키텍처 노트

- **무상태 설계**: PDF엔 상주 앱이 없어 관리할 세션 자체가 없다 — 호출마다 열기→작업→저장→닫기.
  블로킹 작업은 `anyio.to_thread`로 위임해 이벤트 루프를 막지 않는다.
- **두 엔진, 한 원칙**: 순수 파이썬이 못 하는 것(래스터라이즈·레이아웃 텍스트)은 PDFium이,
  문서 수술은 pypdf가 맡는다. PyMuPDF는 AGPL이라 이 repo의 MIT와 충돌해 의도적으로 배제.
- **텍스트 워터마크**는 내장 미니 PDF 생성기(`engine/rawpdf.py`)가 Helvetica(라틴-1 한정)로
  그린다 — 한글 워터마크는 도장 PDF를 만들어 `stamp_path`로.
- **정직한 추출**: 스캔 PDF는 빈 텍스트 결과와 함께 `pdf_render_images`+OCR 안내를 돌려준다.
  날조하지 않는다.
- **원본 보존**: 결과는 항상 새 `out_path`/`out_dir`에 저장.

## 한계

- 텍스트 워터마크는 라틴 문자만(한글 등은 `stamp_path` 사용).
- `pdf_decrypt`는 올바른 암호가 필요 — 편의 도구이지 해제기가 아니다.
- XFA 양식(구형 Adobe LiveCycle)은 미지원, AcroForm 전용.

## 라이선스

[MIT](LICENSE)

## 기여

의견과 PR 안내는 [CONTRIBUTING.md](CONTRIBUTING.md)를, 보안 문제 신고는 [SECURITY.md](SECURITY.md)를 봐 주세요.
