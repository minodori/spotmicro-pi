"""DOCX 안의 텍스트를 찾아 바꾼다. 워드에서 한 글자씩 손보지 않기 위해서다.

    python tools/docx_edit.py --dry     무엇이 바뀌는지만 본다
    python tools/docx_edit.py           실제로 바꾼다 (원본은 .bak 으로 남긴다)

워드는 같은 문단이라도 서식이 조금만 달라지면 <w:r> 을 쪼갠다. 그래서 "검증 8게이트"
같은 문자열이 XML 에서 한 덩어리가 아닐 수 있다. 여기서는 <w:t> 안의 글자만 이어붙여
한 줄로 만든 뒤 그 위에서 찾고, 걸친 런 중 첫 번째에 바뀐 글자를 몰아넣고 나머지를
비운다. 첫 런의 서식이 유지되므로 눈에 띄는 변화가 없다.

**파일을 워드나 리브레오피스에서 닫고 실행해야 한다.** 열려 있으면 저장할 때 이쪽
수정이 덮인다.
"""
import argparse
import glob
import re
import shutil
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# (찾을 것, 바꿀 것, 왜)
EDITS = [
    ("CLS6336HV x 2,( 26.7kg·cm, 461°/s),  Futaba",
     "CLS6336HV ×2 (26.7 kg·cm, 461°/s), Futaba",
     "곱셈기호를 ×9 와 맞추고 쉼표 뒤 괄호와 겹공백을 정리한다"),
    ("네발 지지 구간을", "네 발 지지 구간을", "다른 다섯 곳은 '네 발 지지' 다"),
    ("기구 치수를 바로잡은 결과는 SpotMicro 계열 저장소 전체에 그대로 적용된다",
     "치수가 코드 세 곳에서 어긋나 있다는 사실은 SpotMicro 계열 저장소에 공통이다",
     "우리 실측값은 우리 로봇 것이다. 옮겨가는 것은 값이 아니라 발견이다"),
    ("기구 파라미터 정정 결과는 SpotMicro 계열 전체에 즉시 적용되며",
     "치수가 코드 세 곳에서 어긋나 있다는 사실은 SpotMicro 계열 저장소에 공통이며",
     "같은 과장. 축약본 판에도 남아 있었다"),
    ("Intel RealSense D435 를 보유하고 있으며", "Intel RealSense D435 를 이미 가지고 있으며",
     "'보유하고 있으며' 는 한자투"),
    ("비용 장벽과 환경 장벽을 함께 낮춘다", "비용과 환경 문턱을 함께 낮춘다",
     "'장벽'을 두 번 써서 구호처럼 읽힌다"),
    ("428°/s", "500°/s",
     "폐기한 값. 데이터시트 6.0V 열은 0.12 s/60° = 500°/s"),
    ("6~7.4V", "6V",
     "벅 컨버터를 6V 로 확정했으므로 범위 표기가 애매하다"),
    ("python RaspberryPi/start_automatic_gait.py",
     "cd RaspberryPi && python start_automatic_gait.py",
     "저장소 루트에서 실행하면 ModuleNotFoundError 가 난다"),
    ("속도 4% 이내", "속도 8% 이내",
     "실측은 50->52(4%)와 62->57(8%) 두 점이고 본문 표는 8% 다"),
    ("실측 슬루", "요구 각속도",
     "서보에 위치 피드백이 없어 실측이 아니다. 명령값의 차분이다"),
    ("검증 게이트 8종", "검증 항목 8가지", "gate 직역"),
    ("검증 8게이트", "검증 8항목", "gate 직역"),
    ("8게이트로 확인", "여덟 항목으로 확인", "gate 직역"),
    ("8게이트가", "여덟 항목이", "gate 직역"),
    ("(8게이트)", "(8항목)", "gate 직역"),
    ("검증 게이트가 가리키던", "검증에서 걸렸던", "gate 직역"),
    ("일치를 게이트로 잡는", "일치를 검증 항목으로 잡는", "gate 직역"),
    ("검증 게이트를 실행", "검증 항목을 실행", "gate 직역 (붙임1 SBOM 용도 칸)"),
    ("게이트", "검증 항목", "gate 직역 (검증 항목 표의 머리 칸)"),
    ("피라멘트", "필라멘트", "오타"),
    ("단게", "단계", "오타"),
    ("힝목", "항목", "오타"),
    ("보행 주건", "보행 조건", "오타"),
    ("다섯 단계 계보를", "계보를",
     "개발배경에서 스터디 저장소 둘을 뺐으므로 다섯이 아니다"),
    ("**", "", "마크다운 별표가 그대로 남았다"),
    (", 환경 7개 병렬", "",
     "근거를 찾지 못했다. train.py 기본값은 12 이고 meta.json 에 기록이 없다"),
]

