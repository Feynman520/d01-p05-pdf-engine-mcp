# pdf-engine-mcp

[한국어 안내 → README.ko.md](README.ko.md)

A local MCP server that drives **two native PDF engines** — **PDFium** (Chromium's PDF renderer, via `pypdfium2`) and **pypdf** (+`cryptography`) — to cover the full everyday PDF workflow: **inspect, merge/split, page surgery, watermark, render pages to images, extract text/images, fill AcroForm fields, encrypt/decrypt, compress, embed/extract attachments, rewrite bookmarks and metadata**.

> Design philosophy: same as its siblings ([word](https://github.com/Feynman520/d01-p04-word-engine-mcp) / [excel](https://github.com/Feynman520/d01-p02-excel-engine-mcp) / [ppt](https://github.com/Feynman520/d01-p03-ppt-engine-mcp) / [hwp](https://github.com/Feynman520/d01-p01-hwp-form-automation-mcp)) — expose **engine calls**, not hand-rolled file poking. Unlike the Office siblings there is no desktop app to automate, so this server is **stateless**: no COM session, no worker thread, fully cross-platform. Every tool call opens the file, works, writes to `out_path`, and closes. Originals are never modified.

## Requirements

- Python 3.10+ — verified on **3.12** (Windows 11; no OS-specific dependency)
- [Claude Code](https://claude.com/claude-code) or any MCP client
- No Adobe Acrobat, no MS Office, no Ghostscript needed

## Install

```powershell
git clone https://github.com/Feynman520/d01-p05-pdf-engine-mcp.git
cd d01-p05-pdf-engine-mcp
py -3.12 -m venv .venv          # or: python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

### Register with Claude Code

Run this in the cloned folder (uses absolute paths, so it works from anywhere afterwards):

```powershell
claude mcp add pdf-automation --scope user -- "$PWD\.venv\Scripts\python.exe" "$PWD\server.py"
```

`--scope user` makes it available in every project. Use `--scope project` to limit it to one project.

### Verify

```powershell
$py = ".\.venv\Scripts\python.exe"; $env:PYTHONUTF8 = "1"
& $py tests\smoke_engine.py   # runs all 17 tool paths on self-generated fixture PDFs
& $py tests\server_tools.py   # MCP tool registration
```

## Tools (17 core + 1 diagnostic)

| Group | Tool | Input → Output | Engine |
|---|---|---|---|
| Inspect | `pdf_info` | `path, password?` → pages, page sizes, metadata, encryption, form fields, attachments, bookmark tree | pypdf |
| Assemble | `pdf_merge` | `inputs[{path,pages?,password?}], out_path` → merged file | pypdf |
| | `pdf_split` | `src_path, pages?/out_path` or `out_dir, every` → extracted / chunked files | pypdf |
| | `pdf_pages` | `op: rotate\|delete\|reorder` (+`pages`/`degrees`/`order`) | pypdf |
| | `pdf_watermark` | `text` (built-in Helvetica, Latin) or `stamp_path` (any PDF), `mode: overlay\|background` | pypdf |
| Render | `pdf_render_images` | `src_path, out_dir, pages?, dpi, png\|jpg` → page images | **PDFium** |
| | `pdf_extract_text` | `src_path, pages?` → per-page text (honest empty result for scans) | **PDFium** |
| | `pdf_extract_images` | `src_path, out_dir, pages?` → embedded image originals | pypdf |
| Forms | `pdf_form_fields` | `path` → AcroForm field names/types/values | pypdf |
| | `pdf_fill_form` | `fields{name:value}, flatten?` → filled (optionally locked) form | pypdf |
| Security | `pdf_encrypt` | `user_password, owner_password?, AES-256, allow_printing?, allow_copying?` | pypdf |
| | `pdf_decrypt` | `password` → unencrypted copy (for files whose password you know) | pypdf |
| Optimize | `pdf_compress` | stream compression + duplicate removal (lossless), `image_quality?` (lossy) | pypdf |
| Attach | `pdf_attach_files` / `pdf_extract_attachments` | embed files into / extract from the PDF | pypdf |
| Structure | `pdf_bookmarks` | nested `[{title,page,children?}]` → rewritten outline | pypdf |
| | `pdf_set_metadata` | title/author/subject/keywords/creator/producer | pypdf |
| — | `pdf_health` | → engine versions (stateless, instant) | both |

Page specs are 1-based strings: `"3"`, `"1-3,5"`, `"4-"`, `"-2"`. Paths should be absolute.
PDF→Word conversion is intentionally **not** here — the word sibling's `word_convert` owns it.

## Architecture notes

- **Stateless by design**: PDF has no resident desktop app, so there is no session to manage —
  each call is open → work → write `out_path` → close. Blocking work is delegated to a thread
  (`anyio.to_thread`) to keep the event loop responsive.
- **Two engines, one rule**: PDFium does what pure Python cannot (rasterize, layout-aware text);
  pypdf does document surgery. PyMuPDF was deliberately avoided (AGPL vs this repo's MIT).
- **Text watermark** uses the built-in Helvetica font (Latin-1 only) drawn by a tiny built-in
  raw-PDF generator (`engine/rawpdf.py`) — for CJK watermarks pass a stamp PDF via `stamp_path`.
- **Honest extraction**: scanned PDFs return an empty text result with a note pointing to
  `pdf_render_images` + OCR, never hallucinated text.
- **Originals preserved**: results are always written to a new `out_path`/`out_dir`.

## Limitations

- Text watermark supports Latin scripts only (use `stamp_path` for CJK).
- `pdf_decrypt` requires the correct password — this is a convenience tool, not a cracker.
- XFA forms (legacy Adobe LiveCycle) are not supported; AcroForm only.

## License

[MIT](LICENSE)

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for how to contribute and [SECURITY.md](SECURITY.md) for reporting security issues.
