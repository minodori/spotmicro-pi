"""검증 항목 표 뒤에 시뮬-실물 정합 근거 표 두 개를 넣는다.

    python tools/docx_insert_tables.py --dry
    python tools/docx_insert_tables.py

가안에 "기하 0.0000 mm · 기구학 2% · 동역학 8% 이내" 라는 결론만 있고 그것을
뒷받침하는 표가 빠져 있었다. 숫자만 있고 근거가 없으면 심사에서 "무엇과 무엇의
차이냐" 는 질문에 문서가 답하지 못한다.

서식을 맞추려고 문서 안의 4열 표(네 발 지지 표)를 본으로 복제한다. 새로 만들면
테두리·너비·글꼴이 주변과 달라진다.
"""
import argparse
import glob
import re
import shutil
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TR = re.compile(r"<w:tr[ >].*?</w:tr>", re.S)
TC = re.compile(r"<w:tc>.*?</w:tc>", re.S)
WT = re.compile(r"(<w:t(?: [^>]*)?>)(.*?)(</w:t>)", re.S)


def esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


TABLE_A = [
    ["구분", "무엇을 비교했나", "실물 vs 시뮬", "차이"],
    ["기하", "시뮬이 그리는 발끝 vs 제어가 계산하는 발끝", "상속 코드 18 mm", "0.0000 mm"],
    ["기구학", "무릎 최대 각속도", "323 vs 318 °/s", "2%"],
    ["동역학", "같은 궤적을 재생한 전진 속도", "50 / 62 vs 52 / 57 mm/s", "8% 이내"],
]

TABLE_B = [
    ["보행 설정", "이론 (보폭÷주기)", "실물 실측", "시뮬 재생"],
    ["발높이 20 / 주기 1400 / 보폭 −70", "50 mm/s", "50 mm/s (1m 를 20초)", "52 mm/s"],
    ["발높이 36 / 주기 1300 / 보폭 −80", "62 mm/s", "62 mm/s (1m 를 16초)", "57 mm/s"],
]

P_BEFORE_A = "시뮬레이션이 실물을 예측하는가 — 기하 · 기구학 · 동역학"
P_AFTER_A = ("기하의 0.0000 mm 는 실물을 그 정밀도로 쟀다는 뜻이 아니다. 시뮬레이터가 "
             "그리는 발끝과 제어 코드가 계산하는 발끝이 같은 자리인지를 40자세 × 4다리에서 "
             "대조한 값이고 합격선은 1.0 mm 다. 같은 것을 상속 코드에서 재면 중앙값 18 mm 로 "
             "어긋난다. 두 계산이 갈라질 수 있는 자리를 막아 두었다는 확인이다.")
P_BEFORE_B = "동역학은 두 설정에서 따로 확인했다. 한 점에서 맞는 것은 우연일 수 있다."
P_AFTER_B = ("보폭과 주기를 바꾸면 이론 속도가 50에서 62로 움직이는데 실물과 시뮬이 그 변화를 "
             "함께 따라갔다. 한 점에서 맞추는 것은 상수를 하나 조정하면 되지만, 입력을 바꿨을 때 "
             "함께 움직이는 것은 그렇게 만들 수 없다. 공개 SpotMicro 시뮬레이션은 관절 관성을 "
             "1e-6, 모터 힘을 12.5 N·m(서보 스톨 3.14 의 4.0배), 총 질량을 5.30 kg(실측 2.20 의 "
             "2.4배)으로 두어 대부분의 궤적이 걷는다. 거기서 실물로 넘어가는 것은 궤적뿐이다.")


def fill_row(row: str, values: list[str]) -> str:
    """행 안의 셀들에 값을 채운다. 셀마다 첫 <w:t> 에 쓰고 나머지는 비운다."""
    out, prev = [], 0
    for i, m in enumerate(TC.finditer(row)):
        cell = m.group(0)
        v = esc(values[i]) if i < len(values) else ""
        first = [True]

        def sub(mm):
            if first[0]:
                first[0] = False
                return mm.group(1) + v + mm.group(3)
            return mm.group(1) + mm.group(3)

        new = WT.sub(sub, cell)
        if first[0]:  # <w:t> 가 없는 셀이면 런에 하나 만들어 넣는다
            new = new.replace("</w:rPr>", f"</w:rPr><w:t>{v}</w:t>", 1)
        out.append(row[prev:m.start()])
        out.append(new)
        prev = m.end()
    out.append(row[prev:])
    return "".join(out)