CELL = re.compile(r"<w:t(?: [^>]*)?>(.*?)</w:t>", re.S)


def esc(s: str) -> str:
    """XML 이스케이프. 이것을 빼먹어 && 가 문서를 깨뜨린 적이 있다."""
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def unesc(s: str) -> str:
    return (s.replace("&lt;", "<").replace("&gt;", ">")
             .replace("&quot;", '"').replace("&apos;", "'").replace("&amp;", "&"))


def apply(xml: str, find: str, repl: str) -> tuple[str, int]:
    """<w:t> 조각을 이어붙인 평문에서 찾아, 걸친 조각들에 나눠 쓴다."""
    spans = [(m.start(1), m.end(1), unesc(m.group(1))) for m in CELL.finditer(xml)]
    if not spans:
        return xml, 0
    flat = "".join(s[2] for s in spans)
    # 평문 위치 -> (조각 번호, 조각 안 위치)
    idx, pos = [], 0
    for i, (_, _, t) in enumerate(spans):
        for j in range(len(t)):
            idx.append((i, j))
        pos += len(t)

    hits = []
    start = 0
    while True:
        k = flat.find(find, start)
        if k < 0:
            break
        hits.append(k)
        start = k + len(find)
    if not hits:
        return xml, 0

    # 뒤에서부터 고쳐야 앞쪽 좌표가 밀리지 않는다
    parts = [list(s) for s in spans]
    texts = [s[2] for s in spans]
    for k in reversed(hits):
        first_seg, first_off = idx[k]
        last_seg, last_off = idx[k + len(find) - 1]
        if first_seg == last_seg:
            t = texts[first_seg]
            texts[first_seg] = t[:first_off] + repl + t[last_off + 1:]
        else:
            texts[first_seg] = texts[first_seg][:first_off] + repl
            for s in range(first_seg + 1, last_seg):
                texts[s] = ""
            texts[last_seg] = texts[last_seg][last_off + 1:]

    out, prev = [], 0
    for (a, b, _), t in zip(spans, texts):
        out.append(xml[prev:a])
        out.append(esc(t))
        prev = b
    out.append(xml[prev:])
    return "".join(out), len(hits)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--file", default=None)
    a = ap.parse_args()

    p = Path(a.file) if a.file else Path(sorted(glob.glob(str(ROOT / "Docs" / "*.docx")))[-1])
    lock = p.parent / f".~lock.{p.name}#"
    if lock.exists():
        raise SystemExit(f"{p.name} 이 열려 있습니다. 워드/리브레오피스를 닫고 다시 실행하십시오.")

    z = zipfile.ZipFile(p)
    xml = z.read("word/document.xml").decode("utf-8")
    names = z.namelist()
    blobs = {n: z.read(n) for n in names}
    z.close()

    total = 0
    for find, repl, why in EDITS:
        xml, n = apply(xml, find, repl)
        total += n
        mark = "  " if n else "✗ "
        shown = repl if repl else "(삭제)"
        print(f"{mark}{n}건  {find[:42]:44s} -> {shown[:38]:40s} {why}")

    print(f"\n  모두 {total}건")
    if a.dry:
        print("  --dry 라 저장하지 않았습니다.")
        return

    # 이미 있으면 덮지 않는다. 여러 번 돌려도 맨 처음 원본이 남아야 한다
    bak = p.with_suffix(".docx.bak")
    if not bak.exists():
        shutil.copy2(p, bak)
    blobs["word/document.xml"] = xml.encode("utf-8")
    with zipfile.ZipFile(p, "w", zipfile.ZIP_DEFLATED) as out:
        for n in names:
            out.writestr(n, blobs[n])
    print(f"  저장했습니다. 원본은 {p.with_suffix('.docx.bak').name}")


if __name__ == "__main__":
    main()
