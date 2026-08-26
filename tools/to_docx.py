"""보고서 마크다운을 .docx 와 .html 로 변환한다. 표를 셀 단위로 옮기지 않기 위해서다.

    python tools/to_docx.py 결과보고서.md

docs/build/결과보고서.docx 와 .html 을 만든다.

**쓰는 법 두 가지.** 어느 쪽이든 표가 통째로 붙는다.

  1. .docx 를 워드로 열고 표를 선택해 공식 양식에 붙여넣는다 (가장 확실)
  2. .html 을 브라우저로 열고 표를 드래그해 복사한다 (서식이 더 깔끔할 때가 있다)

글꼴과 여백은 공식 양식과 같게 맞춰 두었다(맑은 고딕 10pt, 여백 35/30mm).
그대로 붙이면 양식 서식을 따라가므로 붙여넣은 뒤 글꼴만 확인하면 된다.

pagecount.py 와 같은 HTML 생성기를 쓰되, 이쪽은 제목 단계와 그림을 살린다.
pagecount 는 페이지 수만 세면 되므로 h3 만 처리한다.
"""
import html
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
OUT = DOCS / "build"

CSS = """
@page{size:A4;margin:35mm 30mm 30mm 30mm}
body{font-family:'Malgun Gothic','Noto Sans CJK KR',sans-serif;font-size:10pt;line-height:1.35}
table{border-collapse:collapse;width:100%;font-size:9pt;margin:4pt 0}
th,td{border:1px solid #999;padding:2pt 4pt;vertical-align:top}
th{background:#f0f0f0;font-weight:bold}
h1{font-size:14pt;margin:10pt 0 5pt}
h2{font-size:12pt;margin:9pt 0 4pt}
h3{font-size:11pt;margin:8pt 0 4pt}
p{margin:0 0 5pt 0}
pre{font-size:9pt;margin:4pt 0;font-family:inherit;white-space:pre-wrap}
img{max-width:100%}
"""


def inline(t: str) -> str:
    """굵게와 코드만 살린다. 나머지는 양식 서식을 따라가게 둔다."""
    t = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", t)
    t = re.sub(r"`(.+?)`", r"<code>\1</code>", t)
    return t


def to_html(body: str) -> str:
    out = [f"<html><head><meta charset='utf-8'><style>{CSS}</style></head><body>"]
    rows: list[str] = []
    para: list[str] = []

    def flush_table():
        if not rows:
            return
        # 구분선(|---|---|)은 버리고, 그 위 한 줄을 머리행으로 쓴다
        sep = next((i for i, r in enumerate(rows)
                    if set(r.replace("|", "").strip()) <= set("-: ")), None)
        cells = [r for i, r in enumerate(rows) if i != sep]
        buf = ["<table>"]
        for i, r in enumerate(cells):
            tag = "th" if (sep == 1 and i == 0) else "td"
            buf.append("<tr>" + "".join(
                f"<{tag}>{inline(html.escape(c.strip()))}</{tag}>"
                for c in r.strip("|").split("|")) + "</tr>")
        buf.append("</table>")
        out.append("".join(buf))
        rows.clear()

    def flush_para():
        if para:
            out.append(f"<p>{inline(html.escape(' '.join(para)))}</p>")
            para.clear()

    for raw in body.split("\n"):
        line = raw.rstrip()
        s = line.strip()

        if s.startswith("```"):
            flush_para()
            continue
        if s.startswith("|"):
            flush_para()
            rows.append(s)
            continue
        flush_table()

        if not s:
            flush_para()
            continue

        img = re.match(r"!\[[^\]]*\]\(([^)]+)\)", s)
        if img:
            flush_para()
            out.append(f'<p><img src="{(DOCS / img.group(1)).as_uri()}"/></p>')
            continue

        h = re.match(r"^(#{1,3}) +(.*)", s)
        if h:
            flush_para()
            n = len(h.group(1))
            out.append(f"<h{n}>{inline(html.escape(h.group(2)))}</h{n}>")
            continue

        # 도식과 글머리 목록은 줄바꿈을 지켜야 읽힌다
        if re.match(r"^\s{2,}|^\s*[·└├─│]", line):
            flush_para()
            out.append(f"<pre>{inline(html.escape(line))}</pre>")
            continue

        para.append(s)

    flush_para()
    flush_table()
    out.append("</body></html>")
    return "\n".join(out)


def main() -> None:
    name = sys.argv[1] if len(sys.argv) > 1 else "결과보고서.md"
    src = DOCS / name
    if not src.exists():
        raise SystemExit(f"{src} 가 없습니다")

    OUT.mkdir(exist_ok=True)
    stem = src.stem
    page = OUT / f"{stem}.html"
    # 인용 블록(> …)은 편집 지시라 옮기지 않는다
    body = "\n".join(l for l in src.read_text(encoding="utf-8").split("\n")
                     if not l.lstrip().startswith(">"))
    page.write_text(to_html(body), encoding="utf-8")

    # LibreOffice 는 HTML 을 Writer/Web 으로 열어 docx 로 바로 못 내보낸다.
    # odt 를 거치면 된다. 한글 파일명도 변환이 조용히 실패하므로 ASCII 로 작업한다.
    work = OUT / "_build"
    work.write_bytes(page.read_bytes())
    for fmt in ("odt", "docx"):
        subprocess.run(["libreoffice", "--headless", "--convert-to", fmt,
                        str(work if fmt == "odt" else work.with_suffix(".odt")),
                        "--outdir", str(OUT)],
                       check=True, capture_output=True, timeout=300)

    docx = OUT / f"{stem}.docx"
    work.with_suffix(".docx").replace(docx)
    for p in (work, work.with_suffix(".odt")):
        p.unlink(missing_ok=True)

    for f in (docx, page):
        print(f"  {f.relative_to(ROOT)}  ({f.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