def build_table(tpl: str, data: list[list[str]]) -> str:
    rows = TR.findall(tpl)
    head_tpl, body_tpl = rows[0], rows[1]
    head = tpl[:tpl.index(rows[0])]          # tblPr + tblGrid
    tail = "</w:tbl>"
    body = [fill_row(head_tpl, data[0])]
    body += [fill_row(body_tpl, r) for r in data[1:]]
    return head + "".join(body) + tail


def build_para(tpl: str, text: str, bold: bool = False) -> str:
    p = tpl
    first = [True]

    def sub(mm):
        if first[0]:
            first[0] = False
            return mm.group(1) + esc(text) + mm.group(3)
        return mm.group(1) + mm.group(3)

    p = WT.sub(sub, p)
    if first[0]:
        p = p.replace("</w:r>", f"<w:t>{esc(text)}</w:t></w:r>", 1)
    if bold:
        p = p.replace("<w:rPr></w:rPr>", "<w:rPr><w:b/><w:bCs/></w:rPr>")
    return p


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true")
    a = ap.parse_args()

    p = Path(sorted(f for f in glob.glob(str(ROOT / "Docs" / "*.docx"))
                    if not f.endswith(".bak"))[-1])
    if (p.parent / f".~lock.{p.name}#").exists():
        raise SystemExit(f"{p.name} 이 열려 있습니다. 닫고 다시 실행하십시오.")

    z = zipfile.ZipFile(p)
    names, blobs = z.namelist(), {n: z.read(n) for n in z.namelist()}
    xml = blobs["word/document.xml"].decode("utf-8")
    z.close()

    if "323 vs 318" in xml:
        raise SystemExit("이미 들어가 있습니다.")

    tbls = list(re.finditer(r"<w:tbl>.*?</w:tbl>", xml, re.S))
    tpl = next(t.group(0) for t in tbls if "네 발 지지" in re.sub(r"<[^>]+>", "", t.group(0)))
    anchor = next(t for t in tbls if "액추에이터" in re.sub(r"<[^>]+>", "", t.group(0)))
    para_tpl = re.search(r"<w:p><w:pPr><w:pStyle w:val=\"BodyText\"/>.*?</w:p>",
                         xml[anchor.end():anchor.end() + 3000], re.S).group(0)

    block = (build_para(para_tpl, P_BEFORE_A, bold=True)
             + build_table(tpl, TABLE_A)
             + build_para(para_tpl, P_AFTER_A)
             + build_para(para_tpl, P_BEFORE_B, bold=True)
             + build_table(tpl, TABLE_B)
             + build_para(para_tpl, P_AFTER_B))

    new = xml[:anchor.end()] + block + xml[anchor.end():]

    import xml.etree.ElementTree as ET
    ET.fromstring(new)  # 깨졌으면 여기서 멈춘다
    print("  XML 정상")
    print(f"  표 {new.count('<w:tbl>')}개 (전 {xml.count('<w:tbl>')}개)")
    for row in TABLE_A + [[]] + TABLE_B:
        print("   ", " | ".join(row))

    if a.dry:
        print("\n  --dry 라 저장하지 않았습니다.")
        return

    bak = p.with_suffix(".docx.bak2")
    if not bak.exists():
        shutil.copy2(p, bak)
    blobs["word/document.xml"] = new.encode("utf-8")
    with zipfile.ZipFile(p, "w", zipfile.ZIP_DEFLATED) as out:
        for n in names:
            out.writestr(n, blobs[n])
    print(f"\n  저장했습니다. 직전 판은 {bak.name}")


if __name__ == "__main__":
    main()
