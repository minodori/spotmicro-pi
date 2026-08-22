"""결과보고서가 5페이지에 들어가는지 잰다.

    python tools/pagecount.py

제출 서식은 **결과보고서 본문 5페이지 이내**를 요구한다(붙임1·2 는 제한 밖).
줄 수로 어림하면 크게 틀린다 — 원문이 80자에서 줄바꿈돼 있어 줄 수는 실제 분량과
비례하지 않고, 표는 줄당 차지하는 높이가 다르다. 그래서 실제로 렌더해서 센다.

LibreOffice 로 A4·맑은고딕 10pt 로 변환한 뒤 PDF 페이지를 센다. 공식 서식의 여백을
확인할 수 없어 20mm 를 가정하므로, **여기서 5페이지면 실제로도 대체로 5페이지**지만
최종 확인은 서식 파일에 붙여넣고 해야 한다.
"""
from __future__ import annotations

import html
import re
import subprocess
import sys
import tempfile
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "docs" / "결과보고서_초안.md"
CSS = """
@page{size:A4;margin:20mm}
body{font-family:'Malgun Gothic','Noto Sans CJK KR',sans-serif;font-size:10pt;line-height:1.3}
table{border-collapse:collapse;width:100%;font-size:9pt;margin:3pt 0}
td{border:1px solid #999;padding:1pt 3pt}
h3{font-size:11pt;margin:7pt 0 3pt}
p{margin:3pt 0}
pre{font-size:9pt;margin:3pt 0;font-family:inherit}
"""


def to_html(body: str) -> str:
    out, rows, para = [f"<html><head><meta charset='utf-8'><style>{CSS}</style></head><body>"], [], []

    def flush_table():
        if not rows:
            return
        cells = [r for r in rows if not set(r.replace("|", "").strip()) <= set("-: ")]
        out.append("<table>" + "".join(
            "<tr>" + "".join(f"<td>{html.escape(c.strip())}</td>"
                             for c in r.strip("|").split("|")) + "</tr>"
            for r in cells) + "</table>")
        rows.clear()

    def flush_para():
        if not para:
            return
        t = " ".join(para)
        t = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", t)
        t = re.sub(r"`(.+?)`", r"\1", t)
        out.append(f"<p>{t}</p>")
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
        if s.startswith("### "):
            flush_para()
            out.append(f"<h3>{s[4:]}</h3>")
            continue
        # 도식과 글머리 목록은 줄바꿈을 지켜야 읽힌다
        if re.match(r"^\s{2,}|^\s*[·└├─│]", line):
            flush_para()
            out.append(f"<pre>{html.escape(line)}</pre>")
            continue
        para.append(s)

    flush_para()
    flush_table()
    out.append("</body></html>")
    return "\n".join(out)


def main() -> None:
    src = SRC.read_text(encoding="utf-8")
    m = re.search(r"## 프로젝트 개요(.*?)# 붙임 1", src, re.S)
    if not m:
        raise SystemExit("본문 범위를 찾지 못했습니다 (프로젝트 개요 ~ 붙임 1)")

    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "report.html"
        p.write_text(to_html(m.group(1)), encoding="utf-8")
        subprocess.run(["libreoffice", "--headless", "--convert-to", "pdf",
                        str(p), "--outdir", d],
                       check=True, capture_output=True, timeout=300)
        pdf = (Path(d) / "report.pdf").read_bytes()

    pages = len(re.findall(rb"/Type\s*/Page[^s]", pdf))
    chars = len(re.sub(r"\s", "", m.group(1)))
    print(f"  본문 {pages} 페이지   ({chars:,} 자)")
    if pages > 5:
        print(f"  ❌ 5페이지를 {pages - 5} 페이지 초과합니다. 약 {(pages-5)/pages:.0%} 를 덜어내야 합니다.")
    else:
        print("  ✅ 5페이지 이내")
    sys.exit(0 if pages <= 5 else 1)


if __name__ == "__main__":
    main()
